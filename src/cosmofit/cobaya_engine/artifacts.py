"""Run-directory and artifact helpers for Cobaya execution."""

from __future__ import annotations

import json
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cobaya
import numpy as np
import yaml
from cobaya.likelihoods.base_classes.sn import SN
from cobaya.tools import resolve_packages_path

import cosmofit
from cosmofit.application import RunConfig, SupernovaDatasetConfig, serialize_run_config


@dataclass(frozen=True)
class RunArtifacts:
    """Filesystem layout for one isolated Cobaya run."""

    run_directory: Path
    logs_directory: Path
    chains_directory: Path
    input_yaml_path: Path
    normalized_config_path: Path
    cobaya_input_path: Path
    updated_cobaya_input_path: Path
    summary_path: Path
    status_path: Path
    metadata_path: Path
    worker_log_path: Path
    cobaya_stdout_path: Path
    cobaya_stderr_path: Path
    events_path: Path
    chain_prefix: Path


def prepare_run_artifacts(run_config: RunConfig) -> RunArtifacts:
    """Create the artifact directory tree for a validated run."""

    run_directory = run_config.runtime.output_directory
    if run_directory.exists() and not run_config.runtime.overwrite:
        raise FileExistsError(
            f"Refusing to overwrite existing run directory '{run_directory}'."
        )
    if run_directory.exists() and not run_directory.is_dir():
        raise FileExistsError(
            f"Run path '{run_directory}' exists and is not a directory."
        )

    logs_directory = run_directory / "logs"
    chains_directory = run_directory / "chains"
    logs_directory.mkdir(parents=True, exist_ok=run_config.runtime.overwrite)
    chains_directory.mkdir(parents=True, exist_ok=run_config.runtime.overwrite)

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
        events_path=logs_directory / "events.jsonl",
        chain_prefix=chains_directory / "chain",
    )


def write_input_yaml(artifacts: RunArtifacts, run_config: RunConfig) -> None:
    """Persist the normalized run configuration as user-facing YAML."""

    with artifacts.input_yaml_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(serialize_run_config(run_config), handle, sort_keys=False)


def write_normalized_config(artifacts: RunArtifacts, run_config: RunConfig) -> None:
    """Persist the resolved run configuration as JSON."""

    with artifacts.normalized_config_path.open("w", encoding="utf-8") as handle:
        json.dump(serialize_run_config(run_config), handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_cobaya_input(artifacts: RunArtifacts, cobaya_input: dict[str, Any]) -> None:
    """Persist the exact Cobaya input dictionary that will be executed."""

    with artifacts.cobaya_input_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(cobaya_input, handle, sort_keys=False)


def write_status(
    artifacts: RunArtifacts,
    *,
    state: str,
    message: str | None = None,
    exit_code: int | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Persist machine-readable run status."""

    payload: dict[str, Any] = {
        "state": state,
        "run_directory": str(artifacts.run_directory),
        "message": message,
        "exit_code": exit_code,
    }
    if extra:
        payload.update(extra)
    _write_json_atomic(artifacts.status_path, payload)


def write_updated_cobaya_input(
    artifacts: RunArtifacts,
    updated_cobaya_input: dict[str, Any],
) -> None:
    """Persist the Cobaya-resolved input dictionary returned by the worker run."""

    with artifacts.updated_cobaya_input_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(
            _serialize_yaml_value(updated_cobaya_input),
            handle,
            sort_keys=False,
        )


def write_metadata(artifacts: RunArtifacts, run_config: RunConfig) -> None:
    """Persist environment metadata needed for debugging and reproducibility."""

    packages_path = resolve_packages_path()
    payload = {
        "cobaya_version": getattr(cobaya, "__version__", "unknown"),
        "cobaya_packages_path": packages_path,
        "cosmofit_version": getattr(cosmofit, "__version__", "0.1.0"),
        "numpy_version": np.__version__,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }
    supernova_datasets = [
        dataset.kind
        for dataset in run_config.datasets
        if isinstance(dataset, SupernovaDatasetConfig)
    ]
    if supernova_datasets:
        payload["supernova_components"] = supernova_datasets
    if supernova_datasets and packages_path:
        sn_data_path = SN.get_path(packages_path)
        payload["sn_data_path"] = sn_data_path
        version_path = Path(sn_data_path) / "version.dat"
        if version_path.is_file():
            payload["sn_data_version"] = version_path.read_text(
                encoding="utf-8"
            ).strip()
    with artifacts.metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_json_artifact(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON artifact atomically."""

    _write_json_atomic(path, payload)


def list_chain_files(artifacts: RunArtifacts) -> list[str]:
    """Return the chain files produced under the chain output directory."""

    return sorted(
        str(path.relative_to(artifacts.run_directory))
        for path in artifacts.chains_directory.glob("*")
        if path.is_file()
    )


def _serialize_yaml_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {key: _serialize_yaml_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_yaml_value(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize_yaml_value(item) for item in value]
    return value


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    temporary_path.replace(path)
