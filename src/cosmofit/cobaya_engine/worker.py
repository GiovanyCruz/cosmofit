"""Cobaya worker subprocess entry point."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import random
import signal
import sys
import traceback
from pathlib import Path
from typing import Any

import numpy as np
from cobaya.run import run

from cosmofit.application import RunConfig, deserialize_run_config, load_worker_request
from cosmofit.application.execution import WorkerRequest
from cosmofit.cobaya_engine.artifacts import (
    RunArtifacts,
    list_chain_files,
    write_json_artifact,
    write_status,
    write_updated_cobaya_input,
)

_EVENT_PREFIX = "COSMOFIT_EVENT "
_cancel_requested = False


def main(argv: list[str] | None = None) -> int:
    """Execute Cobaya for an already prepared run directory."""

    parser = argparse.ArgumentParser()
    parser.add_argument("request_path")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    request = load_worker_request(Path(args.request_path).resolve())
    with request.normalized_config_path.open(encoding="utf-8") as handle:
        run_config = deserialize_run_config(json.load(handle))
    return run_worker_request(request, run_config)


def run_worker_request(request: WorkerRequest, run_config: RunConfig) -> int:
    """Execute a prepared worker request in the current process."""

    global _cancel_requested
    _cancel_requested = False
    artifacts = _artifacts_from_request(request)
    logger = _configure_worker_logging(artifacts)
    _install_signal_handlers()
    started_at = _utc_timestamp()
    try:
        _seed_random_generators(run_config.sampler.seed)
        _emit_event(
            artifacts,
            event="starting",
            message="Iniciando worker de Cobaya.",
            run_directory=str(artifacts.run_directory),
        )
        write_status(
            artifacts,
            state="starting",
            extra={
                "pid": _current_pid(),
                "started_at": started_at,
                "run_label": run_config.runtime.run_label,
            },
        )
        with _tee_standard_streams(artifacts):
            _emit_event(
                artifacts,
                event="running",
                message="Ejecucion de Cobaya en progreso.",
            )
            write_status(
                artifacts,
                state="running",
                extra={
                    "pid": _current_pid(),
                    "started_at": started_at,
                    "run_label": run_config.runtime.run_label,
                },
            )
            updated_info, sampler = run(
                artifacts.cobaya_input_path,
                output=str(artifacts.chain_prefix),
                debug=str(artifacts.worker_log_path),
                stop_at_error=True,
                force=run_config.runtime.overwrite,
                no_mpi=True,
            )
            _raise_if_cancel_requested()
            write_updated_cobaya_input(artifacts, updated_info)
            summary = _build_summary(
                updated_info=updated_info,
                sampler=sampler,
                artifacts=artifacts,
            )
            write_json_artifact(artifacts.summary_path, summary)
            _validate_success_artifacts(artifacts)
        finished_at = _utc_timestamp()
        write_status(
            artifacts,
            state="succeeded",
            exit_code=0,
            extra={
                "pid": _current_pid(),
                "started_at": started_at,
                "finished_at": finished_at,
                "summary_path": str(artifacts.summary_path),
                "final_run_directory": str(artifacts.run_directory),
            },
        )
        _emit_event(
            artifacts,
            event="completed",
            message="Ejecucion completada correctamente.",
            run_directory=str(artifacts.run_directory),
        )
        print(f"RUN_DIRECTORY {artifacts.run_directory}", flush=True)
        logger.info("Cobaya worker completed successfully.")
        return 0
    except _WorkerCancelled:
        finished_at = _utc_timestamp()
        write_status(
            artifacts,
            state="cancelled",
            exit_code=130,
            message="Cobaya worker cancelled.",
            extra={
                "pid": _current_pid(),
                "started_at": started_at,
                "finished_at": finished_at,
            },
        )
        _emit_event(
            artifacts,
            event="cancelled",
            message="La ejecucion fue cancelada.",
            run_directory=str(artifacts.run_directory),
        )
        logger.info("Cobaya worker cancelled.")
        return 130
    except Exception as exc:
        finished_at = _utc_timestamp()
        logger.exception("Cobaya worker failed.")
        write_status(
            artifacts,
            state="failed",
            exit_code=1,
            message=str(exc),
            extra={
                "pid": _current_pid(),
                "started_at": started_at,
                "finished_at": finished_at,
                "traceback": traceback.format_exc(),
            },
        )
        _emit_event(
            artifacts,
            event="failed",
            message=str(exc) or "La ejecucion fallo.",
            run_directory=str(artifacts.run_directory),
        )
        return 1


def _load_run_config(artifacts: RunArtifacts):
    with artifacts.normalized_config_path.open(encoding="utf-8") as handle:
        return deserialize_run_config(json.load(handle))


def _seed_random_generators(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def _build_summary(
    *,
    updated_info: dict[str, Any],
    sampler: Any,
    artifacts: RunArtifacts,
) -> dict[str, Any]:
    products = sampler.products()
    sample = products.get("sample")
    progress = products.get("progress")
    return {
        "chain_files": list_chain_files(artifacts),
        "sample_size": len(sample) if sample is not None else 0,
        "progress_rows": len(progress.index) if progress is not None else 0,
        "updated_info_keys": sorted(updated_info.keys()),
    }


def _configure_worker_logging(artifacts: RunArtifacts) -> logging.Logger:
    logger = logging.getLogger("cosmofit.cobaya_engine.worker")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.FileHandler(artifacts.worker_log_path, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    logger.addHandler(handler)
    return logger


def _artifacts_from_request(request: WorkerRequest) -> RunArtifacts:
    logs_directory = request.run_directory / "logs"
    chains_directory = request.run_directory / "chains"
    return RunArtifacts(
        run_directory=request.run_directory,
        logs_directory=logs_directory,
        chains_directory=chains_directory,
        input_yaml_path=request.run_directory / "input.yaml",
        normalized_config_path=request.normalized_config_path,
        cobaya_input_path=request.cobaya_input_path,
        updated_cobaya_input_path=request.updated_cobaya_input_path,
        summary_path=request.summary_path,
        status_path=request.status_path,
        metadata_path=request.run_directory / "metadata.json",
        worker_log_path=request.worker_log_path,
        cobaya_stdout_path=request.cobaya_stdout_path,
        cobaya_stderr_path=request.cobaya_stderr_path,
        events_path=request.events_path,
        chain_prefix=request.chain_prefix,
    )


class _WorkerCancelled(RuntimeError):
    """Raised when the worker receives a cancellation signal."""


class _StreamTee(io.TextIOBase):
    def __init__(self, original: io.TextIOBase, destination: Path) -> None:
        self._original = original
        self._handle = destination.open("w", encoding="utf-8")
        self._closed = False

    def write(self, text: str) -> int:
        if self._closed:
            return 0
        self._original.write(text)
        self._original.flush()
        self._handle.write(text)
        self._handle.flush()
        return len(text)

    def flush(self) -> None:
        if self._closed:
            return
        self._original.flush()
        self._handle.flush()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._original.flush()
        self._handle.close()


@contextlib.contextmanager
def _tee_standard_streams(artifacts: RunArtifacts):
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    stdout_tee = _StreamTee(original_stdout, artifacts.cobaya_stdout_path)
    stderr_tee = _StreamTee(original_stderr, artifacts.cobaya_stderr_path)
    sys.stdout = stdout_tee
    sys.stderr = stderr_tee
    try:
        yield
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        stdout_tee.close()
        stderr_tee.close()


def _emit_event(
    artifacts: RunArtifacts,
    *,
    event: str,
    message: str,
    run_directory: str | None = None,
) -> None:
    payload = {
        "event": event,
        "message": message,
        "run_directory": run_directory or str(artifacts.run_directory),
        "timestamp": _utc_timestamp(),
    }
    with artifacts.events_path.open("a", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True)
        handle.write("\n")
    print(_EVENT_PREFIX + json.dumps(payload, sort_keys=True), flush=True)


def _install_signal_handlers() -> None:
    signal.signal(signal.SIGTERM, _handle_cancel_signal)
    signal.signal(signal.SIGINT, _handle_cancel_signal)


def _handle_cancel_signal(_signum: int, _frame: object) -> None:
    global _cancel_requested
    _cancel_requested = True


def _raise_if_cancel_requested() -> None:
    if _cancel_requested:
        raise _WorkerCancelled()


def _validate_success_artifacts(artifacts: RunArtifacts) -> None:
    updated_yaml = artifacts.chain_prefix.with_suffix(".updated.yaml")
    chain_files = list_chain_files(artifacts)
    if not updated_yaml.is_file():
        raise RuntimeError("Cobaya did not produce chains/chain.updated.yaml.")
    if not chain_files:
        raise RuntimeError("Cobaya did not produce any chain text files.")


def _utc_timestamp() -> str:
    from datetime import UTC, datetime

    return datetime.now(tz=UTC).isoformat()


def _current_pid() -> int:
    import os

    return os.getpid()


if __name__ == "__main__":
    raise SystemExit(main())
