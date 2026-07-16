"""Headless tests for execution-related main-window behavior."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QMessageBox

from cosmofit.application.examples import build_lcdm_example_run_config
from cosmofit.ui.execution_controller import (
    STATE_CANCELLED,
    STATE_CANCELLING,
    STATE_COMPLETED,
    STATE_RUNNING,
    STATE_STARTING,
)
from cosmofit.ui.main_window import MainWindow


class FakeExecutionController(QObject):
    state_changed = Signal(str, str)
    started = Signal(str)
    running = Signal()
    log_message = Signal(str, str)
    completed = Signal(str)
    failed = Signal(str)
    cancelled = Signal()
    final_run_directory = Signal(str)
    request_rejected = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.active = False
        self.cancel_calls = 0

    def start_run(self, run_config) -> bool:
        self.active = True
        self.last_run_config = run_config
        self.state_changed.emit(STATE_STARTING, "starting")
        return True

    def cancel_run(self) -> bool:
        if not self.active:
            return False
        self.cancel_calls += 1
        self.active = False
        self.state_changed.emit(STATE_CANCELLED, "cancelled")
        self.cancelled.emit()
        return True

    def has_active_run(self) -> bool:
        return self.active


def test_main_window_button_transitions() -> None:
    app = QApplication.instance() or QApplication([])
    controller = FakeExecutionController()
    window = MainWindow(execution_controller=controller)
    window.load_lcdm_example()

    window.start_run()
    app.processEvents()

    assert window.run_fit_button.isEnabled() is False
    assert window.cancel_run_button.isEnabled() is True
    assert window.model_widget.isEnabled() is False

    run_directory = Path.cwd() / "outputs" / "ui-test-run"
    controller.final_run_directory.emit(str(run_directory))
    controller.state_changed.emit(STATE_RUNNING, "running")
    controller.log_message.emit("stdout", "linea de log")
    controller.active = False
    controller.state_changed.emit(STATE_COMPLETED, "done")
    controller.completed.emit(str(run_directory))
    app.processEvents()

    assert window.run_fit_button.isEnabled() is True
    assert window.cancel_run_button.isEnabled() is False
    assert window.results_widget.open_output_button.isEnabled() is True
    assert "linea de log" in window.results_widget.log_area.toPlainText()
    assert "Etiqueta" in window.results_widget.summary_label.text()


def test_failed_run_does_not_enable_output_folder() -> None:
    app = QApplication.instance() or QApplication([])
    controller = FakeExecutionController()
    window = MainWindow(execution_controller=controller)
    window.load_lcdm_example()

    window.start_run()
    controller.active = False
    controller.state_changed.emit("Failed", "failed")
    controller.failed.emit("failed")
    app.processEvents()

    assert window.results_widget.open_output_button.isEnabled() is False
    assert "no disponibles" in window.results_widget.summary_label.text().lower()


def test_cancelling_state_disables_repeat_cancel() -> None:
    app = QApplication.instance() or QApplication([])
    controller = FakeExecutionController()
    window = MainWindow(execution_controller=controller)

    controller.state_changed.emit(STATE_CANCELLING, "cancelling")
    app.processEvents()

    assert window.cancel_run_button.isEnabled() is False
    assert window.run_fit_button.isEnabled() is False
    assert window.model_widget.isEnabled() is False


def test_close_event_confirms_active_process(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    controller = FakeExecutionController()
    controller.active = True
    window = MainWindow(execution_controller=controller)
    window.show()
    app.processEvents()

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.No,
    )
    closed = window.close()
    app.processEvents()

    assert closed is False
    assert controller.cancel_calls == 0
    assert window.isVisible() is True

    controller.active = True
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    closed = window.close()
    for _ in range(20):
        app.processEvents()
        time.sleep(0.01)

    assert closed is False
    assert controller.cancel_calls == 1


def test_successful_run_stores_final_directory() -> None:
    app = QApplication.instance() or QApplication([])
    controller = FakeExecutionController()
    window = MainWindow(execution_controller=controller)
    window.current_run_config = build_lcdm_example_run_config(
        output_directory=Path("outputs/window-success")
    )

    run_directory = Path.cwd() / "outputs" / "window-success-run"
    controller.final_run_directory.emit(str(run_directory))
    controller.state_changed.emit(STATE_COMPLETED, "done")
    controller.completed.emit(str(run_directory))
    app.processEvents()

    assert window.current_run_directory == run_directory
    assert str(run_directory) in window.results_widget.output_directory_label.text()
