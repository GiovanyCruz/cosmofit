"""Optional real smoke test for the Results controller with a completed run."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from cosmofit.application import PosteriorPlotRequest, PosteriorResultsLoadOptions
from cosmofit.cobaya_engine.smoke_run import main as cobaya_smoke_main
from cosmofit.ui.results_controller import ResultsController


@pytest.mark.skipif(
    os.environ.get("COSMOFIT_RUN_RESULTS_SMOKE") != "1",
    reason="Set COSMOFIT_RUN_RESULTS_SMOKE=1 to run the real results smoke test.",
)
def test_results_controller_real_completed_run_smoke(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    output_root = tmp_path / "results-smoke"
    assert cobaya_smoke_main(["--output-root", str(output_root)]) == 0
    run_directory = next(path for path in output_root.iterdir() if path.is_dir())

    controller = ResultsController()
    loaded_payloads: list[object] = []
    plots: list[object] = []
    exports: list[object] = []
    controller.results_loaded.connect(loaded_payloads.append)
    controller.plot_ready.connect(plots.append)
    controller.summary_exported.connect(exports.append)

    assert controller.load_run(run_directory, PosteriorResultsLoadOptions()) is True
    _spin_until(
        lambda: len(loaded_payloads) == 1 and controller.is_busy() is False,
        app,
    )

    assert controller.export_summary("json", tmp_path / "summary.json") is True
    _spin_until(lambda: len(exports) == 1 and controller.is_busy() is False, app)
    assert controller.export_summary("csv", tmp_path / "summary.csv") is True
    _spin_until(lambda: len(exports) == 2 and controller.is_busy() is False, app)

    assert controller.generate_plot(
        PosteriorPlotRequest(
            kind="1d",
            parameters=("H0",),
            confidence_levels=(0.68, 0.95),
        )
    )
    _spin_until(lambda: len(plots) == 1 and controller.is_busy() is False, app)

    loaded = controller.loaded_results()
    assert loaded is not None
    if len(loaded.run_analysis.selectable_parameters) >= 2:
        assert controller.generate_plot(
            PosteriorPlotRequest(
                kind="2d",
                parameters=loaded.run_analysis.selectable_parameters[:2],
                confidence_levels=(0.68, 0.95),
            )
        )
        _spin_until(lambda: len(plots) == 2 and controller.is_busy() is False, app)
        assert controller.generate_plot(
            PosteriorPlotRequest(
                kind="triangle",
                parameters=loaded.run_analysis.selectable_parameters[:2],
                confidence_levels=(0.68, 0.95),
            )
        )
        _spin_until(lambda: len(plots) == 3 and controller.is_busy() is False, app)

    assert controller.export_current_plot(tmp_path / "posterior.png") is True
    _spin_until(lambda: (tmp_path / "posterior.png").is_file(), app)
    assert controller.export_current_plot(tmp_path / "posterior.pdf") is True
    _spin_until(lambda: (tmp_path / "posterior.pdf").is_file(), app)

    assert (tmp_path / "summary.json").is_file()
    assert (tmp_path / "summary.csv").is_file()
    assert (tmp_path / "posterior.png").stat().st_size > 0
    assert (tmp_path / "posterior.pdf").stat().st_size > 0
    controller.shutdown()


def _spin_until(predicate, app: QApplication, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for the real results smoke test.")
