"""Responsive layout tests for the PySide6 main window."""

from __future__ import annotations

from pathlib import Path

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
