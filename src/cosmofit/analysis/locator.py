"""Run-directory validation and Cobaya chain-root location."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from cosmofit.analysis.errors import (
    MalformedRunDirectoryError,
    MultipleChainRootsError,
    RunNotSuccessfulError,
)
from cosmofit.application.config_models import RunConfig, deserialize_run_config

_MANAGED_CHAIN_PREFIX = "chain"


@dataclass(frozen=True)
class LocatedRunResult:
    """Validated run-directory artifacts needed by the analysis layer."""

    run_directory: Path
    chain_root: Path
    chain_files: tuple[Path, ...]
    normalized_config: RunConfig
    status: dict[str, Any]
    summary: dict[str, Any]
    metadata: dict[str, Any]
    updated_info: dict[str, Any]
    checkpoint: dict[str, Any] | None


def locate_run_result(run_directory: Path) -> LocatedRunResult:
    """Validate a completed run directory and return its managed chain root."""

    resolved_run_directory = run_directory.resolve()
    if not resolved_run_directory.is_dir():
        raise MalformedRunDirectoryError(
            (
                f"Run directory '{resolved_run_directory}' does not exist or is not "
                "a directory."
            ),
            run_directory=resolved_run_directory,
        )

    status = _load_json(resolved_run_directory / "status.json")
    state = status.get("state")
    if state != "succeeded":
        raise RunNotSuccessfulError(
            (
                f"Run directory '{resolved_run_directory}' has status "
                f"state={state!r}, expected 'succeeded'."
            ),
            run_directory=resolved_run_directory,
        )

    normalized_config = deserialize_run_config(
        _load_json(resolved_run_directory / "normalized_config.json")
    )
    summary = _load_json(resolved_run_directory / "summary.json")
    metadata = _load_json(resolved_run_directory / "metadata.json")

    chains_directory = resolved_run_directory / "chains"
    if not chains_directory.is_dir():
        raise MalformedRunDirectoryError(
            (
                f"Run directory '{resolved_run_directory}' is missing the chains "
                "directory."
            ),
            run_directory=resolved_run_directory,
        )

    discovered_roots = _discover_chain_roots(chains_directory)
    managed_root = chains_directory / _MANAGED_CHAIN_PREFIX
    managed_updated_info_path = managed_root.with_suffix(".updated.yaml")
    managed_chain_files = tuple(
        sorted(chains_directory.glob(f"{managed_root.name}.[0-9]*.txt"))
    )
    if len(discovered_roots) > 1:
        discovered = ", ".join(str(root.name) for root in discovered_roots)
        raise MultipleChainRootsError(
            (
                f"Run directory '{resolved_run_directory}' contains multiple chain "
                f"roots: {discovered}."
            ),
            run_directory=resolved_run_directory,
        )
    if managed_updated_info_path.is_file() and not managed_chain_files:
        raise MalformedRunDirectoryError(
            (
                f"Run directory '{resolved_run_directory}' has no chain text files "
                f"for root '{managed_root.name}'."
            ),
            run_directory=resolved_run_directory,
        )
    if not discovered_roots:
        raise MalformedRunDirectoryError(
            (
                f"Run directory '{resolved_run_directory}' does not contain a valid "
                f"Cobaya chain root under '{chains_directory}'."
            ),
            run_directory=resolved_run_directory,
        )
    if managed_root not in discovered_roots:
        found_root = discovered_roots[0]
        raise MalformedRunDirectoryError(
            (
                f"Run directory '{resolved_run_directory}' is missing the managed "
                f"chain root '{managed_root.name}' and instead contains "
                f"'{found_root.name}'."
            ),
            run_directory=resolved_run_directory,
        )

    updated_info = _load_yaml(managed_updated_info_path)
    checkpoint_path = managed_root.with_suffix(".checkpoint")
    checkpoint = _load_yaml(checkpoint_path) if checkpoint_path.is_file() else None

    chain_files = managed_chain_files

    return LocatedRunResult(
        run_directory=resolved_run_directory,
        chain_root=managed_root,
        chain_files=chain_files,
        normalized_config=normalized_config,
        status=status,
        summary=summary,
        metadata=metadata,
        updated_info=updated_info,
        checkpoint=checkpoint,
    )


def _discover_chain_roots(chains_directory: Path) -> list[Path]:
    candidates: list[Path] = []
    for updated_path in sorted(chains_directory.glob("*.updated.yaml")):
        prefix = updated_path.name[: -len(".updated.yaml")]
        if not prefix:
            continue
        chain_files = list(chains_directory.glob(f"{prefix}.[0-9]*.txt"))
        if chain_files:
            candidates.append(chains_directory / prefix)
    return candidates


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise MalformedRunDirectoryError(f"Missing required file '{path}'.")
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        raise MalformedRunDirectoryError(
            f"Could not read JSON file '{path}': {exc}."
        ) from exc
    if not isinstance(payload, dict):
        raise MalformedRunDirectoryError(f"JSON file '{path}' must contain an object.")
    return payload


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise MalformedRunDirectoryError(f"Missing required file '{path}'.")
    try:
        with path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
    except (yaml.YAMLError, OSError) as exc:
        raise MalformedRunDirectoryError(
            f"Could not read YAML file '{path}': {exc}."
        ) from exc
    if not isinstance(payload, dict):
        raise MalformedRunDirectoryError(f"YAML file '{path}' must contain a mapping.")
    return payload
