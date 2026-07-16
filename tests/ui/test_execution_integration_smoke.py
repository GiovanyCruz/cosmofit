"""Optional integration smoke test for the real UI execution controller path."""

from __future__ import annotations

import os
import time
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from cosmofit.application import SamplerConfig, build_lcdm_example_run_config
from cosmofit.ui.execution_controller import STATE_COMPLETED, ExecutionController


@pytest.mark.skipif(
    os.environ.get("COSMOFIT_RUN_UI_SMOKE") != "1",
    reason=(
        "Set COSMOFIT_RUN_UI_SMOKE=1 to run the real UI execution smoke test."
    ),
)
def test_real_execution_controller_smoke_run(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    controller = ExecutionController(cancellation_timeout_ms=1000)
    completions: list[str] = []
    failures: list[str] = []
    controller.completed.connect(completions.append)
    controller.failed.connect(failures.append)

    run_config = build_lcdm_example_run_config(output_directory=tmp_path / "ui-smoke")
    run_config = replace(
        run_config,
        sampler=SamplerConfig(
            kind="cobaya_mcmc",
            seed=run_config.sampler.seed,
            max_samples=40,
            burn_in=0,
            learn_proposal=False,
            Rminus1_stop=5.0,
            Rminus1_cl_stop=5.0,
        ),
    )

    assert controller.start_run(run_config) is True
    _spin_until(lambda: bool(completions) or bool(failures), app, timeout=30.0)

    assert failures == []
    assert controller.execution_state().state == STATE_COMPLETED
    run_directory = Path(completions[0])
    assert run_directory.is_dir()
    assert (run_directory / "status.json").is_file()
    assert (run_directory / "summary.json").is_file()
    assert (run_directory / "chains" / "chain.updated.yaml").is_file()


def _spin_until(condition, app: QApplication, timeout: float) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for the real execution smoke run.")
