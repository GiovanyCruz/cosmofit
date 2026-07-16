"""Headless tests for the asynchronous results controller."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject, Slot
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from cosmofit.analysis.errors import InvalidMathTextError
from cosmofit.analysis.models import (
    AnalysisSettings,
    AnalysisSummary,
    ChainDiagnostics,
    CredibleInterval,
    FixedParameterValue,
    PosteriorParameterMetadata,
    PosteriorParameterSummary,
    RunAnalysis,
)
from cosmofit.application import (
    LoadedPosteriorResults,
    PosteriorPlotArtifact,
    PosteriorPlotRequest,
    PosteriorResultsLoadOptions,
    SummaryExportArtifact,
)
from cosmofit.ui.results_controller import STATE_READY, ResultsController

pytestmark = pytest.mark.skipif(
    os.environ.get("COSMOFIT_RUN_RESULTS_CONTROLLER_TESTS") != "1",
    reason=(
        "Set COSMOFIT_RUN_RESULTS_CONTROLLER_TESTS=1 to run threaded "
        "controller tests."
    ),
)


def test_results_controller_ignores_stale_load_result(
    tmp_path: Path,
    controller_harness: _ControllerHarness,
) -> None:
    app = QApplication.instance() or QApplication([])
    controller = controller_harness.create(
        service_factory=lambda: FakePosteriorResultsService(
            tmp_path,
            load_delay_seconds=0.03,
        ),
    )
    loaded_runs: list[LoadedPosteriorResults] = []
    controller.results_loaded.connect(loaded_runs.append)

    first_run = tmp_path / "run-a"
    second_run = tmp_path / "run-b"
    options = PosteriorResultsLoadOptions()

    assert controller.load_run(first_run, options) is True
    assert controller.load_run(second_run, options) is True

    _spin_until(
        lambda: len(loaded_runs) == 1 and controller.is_busy() is False,
        app,
    )

    assert loaded_runs[0].run_analysis.run_directory == second_run.resolve()
    assert controller.wait_for_idle()


def test_results_controller_generates_plot_and_exports_summary(
    tmp_path: Path,
    controller_harness: _ControllerHarness,
) -> None:
    app = QApplication.instance() or QApplication([])
    controller = controller_harness.create(
        service_factory=lambda: FakePosteriorResultsService(tmp_path)
    )
    plots: list[PosteriorPlotArtifact] = []
    exports: list[SummaryExportArtifact] = []
    controller.plot_ready.connect(plots.append)
    controller.summary_exported.connect(exports.append)

    run_directory = tmp_path / "completed-run"
    assert controller.load_run(run_directory, PosteriorResultsLoadOptions()) is True
    _spin_until(
        lambda: controller.loaded_results() is not None
        and controller.state() == STATE_READY
        and controller.is_busy() is False,
        app,
    )

    assert controller.generate_plot(
        PosteriorPlotRequest(
            kind="2d",
            parameters=("H0", "Om"),
            confidence_levels=(0.68, 0.95),
            title="Posterior 2D",
        )
    )
    _spin_until(lambda: len(plots) == 1 and controller.is_busy() is False, app)

    assert plots[0].export.png_path.is_file()
    assert controller.export_summary("json", tmp_path / "summary.json") is True
    _spin_until(lambda: len(exports) == 1 and controller.is_busy() is False, app)

    assert exports[0].output_path == (tmp_path / "summary.json").resolve()
    assert controller.wait_for_idle()


def test_results_controller_rejects_plot_without_loaded_run(
    tmp_path: Path,
    controller_harness: _ControllerHarness,
) -> None:
    app = QApplication.instance() or QApplication([])
    controller = controller_harness.create(
        service_factory=lambda: FakePosteriorResultsService(tmp_path)
    )
    rejections: list[str] = []
    controller.request_rejected.connect(rejections.append)

    assert controller.generate_plot(
        PosteriorPlotRequest(
            kind="1d",
            parameters=("H0",),
            confidence_levels=(0.68, 0.95),
        )
    ) is False

    app.processEvents()
    assert rejections == ["Load a run before generating plots."]
    assert controller.wait_for_idle()


def test_results_controller_reports_invalid_mathtext_cleanly(
    tmp_path: Path,
    controller_harness: _ControllerHarness,
) -> None:
    app = QApplication.instance() or QApplication([])
    controller = controller_harness.create(
        service_factory=lambda: InvalidMathTextPosteriorResultsService(tmp_path)
    )
    failures: list[tuple[str, str]] = []
    controller.failed.connect(
        lambda summary, details: failures.append((summary, details))
    )

    assert controller.load_run(
        tmp_path / "completed-run",
        PosteriorResultsLoadOptions(),
    )
    _spin_until(
        lambda: controller.loaded_results() is not None and not controller.is_busy(),
        app,
    )

    assert controller.generate_plot(
        PosteriorPlotRequest(
            kind="1d",
            parameters=("H0",),
            confidence_levels=(0.68, 0.95),
            title=r"$H_0",
        )
    )
    _spin_until(lambda: len(failures) == 1 and not controller.is_busy(), app)

    assert "invalid Matplotlib MathText".lower() in failures[0][0].lower()
    assert "Expected end of text" in failures[0][1]
    assert controller.wait_for_idle()


def test_results_controller_shutdown_drains_stale_load_before_next_task(
    tmp_path: Path,
    controller_harness: _ControllerHarness,
) -> None:
    app = QApplication.instance() or QApplication([])
    controller = controller_harness.create(
        service_factory=lambda: FakePosteriorResultsService(
            tmp_path,
            load_delay_seconds=0.03,
        )
    )

    first_run = tmp_path / "run-a"
    second_run = tmp_path / "run-b"
    options = PosteriorResultsLoadOptions()

    assert controller.load_run(first_run, options) is True
    assert controller.load_run(second_run, options) is True
    _spin_until(
        lambda: (
            controller.loaded_results() is not None
            and controller.is_busy() is False
        ),
        app,
    )

    assert controller.generate_plot(
        PosteriorPlotRequest(
            kind="1d",
            parameters=("H0",),
            confidence_levels=(0.68, 0.95),
        )
    ) is True
    _spin_until(
        lambda: controller.current_plot() is not None and not controller.is_busy(),
        app,
    )

    current_plot = controller.current_plot()
    assert current_plot is not None
    assert current_plot.export.png_path.is_file()
    assert controller.wait_for_idle()


def test_results_controller_shutdown_prevents_late_callbacks(
    tmp_path: Path,
    controller_harness: _ControllerHarness,
) -> None:
    app = QApplication.instance() or QApplication([])
    controller = controller_harness.create(
        service_factory=lambda: FakePosteriorResultsService(
            tmp_path,
            load_delay_seconds=0.05,
        )
    )
    loaded_runs: list[LoadedPosteriorResults] = []
    states: list[str] = []
    controller.results_loaded.connect(loaded_runs.append)
    controller.state_changed.connect(lambda state, _message: states.append(state))

    assert (
        controller.load_run(tmp_path / "run-a", PosteriorResultsLoadOptions())
        is True
    )
    controller.shutdown()

    app.processEvents()
    assert loaded_runs == []
    assert controller.is_busy() is False
    assert controller.loaded_results() is None
    assert states.count(STATE_READY) == 0


def test_results_controller_can_be_destroyed_after_stale_task_completion(
    tmp_path: Path,
    controller_harness: _ControllerHarness,
) -> None:
    app = QApplication.instance() or QApplication([])
    controller = controller_harness.create(
        service_factory=lambda: FakePosteriorResultsService(
            tmp_path,
            load_delay_seconds=0.03,
        )
    )
    destroyed = _DestroyedProbe()
    controller.destroyed.connect(destroyed.mark_destroyed)

    assert (
        controller.load_run(tmp_path / "run-a", PosteriorResultsLoadOptions())
        is True
    )
    assert (
        controller.load_run(tmp_path / "run-b", PosteriorResultsLoadOptions())
        is True
    )
    _spin_until(lambda: controller.is_busy() is False, app)

    controller.shutdown()
    assert controller.is_busy() is False
    assert controller._active_task is None
    assert controller._pending_completion is None
    assert controller._queued_load is None
    assert controller.loaded_results() is None
    assert controller.current_plot() is None
    controller_harness.forget(controller)
    controller.deleteLater()
    _spin_until(lambda: destroyed.destroyed is True, app)
    assert destroyed.destroyed is True


def test_results_controller_repeated_construction_and_shutdown(
    tmp_path: Path,
    controller_harness: _ControllerHarness,
) -> None:
    app = QApplication.instance() or QApplication([])

    for index in range(10):
        root = tmp_path / f"iteration-{index}"
        controller = controller_harness.create(
            service_factory=lambda root=root: FakePosteriorResultsService(root)
        )
        assert controller.load_run(
            root / "run",
            PosteriorResultsLoadOptions(),
        ) is True
        _spin_until(
            lambda controller=controller: (
                controller.loaded_results() is not None and not controller.is_busy()
            ),
            app,
        )
        controller.shutdown()
        assert controller.wait_for_idle()
        controller_harness.forget(controller)


def test_results_controller_stress_stale_load_then_plot(
    tmp_path: Path,
    controller_harness: _ControllerHarness,
) -> None:
    app = QApplication.instance() or QApplication([])

    for index in range(20):
        root = tmp_path / f"stress-{index}"
        controller = controller_harness.create(
            service_factory=lambda root=root: FakePosteriorResultsService(
                root,
                load_delay_seconds=0.01,
            )
        )
        first_run = root / "run-a"
        second_run = root / "run-b"
        options = PosteriorResultsLoadOptions()

        assert controller.load_run(first_run, options) is True
        assert controller.load_run(second_run, options) is True
        _spin_until(
            lambda controller=controller: (
                controller.loaded_results() is not None and not controller.is_busy()
            ),
            app,
            timeout=5.0,
        )
        assert controller.generate_plot(
            PosteriorPlotRequest(
                kind="2d",
                parameters=("H0", "Om"),
                confidence_levels=(0.68, 0.95),
            )
        ) is True
        _spin_until(
            lambda controller=controller: (
                controller.current_plot() is not None and not controller.is_busy()
            ),
            app,
            timeout=5.0,
        )
        assert controller.current_plot() is not None
        controller.shutdown()
        assert controller.wait_for_idle()
        controller_harness.forget(controller)


def _spin_until(predicate, app: QApplication, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _flush_qt_events(app)
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out while waiting for the results controller.")


def _flush_qt_events(app: QApplication) -> None:
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


class FakePosteriorResultsService:
    """Deterministic posterior-results service stub for UI tests."""

    def __init__(
        self,
        root: Path,
        load_delay_seconds: float = 0.0,
        plot_delay_seconds: float = 0.0,
        export_delay_seconds: float = 0.0,
    ) -> None:
        self._root = root
        self._load_delay_seconds = load_delay_seconds
        self._plot_delay_seconds = plot_delay_seconds
        self._export_delay_seconds = export_delay_seconds
        self._loaded: LoadedPosteriorResults | None = None
        self._current_plot: PosteriorPlotArtifact | None = None

    def clear(self) -> None:
        self._loaded = None
        self._current_plot = None

    def load_run(
        self,
        run_directory: Path,
        *,
        options: PosteriorResultsLoadOptions,
    ) -> LoadedPosteriorResults:
        time.sleep(self._load_delay_seconds)
        resolved = Path(run_directory)
        analysis_directory = self._root / resolved.name / "analysis"
        analysis_directory.mkdir(parents=True, exist_ok=True)
        loaded = LoadedPosteriorResults(
            run_analysis=_build_run_analysis(resolved, analysis_directory, options),
            summary=_build_summary(resolved, analysis_directory, options),
        )
        self._loaded = loaded
        return loaded

    def refresh_summary(
        self,
        confidence_levels: tuple[float, ...],
    ) -> LoadedPosteriorResults:
        assert self._loaded is not None
        loaded = LoadedPosteriorResults(
            run_analysis=self._loaded.run_analysis,
            summary=_build_summary(
                self._loaded.run_analysis.run_directory,
                self._loaded.run_analysis.analysis_directory,
                PosteriorResultsLoadOptions(
                    ignore_rows=self._loaded.summary.settings.ignore_rows,
                    confidence_levels=confidence_levels,
                    filled_contours=self._loaded.summary.settings.filled_contours,
                ),
            ),
        )
        self._loaded = loaded
        return loaded

    def generate_plot(self, request: PosteriorPlotRequest) -> PosteriorPlotArtifact:
        assert self._loaded is not None
        time.sleep(self._plot_delay_seconds)
        plot_directory = self._loaded.run_analysis.analysis_directory / "plots"
        plot_directory.mkdir(parents=True, exist_ok=True)
        stem = request.kind + "_" + "_".join(request.parameters)
        png_path = plot_directory / f"{stem}.png"
        pdf_path = plot_directory / f"{stem}.pdf"
        _write_test_png(png_path)
        pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
        plot = PosteriorPlotArtifact(
            kind=request.kind,
            parameters=request.parameters,
            confidence_levels=request.confidence_levels,
            ignore_rows=self._loaded.summary.settings.ignore_rows,
            title=request.title,
            legend_label=request.legend_label,
            export=type("Export", (), {"png_path": png_path, "pdf_path": pdf_path})(),
        )
        self._current_plot = plot
        return plot

    def export_summary_json(self, output_path: Path) -> SummaryExportArtifact:
        time.sleep(self._export_delay_seconds)
        output = output_path.resolve()
        output.write_text('{"status":"ok"}\n', encoding="utf-8")
        assert self._loaded is not None
        return SummaryExportArtifact(
            format="json",
            output_path=output,
            confidence_levels=self._loaded.summary.settings.confidence_levels,
            ignore_rows=self._loaded.summary.settings.ignore_rows,
        )

    def export_summary_csv(self, output_path: Path) -> SummaryExportArtifact:
        time.sleep(self._export_delay_seconds)
        output = output_path.resolve()
        output.write_text("parameter,mean\nH0,70.1\n", encoding="utf-8")
        assert self._loaded is not None
        return SummaryExportArtifact(
            format="csv",
            output_path=output,
            confidence_levels=self._loaded.summary.settings.confidence_levels,
            ignore_rows=self._loaded.summary.settings.ignore_rows,
        )

    def export_current_plot(self, output_path: Path) -> Path:
        assert self._current_plot is not None
        time.sleep(self._export_delay_seconds)
        output = output_path.resolve()
        source = (
            self._current_plot.export.png_path
            if output.suffix == ".png"
            else self._current_plot.export.pdf_path
        )
        output.write_bytes(source.read_bytes())
        return output


class InvalidMathTextPosteriorResultsService(FakePosteriorResultsService):
    def generate_plot(self, request: PosteriorPlotRequest) -> PosteriorPlotArtifact:
        raise InvalidMathTextError(
            field_name="plot title",
            details="Expected end of text, found '$'  (at char 0)",
        )


def _build_run_analysis(
    run_directory: Path,
    analysis_directory: Path,
    options: PosteriorResultsLoadOptions,
) -> RunAnalysis:
    return RunAnalysis(
        run_directory=run_directory,
        run_label="ui-test-run",
        datasets=("cosmic_chronometers", "pantheon_plus"),
        chain_root=run_directory / "chains" / "chain",
        analysis_directory=analysis_directory,
        settings=AnalysisSettings(
            ignore_rows=options.ignore_rows,
            confidence_levels=options.confidence_levels,
            filled_contours=options.filled_contours,
        ),
        selectable_parameters=("H0", "Om", "w0"),
        parameter_metadata=(
            PosteriorParameterMetadata(
                symbol="H0",
                latex_label="H_0",
                kind="sampled",
                display_name="H0",
                unit="km/s/Mpc",
            ),
            PosteriorParameterMetadata(
                symbol="Om",
                latex_label="\\Omega_m",
                kind="sampled",
                display_name="Om",
                unit=None,
            ),
            PosteriorParameterMetadata(
                symbol="w0",
                latex_label="w_0",
                kind="derived",
                display_name="w0",
                unit=None,
            ),
        ),
        fixed_parameters=(
            FixedParameterValue(
                symbol="Ob",
                display_name="Ob",
                unit=None,
                value=0.049,
            ),
        ),
        diagnostics=_build_diagnostics(run_directory),
    )


def _build_summary(
    run_directory: Path,
    analysis_directory: Path,
    options: PosteriorResultsLoadOptions,
) -> AnalysisSummary:
    return AnalysisSummary(
        run_directory=run_directory,
        chain_root=run_directory / "chains" / "chain",
        analysis_directory=analysis_directory,
        settings=AnalysisSettings(
            ignore_rows=options.ignore_rows,
            confidence_levels=options.confidence_levels,
            filled_contours=options.filled_contours,
        ),
        sampled_parameters=(
            _parameter_summary("H0", 70.1, 1.2, (68.4, 71.5), (67.8, 72.0)),
            _parameter_summary("Om", 0.301, 0.021, (0.28, 0.32), (0.26, 0.34)),
        ),
        fixed_parameters=(
            FixedParameterValue(
                symbol="Ob",
                display_name="Ob",
                unit=None,
                value=0.049,
            ),
        ),
        diagnostics=_build_diagnostics(run_directory),
    )


def _build_diagnostics(run_directory: Path) -> ChainDiagnostics:
    return ChainDiagnostics(
        sample_rows=240,
        chain_count=2,
        total_weight=320.0,
        ignore_rows=0.0,
        chain_root=run_directory / "chains" / "chain",
        chain_files=(run_directory / "chains" / "chain.1.txt",),
        checkpoint_path=run_directory / "chains" / "chain.checkpoint",
        converged=True,
        rminus1_last=0.01,
        checkpoint_burn_in=0.0,
        progress_rows=240,
        maximum_posterior_minuslogpost=1.2,
    )


def _parameter_summary(
    symbol: str,
    mean: float,
    stddev: float,
    interval_68: tuple[float, float],
    interval_95: tuple[float, float],
) -> PosteriorParameterSummary:
    return PosteriorParameterSummary(
        symbol=symbol,
        display_name=symbol,
        latex_label=symbol,
        kind="sampled",
        unit=None,
        mean=mean,
        standard_deviation=stddev,
        median=mean,
        maximum_posterior=mean,
        credible_intervals=(
            CredibleInterval(0.68, interval_68[0], interval_68[1], "two tail"),
            CredibleInterval(0.95, interval_95[0], interval_95[1], "two tail"),
        ),
    )


def _write_test_png(path: Path) -> None:
    image = QImage(64, 64, QImage.Format.Format_RGB32)
    image.fill(0x00AA66)
    assert image.save(str(path))


@pytest.fixture
def controller_harness() -> _ControllerHarness:
    app = QApplication.instance() or QApplication([])
    harness = _ControllerHarness(app)
    yield harness
    harness.shutdown_all()


class _ControllerHarness:
    def __init__(self, app: QApplication) -> None:
        self._app = app
        self._controllers: list[ResultsController] = []

    def create(
        self,
        *,
        service_factory,
    ) -> ResultsController:
        controller = ResultsController(service_factory=service_factory)
        self._controllers.append(controller)
        return controller

    def forget(self, controller: ResultsController) -> None:
        if controller in self._controllers:
            self._controllers.remove(controller)

    def shutdown_all(self) -> None:
        for controller in list(self._controllers):
            controller.shutdown()
            assert controller.wait_for_idle()
            _flush_qt_events(self._app)
        self._controllers.clear()


class _DestroyedProbe(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.destroyed = False

    @Slot()
    def mark_destroyed(self) -> None:
        self.destroyed = True
