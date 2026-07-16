"""Parent-process orchestration for Cobaya worker subprocesses."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

from cosmofit.application import (
    RunConfig,
    cleanup_worker_request,
    prepare_worker_request,
)
from cosmofit.cobaya_engine.artifacts import RunArtifacts


@dataclass(frozen=True)
class RunResult:
    """High-level result for one Cobaya worker execution."""

    artifacts: RunArtifacts
    return_code: int


def run_in_subprocess(run_config: RunConfig) -> RunResult:
    """Prepare artifacts, execute the worker, and return its exit code."""

    prepared = prepare_worker_request(run_config, materialize_run_directory=False)
    try:
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "cosmofit.application.run_worker",
                str(prepared.request_path),
            ],
            check=False,
        )
    finally:
        cleanup_worker_request(prepared.request_path)
    return RunResult(artifacts=prepared.artifacts, return_code=process.returncode)
