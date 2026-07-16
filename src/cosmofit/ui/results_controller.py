"""Qt-facing controller for completed-run posterior loading and exports."""

from __future__ import annotations

import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal, Slot

from cosmofit.analysis.errors import (
    AnalysisPlotSelectionError,
    InvalidAnalysisSettingError,
    InvalidMathTextError,
    MalformedRunDirectoryError,
    MultipleChainRootsError,
    RunNotSuccessfulError,
)
from cosmofit.application import (
    LoadedPosteriorResults,
    PosteriorPlotArtifact,
    PosteriorPlotRequest,
    PosteriorResultsLoadOptions,
    PosteriorResultsService,
    SummaryExportArtifact,
)

STATE_NO_RUN_LOADED = "No run loaded"
STATE_LOADING = "Loading"
STATE_READY = "Ready"
STATE_PLOTTING = "Plotting"
STATE_EXPORTING = "Exporting"
STATE_FAILED = "Failed"
STATE_CLEARED = "Cleared"


@dataclass(frozen=True)
class LoadRequest:
    """Arguments needed to load one completed run."""

    run_directory: Path
    options: PosteriorResultsLoadOptions


@dataclass(frozen=True)
class _PendingTaskCompletion:
    token: int
    finalize: Callable[[], None]


@dataclass
class _ActiveTask:
    token: int
    success_handler: Callable[[object], Callable[[], None]]
    thread: QThread
    worker: _TaskWorker


class _TaskWorker(QObject):
    succeeded = Signal(int, object)
    failed = Signal(int, object, str)
    finished = Signal(int)

    def __init__(self, token: int, operation: Callable[[], object]) -> None:
        super().__init__()
        self._token = token
        self._operation = operation

    @Slot()
    def run(self) -> None:
        try:
            result = self._operation()
        except Exception as error:  # pragma: no cover - exercised via signal tests
            self.failed.emit(self._token, error, traceback.format_exc())
        else:
            self.succeeded.emit(self._token, result)
        finally:
            self.finished.emit(self._token)


class ResultsController(QObject):
    """Run posterior analysis tasks off the GUI thread and expose state via signals."""

    state_changed = Signal(str, str)
    busy_changed = Signal(bool)
    request_rejected = Signal(str)
    results_loaded = Signal(object)
    summary_refreshed = Signal(object)
    plot_ready = Signal(object)
    summary_exported = Signal(object)
    plot_exported = Signal(str)
    failed = Signal(str, str)
    cleared = Signal()

    def __init__(
        self,
        *,
        service_factory: Callable[[], PosteriorResultsService] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service_factory = service_factory or PosteriorResultsService
        self._service = self._service_factory()
        self._state = STATE_NO_RUN_LOADED
        self._active_task: _ActiveTask | None = None
        self._generation = 0
        self._queued_load: LoadRequest | None = None
        self._current_run_directory: Path | None = None
        self._latest_completed_run: Path | None = None
        self._loaded_results: LoadedPosteriorResults | None = None
        self._current_plot: PosteriorPlotArtifact | None = None
        self._pending_completion: _PendingTaskCompletion | None = None
        self._shutdown_requested = False

    def state(self) -> str:
        return self._state

    def is_busy(self) -> bool:
        return self._active_task is not None

    def latest_completed_run(self) -> Path | None:
        return self._latest_completed_run

    def loaded_results(self) -> LoadedPosteriorResults | None:
        return self._loaded_results

    def current_plot(self) -> PosteriorPlotArtifact | None:
        return self._current_plot

    def set_latest_completed_run(self, run_directory: Path | None) -> None:
        self._latest_completed_run = (
            run_directory.expanduser().resolve() if run_directory else None
        )

    def load_latest_completed_run(self, options: PosteriorResultsLoadOptions) -> bool:
        if self._latest_completed_run is None:
            self.request_rejected.emit("No recent completed run is available.")
            return False
        return self.load_run(self._latest_completed_run, options)

    def load_run(
        self,
        run_directory: Path,
        options: PosteriorResultsLoadOptions,
    ) -> bool:
        if not self._accept_new_tasks():
            return False
        request = LoadRequest(
            run_directory=run_directory.expanduser().resolve(),
            options=options,
        )
        if self.is_busy():
            self._generation += 1
            self._queued_load = request
            self._set_state(STATE_LOADING, "The selected run will be reloaded.")
            return True

        self._generation += 1
        self._queued_load = None
        token = self._generation
        return self._start_task(
            token=token,
            state=STATE_LOADING,
            message="Loading completed run.",
            operation=lambda: self._service.load_run(
                request.run_directory,
                options=request.options,
            ),
            success_handler=self._handle_results_loaded,
        )

    def reload(self, options: PosteriorResultsLoadOptions) -> bool:
        if self._current_run_directory is None:
            self.request_rejected.emit("No run is loaded to reload.")
            return False
        return self.load_run(self._current_run_directory, options)

    def refresh_summary(self, confidence_levels: tuple[float, ...]) -> bool:
        if not self._accept_new_tasks():
            return False
        if self._loaded_results is None:
            self.request_rejected.emit("Load a run before refreshing the summary.")
            return False
        if self.is_busy():
            self.request_rejected.emit("Wait for the current operation to finish.")
            return False
        self._generation += 1
        token = self._generation
        return self._start_task(
            token=token,
            state=STATE_LOADING,
            message="Refreshing posterior summary.",
            operation=lambda: self._service.refresh_summary(confidence_levels),
            success_handler=self._handle_summary_refreshed,
        )

    def generate_plot(self, request: PosteriorPlotRequest) -> bool:
        if not self._accept_new_tasks():
            return False
        if self._loaded_results is None:
            self.request_rejected.emit("Load a run before generating plots.")
            return False
        if self.is_busy():
            self.request_rejected.emit("Wait for the current operation to finish.")
            return False
        self._generation += 1
        token = self._generation
        return self._start_task(
            token=token,
            state=STATE_PLOTTING,
            message="Generating posterior plot.",
            operation=lambda: self._service.generate_plot(request),
            success_handler=self._handle_plot_ready,
        )

    def export_summary(self, export_format: str, output_path: Path) -> bool:
        if not self._accept_new_tasks():
            return False
        if self._loaded_results is None:
            self.request_rejected.emit("Load a run before exporting the summary.")
            return False
        if self.is_busy():
            self.request_rejected.emit("Wait for the current operation to finish.")
            return False
        if export_format not in {"json", "csv"}:
            self.request_rejected.emit("Unsupported export format.")
            return False

        if export_format == "json":

            def operation() -> object:
                return self._service.export_summary_json(output_path)
        else:

            def operation() -> object:
                return self._service.export_summary_csv(output_path)

        self._generation += 1
        token = self._generation
        return self._start_task(
            token=token,
            state=STATE_EXPORTING,
            message=f"Exporting summary {export_format.upper()}.",
            operation=operation,
            success_handler=self._handle_summary_exported,
        )

    def export_current_plot(self, output_path: Path) -> bool:
        if not self._accept_new_tasks():
            return False
        if self._current_plot is None:
            self.request_rejected.emit("Generate a plot before exporting it.")
            return False
        if self.is_busy():
            self.request_rejected.emit("Wait for the current operation to finish.")
            return False
        self._generation += 1
        token = self._generation
        return self._start_task(
            token=token,
            state=STATE_EXPORTING,
            message=f"Exporting plot {output_path.suffix.upper()}.",
            operation=lambda: self._service.export_current_plot(output_path),
            success_handler=self._handle_plot_exported,
        )

    def clear_results(self) -> None:
        self._generation += 1
        self._queued_load = None
        self._pending_completion = None
        self._service.clear()
        self._current_run_directory = None
        self._loaded_results = None
        self._current_plot = None
        self._set_state(STATE_CLEARED, "Results cleared.")
        self.cleared.emit()

    def shutdown(self, timeout_ms: int = 5000) -> None:
        self._shutdown_requested = True
        self._generation += 1
        self._queued_load = None
        self._pending_completion = None
        if not self.wait_for_idle(timeout_ms=timeout_ms):
            raise RuntimeError("ResultsController shutdown timed out.")
        self._service.clear()
        self._current_run_directory = None
        self._loaded_results = None
        self._current_plot = None

    def wait_for_idle(self, timeout_ms: int = 5000) -> bool:
        deadline = time.monotonic() + (timeout_ms / 1000)
        while self._active_task is not None:
            active_task = self._active_task
            assert active_task is not None
            self._process_events()
            if active_task.thread.wait(25):
                self._process_events()
                continue
            if time.monotonic() >= deadline:
                return False
        self._process_events()
        return True

    def _accept_new_tasks(self) -> bool:
        if self._shutdown_requested:
            self.request_rejected.emit("The results analysis is already closed.")
            return False
        return True

    def _start_task(
        self,
        *,
        token: int,
        state: str,
        message: str,
        operation: Callable[[], object],
        success_handler: Callable[[object], Callable[[], None]],
    ) -> bool:
        thread = QThread()
        worker = _TaskWorker(token, operation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._dispatch_success)
        worker.failed.connect(self._dispatch_failure)
        worker.finished.connect(thread.quit)
        worker.finished.connect(self._handle_task_finished)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._handle_thread_finished)

        self._active_task = _ActiveTask(
            token=token,
            success_handler=success_handler,
            thread=thread,
            worker=worker,
        )
        self._set_state(state, message)
        thread.start()
        return True

    @Slot(int, object)
    def _dispatch_success(self, token: int, payload: object) -> None:
        if self._shutdown_requested or token != self._generation:
            return
        active_task = self._active_task
        if active_task is None or active_task.token != token:
            return
        finalize = active_task.success_handler(payload)
        self._pending_completion = _PendingTaskCompletion(
            token=token,
            finalize=finalize,
        )

    @Slot(int, object, str)
    def _dispatch_failure(self, token: int, error: object, details: str) -> None:
        if self._shutdown_requested or token != self._generation:
            return
        active_task = self._active_task
        if active_task is None or active_task.token != token:
            return
        if self._state == STATE_LOADING:
            self._current_run_directory = None
            self._loaded_results = None
            self._current_plot = None
        message = _present_error(error)
        self._pending_completion = _PendingTaskCompletion(
            token=token,
            finalize=lambda: self._finalize_failure(message, details),
        )

    def _handle_results_loaded(self, payload: object) -> Callable[[], None]:
        loaded = payload
        assert isinstance(loaded, LoadedPosteriorResults)
        self._current_run_directory = loaded.run_analysis.run_directory
        self._loaded_results = loaded
        self._current_plot = None
        return lambda: self._finalize_results_loaded(loaded)

    def _handle_summary_refreshed(self, payload: object) -> Callable[[], None]:
        loaded = payload
        assert isinstance(loaded, LoadedPosteriorResults)
        self._loaded_results = loaded
        return lambda: self._finalize_summary_refreshed(loaded)

    def _handle_plot_ready(self, payload: object) -> Callable[[], None]:
        plot = payload
        assert isinstance(plot, PosteriorPlotArtifact)
        self._current_plot = plot
        return lambda: self._finalize_plot_ready(plot)

    def _handle_summary_exported(self, payload: object) -> Callable[[], None]:
        artifact = payload
        assert isinstance(artifact, SummaryExportArtifact)
        return lambda: self._finalize_summary_exported(artifact)

    def _handle_plot_exported(self, payload: object) -> Callable[[], None]:
        path = payload
        assert isinstance(path, Path)
        return lambda: self._finalize_plot_exported(path)

    @Slot(int)
    def _handle_task_finished(self, token: int) -> None:
        pending_completion = self._pending_completion
        if (
            not self._shutdown_requested
            and token == self._generation
            and pending_completion is not None
            and pending_completion.token == token
        ):
            self._pending_completion = None
            pending_completion.finalize()
        elif pending_completion is not None and pending_completion.token == token:
            self._pending_completion = None
        self._emit_busy_changed()

    @Slot()
    def _handle_thread_finished(self) -> None:
        sender = self.sender()
        active_task = self._active_task
        if isinstance(sender, QThread) and active_task is not None:
            if active_task.thread is sender:
                self._active_task = None

        queued_load = self._queued_load
        if (
            not self._shutdown_requested
            and self._active_task is None
            and queued_load is not None
        ):
            self._queued_load = None
            self.load_run(queued_load.run_directory, queued_load.options)
        elif self._shutdown_requested and self._active_task is None:
            self._service.clear()

        if isinstance(sender, QThread):
            sender.deleteLater()
        self._emit_busy_changed()

    def _set_state(self, state: str, message: str) -> None:
        self._state = state
        self.state_changed.emit(state, message)
        self._emit_busy_changed()

    def _emit_busy_changed(self) -> None:
        self.busy_changed.emit(self.is_busy())

    def _process_events(self) -> None:
        app = QCoreApplication.instance()
        if app is not None:
            app.processEvents()

    def _finalize_results_loaded(self, loaded: LoadedPosteriorResults) -> None:
        self._set_state(STATE_READY, "Results ready.")
        self.results_loaded.emit(loaded)

    def _finalize_summary_refreshed(self, loaded: LoadedPosteriorResults) -> None:
        self._set_state(STATE_READY, "Posterior summary refreshed.")
        self.summary_refreshed.emit(loaded)

    def _finalize_plot_ready(self, plot: PosteriorPlotArtifact) -> None:
        self._set_state(STATE_READY, "Posterior plot ready.")
        self.plot_ready.emit(plot)

    def _finalize_summary_exported(self, artifact: SummaryExportArtifact) -> None:
        self._set_state(STATE_READY, f"Summary exported to {artifact.output_path}.")
        self.summary_exported.emit(artifact)

    def _finalize_plot_exported(self, path: Path) -> None:
        self._set_state(STATE_READY, f"Plot exported to {path}.")
        self.plot_exported.emit(str(path))

    def _finalize_failure(self, message: str, details: str) -> None:
        self._set_state(STATE_FAILED, message)
        self.failed.emit(message, details)


def _present_error(error: object) -> str:
    message = str(error)
    if isinstance(error, RunNotSuccessfulError):
        return "The run did not complete successfully."
    if isinstance(error, MultipleChainRootsError):
        return "The run contains multiple chain roots."
    if isinstance(error, MalformedRunDirectoryError):
        return "The run directory is invalid or incomplete."
    if isinstance(error, AnalysisPlotSelectionError):
        return "The parameter selection is invalid."
    if isinstance(error, InvalidAnalysisSettingError):
        if isinstance(error, InvalidMathTextError):
            return (
                "One or more plot labels contain invalid Matplotlib MathText. "
                "Check the title, legend label, or parameter display labels."
            )
        if "1D plots require exactly one selected parameter." in message:
            return "Select exactly one parameter for a 1D plot."
        if "2D plots require exactly two selected parameters." in message:
            return "Select exactly two parameters for a 2D plot."
        if "Triangle plots require at least two selected parameters." in message:
            return "Select at least two parameters for a triangle plot."
        return "The analysis options are invalid."
    return "Posterior analysis failed."
