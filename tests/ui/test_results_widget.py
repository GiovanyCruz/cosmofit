"""Headless tests for the results-tab widget."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog

from cosmofit.analysis.errors import RunNotSuccessfulError
from cosmofit.ui.results_controller import ResultsController
from cosmofit.ui.results_widget import ResultsWidget
from tests.ui.test_results_controller import FakePosteriorResultsService, _spin_until


def test_results_widget_loads_completed_run_and_populates_summary(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    controller = ResultsController(
        service_factory=lambda: FakePosteriorResultsService(tmp_path)
    )
    widget = ResultsWidget(controller=controller)

    assert widget.load_run_from_path(tmp_path / "completed-run") is True
    _spin_until(lambda: widget.parameter_list.count() == 2, app)

    assert widget.run_label_value.text() == "ui-test-run"
    assert widget.parameter_summary_table.rowCount() == 3
    assert widget.open_output_button.isEnabled() is True
    assert "completed-run" in widget.output_directory_label.text()
    controller.shutdown()


def test_results_widget_generates_plot_preview_and_exports_png(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = QApplication.instance() or QApplication([])
    controller = ResultsController(
        service_factory=lambda: FakePosteriorResultsService(tmp_path)
    )
    widget = ResultsWidget(controller=controller)
    widget.load_run_from_path(tmp_path / "completed-run")
    _spin_until(lambda: widget.parameter_list.count() == 2, app)

    widget.parameter_list.selectAll()
    app.processEvents()
    widget._request_plot("2d")
    _spin_until(lambda: widget.current_plot() is not None, app)

    destination = tmp_path / "copied-plot.png"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(destination), "PNG (*.png)"),
    )
    monkeypatch.setattr(
        controller,
        "export_current_plot",
        lambda path: destination.write_bytes(b"png") or True,
    )
    widget._save_current_plot(".png")

    assert widget.plot_preview_label.pixmap() is not None
    assert destination.is_file()
    controller.shutdown()


def test_results_widget_renders_mathtext_title_preview(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    controller = ResultsController(
        service_factory=lambda: FakePosteriorResultsService(tmp_path)
    )
    widget = ResultsWidget(controller=controller)

    widget.plot_title_edit.setText(r"$H_0$")
    app.processEvents()

    assert widget.plot_title_preview.preview_label.pixmap() is not None
    assert "MathText examples" in widget.plot_title_edit.toolTip()
    controller.shutdown()


def test_results_widget_load_latest_completed_run(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    controller = ResultsController(
        service_factory=lambda: FakePosteriorResultsService(tmp_path)
    )
    widget = ResultsWidget(controller=controller)
    widget.set_latest_completed_run(tmp_path / "completed-run")

    widget.load_latest_button.click()
    _spin_until(lambda: widget.run_label_value.text() == "ui-test-run", app)

    assert widget.run_directory_edit.text().endswith("completed-run")
    controller.shutdown()


def test_results_widget_load_button_requires_directory(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    controller = ResultsController(
        service_factory=lambda: FakePosteriorResultsService(tmp_path)
    )
    widget = ResultsWidget(controller=controller)

    widget.run_directory_edit.clear()
    widget.load_run_button.click()
    app.processEvents()

    assert "Select a run directory" in widget.status_message_label.text()
    controller.shutdown()


def test_results_widget_clears_stale_results_after_failed_load(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    controller = ResultsController(
        service_factory=lambda: FakePosteriorResultsService(tmp_path)
    )
    widget = ResultsWidget(controller=controller)
    widget.load_run_from_path(tmp_path / "completed-run")
    _spin_until(lambda: widget.parameter_list.count() == 2, app)

    controller._service = FailingPosteriorResultsService()  # noqa: SLF001
    assert widget.load_run_from_path(tmp_path / "failed-run") is True
    _spin_until(
        lambda: "did not complete successfully"
        in widget.status_message_label.text().lower(),
        app,
    )

    assert widget.parameter_list.count() == 0
    assert widget.run_label_value.text() == "n/a"
    assert widget.export_summary_json_button.isEnabled() is False
    controller.shutdown()


def test_results_widget_marks_runtime_option_changes_as_dirty(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    controller = ResultsController(
        service_factory=lambda: FakePosteriorResultsService(tmp_path)
    )
    widget = ResultsWidget(controller=controller)
    widget.load_run_from_path(tmp_path / "completed-run")
    _spin_until(lambda: widget.parameter_list.count() == 2, app)

    widget.parameter_list.item(0).setSelected(True)
    widget.ignore_rows_spin.setValue(0.25)
    app.processEvents()

    assert widget.plot_1d_button.isEnabled() is False
    assert widget.export_summary_json_button.isEnabled() is False
    assert "reload the results" in widget.status_message_label.text().lower()
    controller.shutdown()


def test_results_widget_plot_ready_preserves_action_button_height(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    controller = ResultsController(
        service_factory=lambda: FakePosteriorResultsService(tmp_path)
    )
    widget = ResultsWidget(controller=controller)
    widget.show()
    widget.resize(800, 600)
    widget.load_run_from_path(tmp_path / "completed-run")
    _spin_until(lambda: widget.parameter_list.count() == 2, app)

    widget.parameter_list.selectAll()
    app.processEvents()
    action_panel_hint = widget.plot_actions_group.sizeHint().height()
    per_button_hints = {
        button.text(): button.sizeHint().height()
        for button in widget.plot_action_buttons
    }

    widget._request_plot("2d")
    _spin_until(lambda: widget.current_plot() is not None, app)
    app.processEvents()

    assert widget.plot_actions_group.height() >= action_panel_hint
    for button in widget.plot_action_buttons:
        assert button.height() >= per_button_hints[button.text()]
        assert button.height() > button.fontMetrics().height()
    widget.close()
    app.processEvents()
    controller.shutdown()


def test_results_widget_preview_shrinks_before_actions_collapse(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    controller = ResultsController(
        service_factory=lambda: FakePosteriorResultsService(tmp_path)
    )
    widget = ResultsWidget(controller=controller)
    widget.show()
    widget.resize(1200, 800)
    widget.load_run_from_path(tmp_path / "completed-run")
    _spin_until(lambda: widget.parameter_list.count() == 2, app)

    widget.parameter_list.selectAll()
    app.processEvents()
    widget._request_plot("triangle")
    _spin_until(lambda: widget.current_plot() is not None, app)
    app.processEvents()

    action_panel_hint = widget.plot_actions_group.sizeHint().height()
    large_preview_height = widget.plot_scroll.viewport().height()

    widget.resize(800, 600)
    app.processEvents()

    assert widget.plot_actions_group.height() >= action_panel_hint
    assert widget.plot_scroll.viewport().height() < large_preview_height
    assert widget.plot_preview_label.pixmap() is not None
    assert (
        widget.plot_preview_label.pixmap().height()
        <= widget.plot_scroll.viewport().height()
    )
    widget.close()
    app.processEvents()
    controller.shutdown()


def test_results_widget_plot_buttons_refresh_immediately_without_focus_change(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    controller = ResultsController(
        service_factory=lambda: FakePosteriorResultsService(tmp_path)
    )
    widget = ResultsWidget(controller=controller)
    widget.show()
    widget.load_run_from_path(tmp_path / "completed-run")
    _spin_until(lambda: widget.parameter_list.count() == 2, app)

    widget.parameter_list.setFocus()
    widget.parameter_list.item(0).setSelected(True)
    app.processEvents()

    assert widget.focusWidget() is widget.parameter_list
    assert widget.plot_1d_button.isEnabled() is True
    assert widget.plot_2d_button.isEnabled() is False
    assert widget.triangle_plot_button.isEnabled() is False

    widget.parameter_list.item(1).setSelected(True)
    app.processEvents()

    assert widget.focusWidget() is widget.parameter_list
    assert widget.plot_1d_button.isEnabled() is False
    assert widget.plot_2d_button.isEnabled() is True
    assert widget.triangle_plot_button.isEnabled() is True

    widget.parameter_list.item(1).setSelected(False)
    app.processEvents()

    assert widget.focusWidget() is widget.parameter_list
    assert widget.plot_1d_button.isEnabled() is True
    assert widget.plot_2d_button.isEnabled() is False
    assert widget.triangle_plot_button.isEnabled() is False

    widget.parameter_list.clearSelection()
    app.processEvents()

    assert widget.plot_1d_button.isEnabled() is False
    assert widget.plot_2d_button.isEnabled() is False
    assert widget.triangle_plot_button.isEnabled() is False
    widget.close()
    app.processEvents()
    controller.shutdown()


def test_results_widget_keyboard_selection_updates_plot_buttons_immediately(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    controller = ResultsController(
        service_factory=lambda: FakePosteriorResultsService(tmp_path)
    )
    widget = ResultsWidget(controller=controller)
    widget.show()
    widget.load_run_from_path(tmp_path / "completed-run")
    _spin_until(lambda: widget.parameter_list.count() == 2, app)

    widget.parameter_list.setFocus()
    widget.parameter_list.setCurrentRow(0)
    QTest.keyClick(widget.parameter_list, Qt.Key.Key_Space)
    app.processEvents()

    assert widget.focusWidget() is widget.parameter_list
    assert widget.plot_1d_button.isEnabled() is True
    assert widget.plot_2d_button.isEnabled() is False
    assert widget.triangle_plot_button.isEnabled() is False

    QTest.keyClick(
        widget.parameter_list,
        Qt.Key.Key_Down,
        Qt.KeyboardModifier.ShiftModifier,
    )
    app.processEvents()

    assert widget.focusWidget() is widget.parameter_list
    assert widget.plot_1d_button.isEnabled() is False
    assert widget.plot_2d_button.isEnabled() is True
    assert widget.triangle_plot_button.isEnabled() is True

    QTest.keyClick(
        widget.parameter_list,
        Qt.Key.Key_Up,
        Qt.KeyboardModifier.ShiftModifier,
    )
    app.processEvents()

    assert widget.focusWidget() is widget.parameter_list
    assert widget.plot_1d_button.isEnabled() is True
    assert widget.plot_2d_button.isEnabled() is False
    assert widget.triangle_plot_button.isEnabled() is False
    widget.close()
    app.processEvents()
    controller.shutdown()


class FailingPosteriorResultsService(FakePosteriorResultsService):
    def __init__(self) -> None:
        super().__init__(Path("/tmp"))

    def load_run(self, run_directory: Path, *, options):  # type: ignore[override]
        raise RunNotSuccessfulError(
            f"Run directory '{run_directory}' has status state='failed'."
        )
