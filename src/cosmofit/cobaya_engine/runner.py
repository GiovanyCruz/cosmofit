"""Parent-process orchestration for Cobaya worker subprocesses."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

from cosmofit.application import RunConfig, resolve_run_config
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


@dataclass(frozen=True)
class RunResult:
    """High-level result for one Cobaya worker execution."""

    artifacts: RunArtifacts
    return_code: int


def run_in_subprocess(run_config: RunConfig) -> RunResult:
    """Prepare artifacts, execute the worker, and return its exit code."""

    resolved_config = resolve_run_config(run_config)
    artifacts = prepare_run_artifacts(resolved_config)
    cobaya_input = build_cobaya_input(resolved_config)

    write_input_yaml(artifacts, resolved_config)
    write_normalized_config(artifacts, resolved_config)
    write_cobaya_input(artifacts, cobaya_input.info)
    write_metadata(artifacts)
    write_status(artifacts, state="pending")

    with (
        artifacts.cobaya_stdout_path.open("w", encoding="utf-8") as stdout_handle,
        artifacts.cobaya_stderr_path.open("w", encoding="utf-8") as stderr_handle,
    ):
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "cosmofit.cobaya_engine.worker",
                str(artifacts.run_directory),
            ],
            check=False,
            stdout=stdout_handle,
            stderr=stderr_handle,
        )

    if process.returncode != 0:
        write_status(
            artifacts,
            state="failed",
            exit_code=process.returncode,
            message="Cobaya worker subprocess failed.",
        )
    return RunResult(artifacts=artifacts, return_code=process.returncode)
