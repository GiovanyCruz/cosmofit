"""Cobaya worker subprocess entry point."""

from __future__ import annotations

import json
import logging
import random
import sys
import traceback
from pathlib import Path
from typing import Any

import numpy as np
from cobaya.run import run

from cosmofit.application import deserialize_run_config
from cosmofit.cobaya_engine.artifacts import (
    RunArtifacts,
    list_chain_files,
    write_status,
    write_updated_cobaya_input,
)


def main(argv: list[str] | None = None) -> int:
    """Execute Cobaya for an already prepared run directory."""

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        raise SystemExit(
            "Usage: python -m cosmofit.cobaya_engine.worker <run-directory>"
        )

    artifacts = _artifacts_from_run_directory(Path(args[0]).resolve())
    logger = _configure_worker_logging(artifacts)
    run_config = _load_run_config(artifacts)
    _seed_random_generators(run_config.sampler.seed)
    write_status(artifacts, state="running")

    try:
        updated_info, sampler = run(
            artifacts.cobaya_input_path,
            output=str(artifacts.chain_prefix),
            debug=str(artifacts.worker_log_path),
            stop_at_error=True,
            force=run_config.runtime.overwrite,
            no_mpi=True,
        )
        write_updated_cobaya_input(artifacts, updated_info)
        summary = _build_summary(
            updated_info=updated_info,
            sampler=sampler,
            artifacts=artifacts,
        )
        with artifacts.summary_path.open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2, sort_keys=True)
            handle.write("\n")
        write_status(
            artifacts,
            state="succeeded",
            exit_code=0,
            extra={"summary_path": str(artifacts.summary_path)},
        )
        logger.info("Cobaya worker completed successfully.")
        return 0
    except Exception as exc:
        logger.exception("Cobaya worker failed.")
        write_status(
            artifacts,
            state="failed",
            exit_code=1,
            message=str(exc),
            extra={"traceback": traceback.format_exc()},
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


def _artifacts_from_run_directory(run_directory: Path) -> RunArtifacts:
    logs_directory = run_directory / "logs"
    chains_directory = run_directory / "chains"
    return RunArtifacts(
        run_directory=run_directory,
        logs_directory=logs_directory,
        chains_directory=chains_directory,
        input_yaml_path=run_directory / "input.yaml",
        normalized_config_path=run_directory / "normalized_config.json",
        cobaya_input_path=run_directory / "cobaya_input.yaml",
        updated_cobaya_input_path=run_directory / "updated_cobaya_input.yaml",
        summary_path=run_directory / "summary.json",
        status_path=run_directory / "status.json",
        metadata_path=run_directory / "metadata.json",
        worker_log_path=logs_directory / "worker.log",
        cobaya_stdout_path=logs_directory / "cobaya.stdout.log",
        cobaya_stderr_path=logs_directory / "cobaya.stderr.log",
        chain_prefix=chains_directory / "chain",
    )


if __name__ == "__main__":
    raise SystemExit(main())
