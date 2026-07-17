"""Responsive layout tests for the PySide6 main window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QWidget

from cosmofit.ui.main_window import MainWindow
from cosmofit.ui.results_controller import ResultsController
from tests.ui.test_results_controller import FakePosteriorResultsService, _spin_until


def _build_window() -> MainWindow:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    app.processEvents()
    return window


def test_main_window_minimum_size_hint_is_practical() -> None:
    app = QApplication.instance() or QApplication([])
    window = _build_window()

    minimum_size_hint = window.minimumSizeHint()

    assert minimum_size_hint.width() <= 900
    assert minimum_size_hint.height() <= 720
    assert window.minimumSize().width() == 800
    assert window.minimumSize().height() == 600
    window.close()
    app.processEvents()


def test_main_window_can_resize_to_800_by_600() -> None:
    app = QApplication.instance() or QApplication([])
    window = _build_window()

    window.resize(800, 600)
    app.processEvents()

    assert window.size().width() == 800
    assert window.size().height() == 600
    window.close()
    app.processEvents()


def test_long_tab_pages_expose_scroll_areas() -> None:
    app = QApplication.instance() or QApplication([])
    window = _build_window()

    for widget in (
        window.model_widget,
        window.datasets_widget,
        window.sampler_widget,
    ):
        assert widget.scroll_area.widgetResizable() is True

    assert window.results_widget.results_scroll_area.widgetResizable() is True
    assert window.results_widget.content_scroll_area.widgetResizable() is True
    assert window.results_widget.plot_scroll.widgetResizable() is True
    window.close()
    app.processEvents()


def test_tables_scroll_instead_of_expanding_window(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    window = _build_window()
    window.resize(800, 600)
    window.load_lcdm_example()

    rows = []
    for index in range(6):
        rows.append(
            {
                "name": f"parameter_{index}",
                "label": f"Long parameter label {index}",
                "role": "sampled",
                "prior_min": "0.0",
                "prior_max": "1.0",
                "reference": "0.5",
                "proposal": "0.1",
                "fixed_value": "",
                "unit": "km/s/Mpc",
                "nuisance": False,
            }
        )
    window.parameter_table.set_parameters_state(rows)
    window.tabs.setCurrentWidget(window.parameter_table)
    app.processEvents()

    controller = ResultsController(
        service_factory=lambda: FakePosteriorResultsService(tmp_path)
    )
    window.results_widget.results_controller.shutdown()
    window.results_widget.results_controller = controller
    window.results_widget._wire_signals()  # noqa: SLF001
    window.results_widget.load_run_from_path(tmp_path / "completed-run")
    _spin_until(lambda: window.results_widget.parameter_list.count() == 2, app)
    window.tabs.setCurrentWidget(window.results_widget)
    app.processEvents()

    assert window.parameter_table.table.horizontalScrollBar().maximum() > 0
    assert (
        window.results_widget.parameter_summary_table.horizontalScrollBar().maximum()
        > 0
    )
    assert window.minimumSizeHint().width() <= 900
    controller.shutdown()
    window.close()
    app.processEvents()


def test_parameter_label_preview_uses_separate_column_without_row_overlap() -> None:
    app = QApplication.instance() or QApplication([])
    window = _build_window()
    window.resize(800, 600)
    window.parameter_table.set_parameters_state(
        [
            {
                "name": "H0",
                "label": "H0",
                "role": "sampled",
                "prior_min": "50",
                "prior_max": "90",
                "reference": "70",
                "proposal": "1",
                "fixed_value": "",
                "unit": "km/s/Mpc",
                "nuisance": False,
            },
            {
                "name": "Om",
                "label": r"$\Omega_m$",
                "role": "sampled",
                "prior_min": "0.1",
                "prior_max": "0.5",
                "reference": "0.3",
                "proposal": "0.01",
                "fixed_value": "",
                "unit": "",
                "nuisance": False,
            },
            {
                "name": "bad",
                "label": r"$\Omega_m",
                "role": "sampled",
                "prior_min": "0.1",
                "prior_max": "0.5",
                "reference": "0.3",
                "proposal": "0.01",
                "fixed_value": "",
                "unit": "",
                "nuisance": False,
            },
        ]
    )
    window.tabs.setCurrentWidget(window.parameter_table)
    app.processEvents()

    table = window.parameter_table.table
    preview_column = window.parameter_table.COLUMN_PREVIEW
    plain_preview = table.cellWidget(0, preview_column)
    math_preview = table.cellWidget(1, preview_column)
    invalid_preview = table.cellWidget(2, preview_column)

    assert table.horizontalHeaderItem(preview_column).text() == "Preview"
    assert table.cellWidget(0, window.parameter_table.COLUMN_LABEL) is not plain_preview
    assert table.rowHeight(0) <= 40
    assert plain_preview is not None
    assert math_preview is not None
    assert invalid_preview is not None
    assert (
        plain_preview.preview_label.text() == "H0"
        or plain_preview.preview_label.pixmap() is not None
    )
    assert math_preview.preview_label.pixmap() is not None
    assert invalid_preview.preview_label.text() == "Invalid MathText."

    plain_rect = plain_preview.geometry()
    next_row_top = table.visualRect(table.model().index(1, preview_column)).top()
    assert plain_rect.bottom() < next_row_top

    table.selectRow(1)
    app.processEvents()
    highlight_color = table.palette().color(table.foregroundRole())
    assert math_preview.autoFillBackground() is True
    assert (
        math_preview.palette().color(math_preview.backgroundRole())
        != highlight_color
    )

    window.resize(640, 480)
    app.processEvents()
    math_rect = math_preview.geometry()
    math_cell_rect = table.visualRect(table.model().index(1, preview_column))
    assert math_rect.height() <= table.rowHeight(1)
    assert math_rect.top() >= math_cell_rect.top()
    assert math_rect.bottom() <= math_cell_rect.bottom()
    assert table.horizontalScrollBar().maximum() >= 0
    assert table.verticalScrollBar().maximum() >= 0
    window.close()
    app.processEvents()


def test_results_page_overflow_uses_scrollbars_at_small_size(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    controller = ResultsController(
        service_factory=lambda: FakePosteriorResultsService(tmp_path)
    )
    window = MainWindow()
    window.results_widget.results_controller.shutdown()
    window.results_widget.results_controller = controller
    window.results_widget._wire_signals()  # noqa: SLF001
    window.show()
    window.resize(800, 600)
    window.results_widget.load_run_from_path(tmp_path / "completed-run")
    _spin_until(lambda: window.results_widget.parameter_list.count() == 2, app)
    window.tabs.setCurrentWidget(window.results_widget)
    app.processEvents()

    assert window.results_widget.results_scroll_area.verticalScrollBar().maximum() > 0
    assert (
        window.results_widget.plot_scroll.verticalScrollBarPolicy().name
        == "ScrollBarAsNeeded"
    )
    controller.shutdown()
    window.close()
    app.processEvents()


def test_datasets_page_wraps_supernova_note_and_long_packages_path() -> None:
    app = QApplication.instance() or QApplication([])
    window = _build_window()
    window.resize(800, 600)
    long_path = Path("/tmp/cosmofit/cobaya/packages/with/a/very/long/path/for/layout")
    window.datasets_widget.set_packages_path(long_path)
    window.tabs.setCurrentWidget(window.datasets_widget)
    app.processEvents()

    note = window.datasets_widget.use_abs_mag_label
    packages = window.datasets_widget.packages_path_edit
    note_origin = note.mapToGlobal(QPoint(0, 0))
    packages_origin = packages.mapToGlobal(QPoint(0, 0))

    assert "use_abs_mag" not in note.text()
    assert "absolute-magnitude" in note.text()
    assert note.wordWrap() is True
    assert (
        note.alignment()
        == Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
    )
    assert note.sizePolicy().verticalPolicy().name == "Preferred"
    assert packages.isReadOnly() is True
    assert packages.text() == str(long_path)
    assert packages.toolTip() == str(long_path)
    assert note_origin.y() + note.height() <= packages_origin.y()
    assert window.datasets_widget.scroll_area.widgetResizable() is True
    window.close()
    app.processEvents()


def test_plot_preview_scales_without_replacing_export_resolution(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    controller = ResultsController(
        service_factory=lambda: FakePosteriorResultsService(tmp_path)
    )
    window = MainWindow()
    window.results_widget.results_controller.shutdown()
    window.results_widget.results_controller = controller
    window.results_widget._wire_signals()  # noqa: SLF001
    window.show()
    window.resize(800, 600)
    window.results_widget.load_run_from_path(tmp_path / "completed-run")
    _spin_until(lambda: window.results_widget.parameter_list.count() == 2, app)
    window.tabs.setCurrentWidget(window.results_widget)
    app.processEvents()
    window.results_widget.parameter_list.selectAll()
    app.processEvents()
    window.results_widget._request_plot("2d")  # noqa: SLF001
    _spin_until(lambda: window.results_widget.current_plot() is not None, app)

    preview = window.results_widget.plot_preview_label.pixmap()
    assert preview is not None
    assert window.results_widget.current_plot() is not None
    original = window.results_widget.current_plot().export.png_path
    assert original.is_file()
    assert preview.width() <= window.results_widget.plot_scroll.viewport().width()
    assert preview.height() <= window.results_widget.plot_scroll.viewport().height()
    controller.shutdown()
    window.close()
    app.processEvents()


def test_results_actions_remain_usable_after_plot_ready_at_800_by_600(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    controller = ResultsController(
        service_factory=lambda: FakePosteriorResultsService(tmp_path)
    )
    window = MainWindow()
    window.results_widget.results_controller.shutdown()
    window.results_widget.results_controller = controller
    window.results_widget._wire_signals()  # noqa: SLF001
    window.show()
    window.resize(800, 600)
    window.results_widget.load_run_from_path(tmp_path / "completed-run")
    _spin_until(lambda: window.results_widget.parameter_list.count() == 2, app)
    window.tabs.setTabEnabled(window.tabs.indexOf(window.results_widget), True)
    window.tabs.setCurrentWidget(window.results_widget)
    app.processEvents()
    window.results_widget.parameter_list.selectAll()
    app.processEvents()

    splitter_sizes_before = tuple(window.results_widget.content_splitter.sizes())
    action_panel_hint = window.results_widget.plot_actions_group.sizeHint().height()

    window.results_widget._request_plot("2d")  # noqa: SLF001
    _spin_until(lambda: window.results_widget.current_plot() is not None, app)
    app.processEvents()

    splitter_sizes_after = tuple(window.results_widget.content_splitter.sizes())

    assert window.results_widget.plot_actions_group.height() >= action_panel_hint
    assert all(
        button.height() >= button.sizeHint().height()
        for button in window.results_widget.plot_action_buttons
    )
    assert len(splitter_sizes_before) == 2
    assert len(splitter_sizes_after) == 2
    assert min(splitter_sizes_after) > 0
    controller.shutdown()
    window.close()
    app.processEvents()


def test_no_widget_uses_large_fixed_dimensions() -> None:
    app = QApplication.instance() or QApplication([])
    window = _build_window()

    offenders: list[str] = []
    for widget in window.findChildren(QWidget):
        minimum = widget.minimumSize()
        maximum = widget.maximumSize()
        if (
            minimum.width() == maximum.width()
            and minimum.width() > 400
            and minimum.width() < 16777215
        ):
            offenders.append(type(widget).__name__)
        if (
            minimum.height() == maximum.height()
            and minimum.height() > 260
            and minimum.height() < 16777215
        ):
            offenders.append(type(widget).__name__)

    assert offenders == []
    window.close()
    app.processEvents()
