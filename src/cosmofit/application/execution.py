"""Execution preparation helpers shared by the CLI worker and the desktop UI."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from cosmofit.application.config_models import (
    CosmicChronometerDatasetConfig,
    RunConfig,
)
from cosmofit.application.services import (
    build_background_model,
    build_cosmic_chronometers_likelihood,
    resolve_run_config,
)
from cosmofit.cobaya_engine.artifacts import (
    RunArtifacts,
    prepare_run_artifacts,
    write_cobaya_input,
    write_input_yaml,
    write_metadata,
    write_normalized_config,
    write_status,
)
from cosmofit.cobaya_engine.config_builder import build_cobaya_input

WORKER_REQUEST_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class WorkerRequest:
    """Serializable worker launch request."""

    schema_version: int
    run_directory: Path
    normalized_config_path: Path
    cobaya_input_path: Path
    chain_prefix: Path
    status_path: Path
    summary_path: Path
    updated_cobaya_input_path: Path
    worker_log_path: Path
    cobaya_stdout_path: Path
    cobaya_stderr_path: Path
    events_path: Path
    overwrite: bool
    seed: int


@dataclass(frozen=True)
class PreparedRunExecution:
    """Prepared execution artifacts plus the temporary worker request path."""

    run_config: RunConfig
    output_root: Path
    artifacts: RunArtifacts
    request: WorkerRequest
    request_path: Path


def validate_run_config_for_execution(run_config: RunConfig) -> RunConfig:
    """Revalidate a run configuration with the same backend services used by the UI."""

    resolved_config = resolve_run_config(run_config)
    build_background_model(resolved_config)
    for dataset in resolved_config.datasets:
        if isinstance(dataset, CosmicChronometerDatasetConfig):
            build_cosmic_chronometers_likelihood(dataset)
    return resolved_config


def prepare_worker_request(
    run_config: RunConfig,
    *,
    materialize_run_directory: bool = True,
) -> PreparedRunExecution:
    """Prepare a managed run directory and a temporary worker request file."""

    validated_config = validate_run_config_for_execution(run_config)
    output_root = validated_config.runtime.output_directory.resolve()
    effective_config = (
        _materialize_managed_run_directory(validated_config)
        if materialize_run_directory
        else validated_config
    )
    artifacts = prepare_run_artifacts(effective_config)
    cobaya_input = build_cobaya_input(effective_config)

    write_input_yaml(artifacts, effective_config)
    write_normalized_config(artifacts, effective_config)
    write_cobaya_input(artifacts, cobaya_input.info)
    write_metadata(artifacts, effective_config)
    write_status(
        artifacts,
        state="pending",
        extra={
            "output_root": str(output_root),
            "run_label": effective_config.runtime.run_label,
            "sampled_parameters": list(cobaya_input.sampled_symbols),
            "datasets": [dataset.kind for dataset in effective_config.datasets],
        },
    )

    request = WorkerRequest(
        schema_version=WORKER_REQUEST_SCHEMA_VERSION,
        run_directory=artifacts.run_directory,
        normalized_config_path=artifacts.normalized_config_path,
        cobaya_input_path=artifacts.cobaya_input_path,
        chain_prefix=artifacts.chain_prefix,
        status_path=artifacts.status_path,
        summary_path=artifacts.summary_path,
        updated_cobaya_input_path=artifacts.updated_cobaya_input_path,
        worker_log_path=artifacts.worker_log_path,
        cobaya_stdout_path=artifacts.cobaya_stdout_path,
        cobaya_stderr_path=artifacts.cobaya_stderr_path,
        events_path=artifacts.events_path,
        overwrite=effective_config.runtime.overwrite,
        seed=effective_config.sampler.seed,
    )
    request_path = _write_request_file(request)
    return PreparedRunExecution(
        run_config=effective_config,
        output_root=output_root,
        artifacts=artifacts,
        request=request,
        request_path=request_path,
    )


def load_worker_request(path: Path) -> WorkerRequest:
    """Load and validate a worker request from JSON."""

    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    if payload.get("schema_version") != WORKER_REQUEST_SCHEMA_VERSION:
        raise ValueError("Unsupported worker request schema version.")

    return WorkerRequest(
        schema_version=int(payload["schema_version"]),
        run_directory=Path(payload["run_directory"]).resolve(),
        normalized_config_path=Path(payload["normalized_config_path"]).resolve(),
        cobaya_input_path=Path(payload["cobaya_input_path"]).resolve(),
        chain_prefix=Path(payload["chain_prefix"]).resolve(),
        status_path=Path(payload["status_path"]).resolve(),
        summary_path=Path(payload["summary_path"]).resolve(),
        updated_cobaya_input_path=Path(payload["updated_cobaya_input_path"]).resolve(),
        worker_log_path=Path(payload["worker_log_path"]).resolve(),
        cobaya_stdout_path=Path(payload["cobaya_stdout_path"]).resolve(),
        cobaya_stderr_path=Path(payload["cobaya_stderr_path"]).resolve(),
        events_path=Path(payload["events_path"]).resolve(),
        overwrite=bool(payload["overwrite"]),
        seed=int(payload["seed"]),
    )


def cleanup_worker_request(path: Path) -> None:
    """Remove a temporary worker request file if it still exists."""

    try:
        path.unlink(missing_ok=True)
    except OSError:
        return


def _materialize_managed_run_directory(run_config: RunConfig) -> RunConfig:
    output_root = run_config.runtime.output_directory.resolve()
    run_directory = output_root / _default_run_directory_name(
        run_config.runtime.run_label
    )
    return replace(
        run_config,
        runtime=replace(run_config.runtime, output_directory=run_directory),
    )


def _default_run_directory_name(run_label: str) -> str:
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_label = re.sub(r"[^A-Za-z0-9._-]+", "-", run_label.strip()).strip("-")
    return f"{safe_label or 'run'}-{timestamp}"


def _write_request_file(request: WorkerRequest) -> Path:
    descriptor, raw_path = tempfile.mkstemp(
        prefix="cosmofit-run-request-",
        suffix=".json",
    )
    path = Path(raw_path)
    try:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(_serialize_request(request), handle, indent=2, sort_keys=True)
            handle.write("\n")
    finally:
        os.close(descriptor)
    return path


def _serialize_request(request: WorkerRequest) -> dict[str, object]:
    return {
        "schema_version": request.schema_version,
        "run_directory": str(request.run_directory),
        "normalized_config_path": str(request.normalized_config_path),
        "cobaya_input_path": str(request.cobaya_input_path),
        "chain_prefix": str(request.chain_prefix),
        "status_path": str(request.status_path),
        "summary_path": str(request.summary_path),
        "updated_cobaya_input_path": str(request.updated_cobaya_input_path),
        "worker_log_path": str(request.worker_log_path),
        "cobaya_stdout_path": str(request.cobaya_stdout_path),
        "cobaya_stderr_path": str(request.cobaya_stderr_path),
        "events_path": str(request.events_path),
        "overwrite": request.overwrite,
        "seed": request.seed,
    }
