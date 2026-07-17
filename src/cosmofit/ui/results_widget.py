"""Results tab widget for completed-run posterior summaries and plots."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cosmofit.analysis.models import CredibleInterval
from cosmofit.application import (
    LoadedPosteriorResults,
    MathTextService,
    PosteriorPlotArtifact,
    PosteriorPlotRequest,
    PosteriorResultsLoadOptions,
)
from cosmofit.ui.results_controller import (
    STATE_CLEARED,
    STATE_EXPORTING,
    STATE_FAILED,
    STATE_LOADING,
    STATE_NO_RUN_LOADED,
    STATE_PLOTTING,
    STATE_READY,
    ResultsController,
)

_SUPPORTED_CONFIDENCE_LEVELS = {"68%": 0.68, "95%": 0.95}
_MATH_TEXT_EXAMPLES = "\n".join(
    [
        "Matplotlib MathText examples:",
        "$H_0$",
        "$\\Omega_m$",
        "$\\Lambda$CDM",
        "$w_0$",
        "$w_a$",
    ]
)


class PlotPreviewLabel(QLabel):
    """Scale plot previews to the available viewport without changing exports."""

    def __init__(self) -> None:
        super().__init__("Preview unavailable.")
        self._source_pixmap = QPixmap()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(96, 72)
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored,
        )
        self.setWordWrap(True)

    def set_preview_pixmap(self, pixmap: QPixmap) -> None:
        self._source_pixmap = QPixmap(pixmap)
        self._refresh_scaled_pixmap()

    def clear_preview(self, message: str) -> None:
        self._source_pixmap = QPixmap()
        self.setPixmap(QPixmap())
        self.setText(message)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._refresh_scaled_pixmap()

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return self._bounded_preview_size()

    def minimumSizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(96, 72)

    def _refresh_scaled_pixmap(self) -> None:
        if self._source_pixmap.isNull():
            return
        scaled = self._source_pixmap.scaled(
            max(self.width() - 12, 1),
            max(self.height() - 12, 1),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)
        self.setText("")

    def _bounded_preview_size(self) -> QSize:
        if self._source_pixmap.isNull():
            return QSize(320, 240)

        bounded = self._source_pixmap.size()
        bounded.scale(
            480,
            360,
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        return bounded.expandedTo(QSize(96, 72))


class MathTextPreviewBox(QWidget):
    """Preview one title or legend field using the application MathText helper."""

    def __init__(self, *, edit: QLineEdit, field_name: str) -> None:
        super().__init__()
        self._edit = edit
        self._field_name = field_name
        self._service = MathTextService()
        self.preview_label = QLabel("Plain text or MathText preview.")
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(28)
        self.preview_label.setToolTip(_MATH_TEXT_EXAMPLES)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.preview_label)

        self._edit.setToolTip(_MATH_TEXT_EXAMPLES)
        self._edit.textChanged.connect(self.refresh_preview)
        self.refresh_preview(self._edit.text())

    def refresh_preview(self, text: str) -> None:
        if not text.strip():
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setStyleSheet("")
            self.preview_label.setText("Plain text or MathText preview.")
            return
        try:
            preview = self._service.render_preview(text, field_name=self._field_name)
        except ValueError as error:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setStyleSheet("color: #9b1c1c;")
            self.preview_label.setText("Invalid MathText.")
            self.preview_label.setToolTip(f"{_MATH_TEXT_EXAMPLES}\n\n{error}")
            return

        self.preview_label.setStyleSheet("")
        self.preview_label.setToolTip(_MATH_TEXT_EXAMPLES)
        if preview is None:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("Plain text or MathText preview.")
            return

        pixmap = QPixmap()
        pixmap.loadFromData(preview.png_bytes)
        self.preview_label.setPixmap(pixmap)
        self.preview_label.setText("")


class ResultsWidget(QWidget):
    """Display logs plus posterior loading, summaries, and plot controls."""

    def __init__(self, *, controller: ResultsController | None = None) -> None:
        super().__init__()
        self._pending_log_lines: list[str] = []
        self._current_output_directory: Path | None = None
        self._latest_completed_run: Path | None = None
        self._loaded_results: LoadedPosteriorResults | None = None
        self._current_plot: PosteriorPlotArtifact | None = None
        self._options_dirty = False
        self._selection_refresh_queued = False
        self._list_signals_wired = False
        self.results_controller = controller or ResultsController(parent=self)

        self.state_label = QLabel(f"State: {STATE_NO_RUN_LOADED}")
        self.output_directory_label = QLabel("Output folder: no execution")
        self.output_directory_label.setWordWrap(True)
        self.run_label_value = QLabel("n/a")
        self.run_directory_value = QLabel("n/a")
        self.run_directory_value.setWordWrap(True)
        self.datasets_value = QLabel("n/a")
        self.datasets_value.setWordWrap(True)
        self.sampled_count_value = QLabel("0")
        self.status_message_label = QLabel("No run loaded.")
        self.status_message_label.setWordWrap(True)
        self.summary_label = QLabel(
            "Completed results are not available yet.\n"
            "Load a completed run to inspect the posterior results."
        )
        self.summary_label.setWordWrap(True)
        self.fixed_parameters_label = QLabel("Fixed parameters: n/a")
        self.fixed_parameters_label.setWordWrap(True)

        self.run_directory_edit = QLineEdit()
        self.run_directory_edit.setPlaceholderText(
            "Select a completed CosmoFit run"
        )
        self.load_latest_button = QPushButton("Load latest completed run")
        self.open_run_button = QPushButton("Open run directory")
        self.load_run_button = QPushButton("Load")
        self.reload_button = QPushButton("Reload")
        self.clear_results_button = QPushButton("Clear results")

        self.credible_level_combo = QComboBox()
        self.credible_level_combo.addItems(tuple(_SUPPORTED_CONFIDENCE_LEVELS))
        self.ignore_rows_spin = QDoubleSpinBox()
        self.ignore_rows_spin.setRange(0.0, 0.99)
        self.ignore_rows_spin.setDecimals(2)
        self.ignore_rows_spin.setSingleStep(0.05)
        self.plot_title_edit = QLineEdit()
        self.plot_title_edit.setPlaceholderText("Optional plot title")
        self.plot_title_preview = MathTextPreviewBox(
            edit=self.plot_title_edit,
            field_name="plot title",
        )
        self.legend_label_edit = QLineEdit()
        self.legend_label_edit.setPlaceholderText("Optional legend label")
        self.legend_label_preview = MathTextPreviewBox(
            edit=self.legend_label_edit,
            field_name="legend label",
        )
        self.filled_contours_checkbox = QCheckBox("Filled contours")
        self.filled_contours_checkbox.setChecked(True)

        self.parameter_list = QListWidget()
        self.parameter_list.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection
        )
        self.select_all_button = QPushButton("Select all")
        self.clear_selection_button = QPushButton("Clear selection")
        self.invert_selection_button = QPushButton("Invert selection")

        self.plot_1d_button = QPushButton("Generate 1D")
        self.plot_2d_button = QPushButton("Generate 2D")
        self.triangle_plot_button = QPushButton("Generate triangle")
        self.export_summary_json_button = QPushButton("Export summary JSON")
        self.export_summary_csv_button = QPushButton("Export summary CSV")
        self.save_plot_png_button = QPushButton("Save current plot as PNG")
        self.save_plot_pdf_button = QPushButton("Save current plot as PDF")
        self.clear_plot_button = QPushButton("Clear plot")

        self.parameter_summary_table = QTableWidget(0, 10)
        self.parameter_summary_table.setHorizontalHeaderLabels(
            [
                "name",
                "label",
                "mean",
                "std",
                "median",
                "lower",
                "upper",
                "map",
                "nuisance",
                "derived",
            ]
        )
        self.parameter_summary_table.verticalHeader().setVisible(False)
        self.parameter_summary_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.parameter_summary_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.parameter_summary_table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.parameter_summary_table.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored
        )
        self.parameter_summary_table.setWordWrap(False)
        self.parameter_summary_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.parameter_summary_table.horizontalHeader().setMinimumSectionSize(68)
        self.parameter_summary_table.horizontalHeader().setDefaultSectionSize(110)
        self.parameter_summary_table.horizontalHeader().setStretchLastSection(False)

        self.plot_info_label = QLabel("No plot available.")
        self.plot_info_label.setWordWrap(True)
        self.plot_preview_label = PlotPreviewLabel()

        self.plot_scroll = QScrollArea()
        self.plot_scroll.setWidgetResizable(True)
        self.plot_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.plot_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.plot_scroll.setWidget(self.plot_preview_label)
        self.plot_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.document().setMaximumBlockCount(5000)
        self.log_area.setMinimumHeight(0)
        self.clear_log_button = QPushButton("Clear log")
        self.open_output_button = QPushButton("Open output folder")
        self.open_output_button.setEnabled(False)

        self._log_flush_timer = QTimer(self)
        self._log_flush_timer.setSingleShot(True)
        self._log_flush_timer.setInterval(25)
        self._log_flush_timer.timeout.connect(self._flush_log_lines)

        self._build_layout()
        self._wire_signals()
        self._apply_results_enabled(False)
        self._refresh_action_state()

    def append_log_line(self, stream: str, line: str) -> None:
        prefix = "[stderr] " if stream == "stderr" else ""
        self._pending_log_lines.append(prefix + line)
        if not self._log_flush_timer.isActive():
            self._log_flush_timer.start()

    def clear_log(self) -> None:
        self._pending_log_lines.clear()
        self._log_flush_timer.stop()
        self.log_area.clear()

    def set_execution_state(self, state: str) -> None:
        self._flush_log_lines()
        self.state_label.setText(f"State: {state}")

    def set_output_directory(self, path: Path | None) -> None:
        self._current_output_directory = path
        label = "no execution" if path is None else str(path)
        self.output_directory_label.setText(f"Output folder: {label}")
        self.open_output_button.setEnabled(path is not None)

    def set_placeholder_summary(
        self,
        *,
        run_label: str,
        completion_state: str,
        output_directory: Path,
        datasets: tuple[str, ...],
        sampled_parameters: tuple[str, ...],
    ) -> None:
        self.summary_label.setText(
            "\n".join(
                [
                    f"Run label: {run_label}",
                    f"Final state: {completion_state}",
                    f"Run directory: {output_directory}",
                    "Datasets: " + ", ".join(datasets),
                    "Sampled parameters: " + ", ".join(sampled_parameters),
                    "Results are ready to load from the completed run.",
                ]
            )
        )

    def set_latest_completed_run(self, run_directory: Path | None) -> None:
        self._latest_completed_run = (
            run_directory.expanduser().resolve() if run_directory else None
        )
        self.results_controller.set_latest_completed_run(self._latest_completed_run)
        self.load_latest_button.setEnabled(self._latest_completed_run is not None)
        if self._latest_completed_run is not None:
            self.run_directory_edit.setText(str(self._latest_completed_run))

    def reset_loaded_results(self) -> None:
        self._loaded_results = None
        self._current_plot = None
        self._options_dirty = False
        self.parameter_list.clear()
        self.parameter_summary_table.setRowCount(0)
        self.plot_preview_label.clear_preview("Preview unavailable.")
        self.plot_info_label.setText("No plot available.")
        self.run_label_value.setText("n/a")
        self.run_directory_value.setText("n/a")
        self.datasets_value.setText("n/a")
        self.sampled_count_value.setText("0")
        self.fixed_parameters_label.setText("Fixed parameters: n/a")
        self._apply_results_enabled(False)
        self._refresh_action_state()

    def current_plot(self) -> PosteriorPlotArtifact | None:
        return self._current_plot

    def selected_parameters(self) -> tuple[str, ...]:
        symbols: list[str] = []
        seen: set[str] = set()
        for item in self.parameter_list.selectedItems():
            symbol = str(item.data(Qt.ItemDataRole.UserRole))
            if symbol in seen:
                continue
            seen.add(symbol)
            symbols.append(symbol)
        return tuple(symbols)

    def load_run_from_path(self, run_directory: Path) -> bool:
        self.run_directory_edit.setText(str(run_directory))
        return self.results_controller.load_run(run_directory, self._load_options())

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.results_controller.shutdown()
        super().closeEvent(event)

    def _build_layout(self) -> None:
        metadata_group = QGroupBox("Summary")
        metadata_layout = QGridLayout(metadata_group)
        metadata_layout.addWidget(QLabel("Run label"), 0, 0)
        metadata_layout.addWidget(self.run_label_value, 0, 1)
        metadata_layout.addWidget(QLabel("Run directory"), 1, 0)
        metadata_layout.addWidget(self.run_directory_value, 1, 1)
        metadata_layout.addWidget(QLabel("Datasets"), 2, 0)
        metadata_layout.addWidget(self.datasets_value, 2, 1)
        metadata_layout.addWidget(QLabel("Sampled count"), 3, 0)
        metadata_layout.addWidget(self.sampled_count_value, 3, 1)

        load_group = QGroupBox("Load")
        load_layout = QGridLayout(load_group)
        load_layout.addWidget(self.load_latest_button, 0, 0)
        load_layout.addWidget(self.open_run_button, 0, 1)
        load_layout.addWidget(self.load_run_button, 0, 2)
        load_layout.addWidget(self.reload_button, 1, 0)
        load_layout.addWidget(self.clear_results_button, 1, 1)
        load_layout.setColumnStretch(3, 1)
        load_layout.addWidget(QLabel("Run directory"), 2, 0)
        load_layout.addWidget(self.run_directory_edit, 2, 1, 1, 3)
        load_layout.addWidget(self.status_message_label, 3, 0, 1, 4)

        options_group = QGroupBox("Options")
        options_layout = QFormLayout(options_group)
        options_top_row = QHBoxLayout()
        options_top_row.addWidget(self.credible_level_combo)
        options_top_row.addWidget(QLabel("Ignore initial fraction"))
        options_top_row.addWidget(self.ignore_rows_spin)
        options_top_row.addWidget(self.filled_contours_checkbox)
        options_top_row.addStretch(1)
        options_layout.addRow("Credible level", options_top_row)
        plot_title_widget = QWidget()
        plot_title_layout = QVBoxLayout(plot_title_widget)
        plot_title_layout.setContentsMargins(0, 0, 0, 0)
        plot_title_layout.setSpacing(2)
        plot_title_layout.addWidget(self.plot_title_edit)
        plot_title_layout.addWidget(self.plot_title_preview)
        legend_widget = QWidget()
        legend_layout = QVBoxLayout(legend_widget)
        legend_layout.setContentsMargins(0, 0, 0, 0)
        legend_layout.setSpacing(2)
        legend_layout.addWidget(self.legend_label_edit)
        legend_layout.addWidget(self.legend_label_preview)
        options_layout.addRow("Plot title", plot_title_widget)
        options_layout.addRow("Legend label", legend_widget)

        selection_group = QGroupBox("Parameters")
        selection_layout = QVBoxLayout(selection_group)
        selection_buttons = QHBoxLayout()
        selection_buttons.addWidget(self.select_all_button)
        selection_buttons.addWidget(self.clear_selection_button)
        selection_buttons.addWidget(self.invert_selection_button)
        selection_buttons.addStretch(1)
        selection_layout.addLayout(selection_buttons)
        selection_layout.addWidget(self.parameter_list)

        self.plot_actions_group = QGroupBox("Actions")
        plot_actions_layout = QGridLayout(self.plot_actions_group)
        self.plot_action_buttons = (
            self.plot_1d_button,
            self.plot_2d_button,
            self.triangle_plot_button,
            self.export_summary_json_button,
            self.export_summary_csv_button,
            self.save_plot_png_button,
            self.save_plot_pdf_button,
            self.clear_plot_button,
        )
        for index, button in enumerate(self.plot_action_buttons):
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            button.setMinimumHeight(button.sizeHint().height())
            plot_actions_layout.addWidget(button, index // 2, index % 2)
        self.plot_actions_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        left_panel = QWidget()
        left_panel.setMinimumWidth(0)
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(metadata_group)
        left_layout.addWidget(load_group)
        left_layout.addWidget(options_group)
        left_layout.addWidget(selection_group)
        left_layout.addWidget(self.summary_label)
        left_layout.addWidget(self.fixed_parameters_label)
        left_layout.addWidget(self.parameter_summary_table, stretch=1)

        self.results_scroll_area = QScrollArea()
        self.results_scroll_area.setWidgetResizable(True)
        self.results_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.results_scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.results_scroll_area.setWidget(left_panel)

        self.plot_info_scroll = QScrollArea()
        self.plot_info_scroll.setWidgetResizable(True)
        self.plot_info_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.plot_info_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.plot_info_scroll.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        self.plot_info_scroll.setMinimumHeight(72)
        self.plot_info_scroll.setMaximumHeight(132)
        self.plot_info_scroll.setWidget(self.plot_info_label)

        right_panel = QWidget()
        right_panel.setMinimumWidth(0)
        right_panel.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.plot_actions_group)
        right_layout.addWidget(self.plot_info_scroll)
        right_layout.addWidget(self.plot_scroll, stretch=1)
        right_layout.setStretch(0, 0)
        right_layout.setStretch(1, 0)
        right_layout.setStretch(2, 1)

        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.content_splitter.setChildrenCollapsible(False)
        self.content_splitter.addWidget(self.results_scroll_area)
        self.content_splitter.addWidget(right_panel)
        self.content_splitter.setStretchFactor(0, 3)
        self.content_splitter.setStretchFactor(1, 2)
        self.content_splitter.setCollapsible(0, False)
        self.content_splitter.setCollapsible(1, False)

        buttons = QHBoxLayout()
        buttons.addWidget(self.clear_log_button)
        buttons.addWidget(self.open_output_button)
        buttons.addStretch(1)

        log_panel = QWidget()
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.addLayout(buttons)
        log_layout.addWidget(self.log_area)

        content_panel = QWidget()
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.content_splitter)

        self.content_scroll_area = QScrollArea()
        self.content_scroll_area.setWidgetResizable(True)
        self.content_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.content_scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.content_scroll_area.setWidget(content_panel)

        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        self.vertical_splitter.setChildrenCollapsible(True)
        self.vertical_splitter.addWidget(self.content_scroll_area)
        self.vertical_splitter.addWidget(log_panel)
        self.vertical_splitter.setStretchFactor(0, 5)
        self.vertical_splitter.setStretchFactor(1, 2)
        self.vertical_splitter.setCollapsible(0, False)
        self.vertical_splitter.setCollapsible(1, True)

        layout = QVBoxLayout(self)
        layout.addWidget(self.state_label)
        layout.addWidget(self.output_directory_label)
        layout.addWidget(self.vertical_splitter, stretch=1)

    def _wire_signals(self) -> None:
        self.load_latest_button.clicked.connect(self._load_latest_completed_run)
        self.open_run_button.clicked.connect(self._browse_run_directory)
        self.load_run_button.clicked.connect(self._load_run_from_edit)
        self.reload_button.clicked.connect(self._reload_current_run)
        self.clear_results_button.clicked.connect(self._clear_results)
        self.credible_level_combo.currentTextChanged.connect(
            self._handle_credible_level_changed
        )
        self.ignore_rows_spin.valueChanged.connect(self._handle_runtime_option_changed)
        self.filled_contours_checkbox.toggled.connect(
            self._handle_runtime_option_changed
        )
        self.select_all_button.clicked.connect(self.parameter_list.selectAll)
        self.clear_selection_button.clicked.connect(self.parameter_list.clearSelection)
        self.invert_selection_button.clicked.connect(self._invert_selection)
        self._wire_parameter_list_signals()
        self.plot_1d_button.clicked.connect(lambda: self._request_plot("1d"))
        self.plot_2d_button.clicked.connect(lambda: self._request_plot("2d"))
        self.triangle_plot_button.clicked.connect(
            lambda: self._request_plot("triangle")
        )
        self.export_summary_json_button.clicked.connect(
            lambda: self._export_summary("json")
        )
        self.export_summary_csv_button.clicked.connect(
            lambda: self._export_summary("csv")
        )
        self.save_plot_png_button.clicked.connect(
            lambda: self._save_current_plot(".png")
        )
        self.save_plot_pdf_button.clicked.connect(
            lambda: self._save_current_plot(".pdf")
        )
        self.clear_plot_button.clicked.connect(self._clear_plot)
        self.clear_log_button.clicked.connect(self.clear_log)

        self.results_controller.state_changed.connect(self._handle_controller_state)
        self.results_controller.request_rejected.connect(
            self.status_message_label.setText
        )
        self.results_controller.results_loaded.connect(self._handle_results_loaded)
        self.results_controller.summary_refreshed.connect(self._handle_results_loaded)
        self.results_controller.plot_ready.connect(self._handle_plot_ready)
        self.results_controller.summary_exported.connect(self._handle_summary_exported)
        self.results_controller.plot_exported.connect(self._handle_plot_exported)
        self.results_controller.failed.connect(self._handle_controller_failure)
        self.results_controller.cleared.connect(self._handle_results_cleared)

    def _load_options(self) -> PosteriorResultsLoadOptions:
        return PosteriorResultsLoadOptions(
            ignore_rows=float(self.ignore_rows_spin.value()),
            confidence_levels=(0.68, 0.95),
            filled_contours=self.filled_contours_checkbox.isChecked(),
        )

    def _load_latest_completed_run(self) -> None:
        self.results_controller.load_latest_completed_run(self._load_options())

    def _browse_run_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select completed run",
            str(self._current_output_directory or Path.cwd()),
        )
        if directory:
            self.run_directory_edit.setText(directory)

    def _load_run_from_edit(self) -> None:
        raw_path = self.run_directory_edit.text().strip()
        if not raw_path:
            self.status_message_label.setText(
                "Select a run directory before loading results."
            )
            return
        self.results_controller.load_run(Path(raw_path), self._load_options())

    def _reload_current_run(self) -> None:
        self.results_controller.reload(self._load_options())

    def _clear_results(self) -> None:
        self.results_controller.clear_results()

    def _handle_credible_level_changed(self, _text: str) -> None:
        if self._loaded_results is None:
            return
        self._populate_parameter_table(self._loaded_results)

    def _handle_runtime_option_changed(self, _value: object) -> None:
        self._options_dirty = (
            self._loaded_results is not None and not self._options_match()
        )
        if self._options_dirty:
            self.status_message_label.setText(
                "Reload the results to apply Ignore initial fraction "
                "or filled contours."
            )
        self._refresh_action_state()

    def _invert_selection(self) -> None:
        for index in range(self.parameter_list.count()):
            item = self.parameter_list.item(index)
            item.setSelected(not item.isSelected())

    def _request_plot(self, kind: str) -> None:
        if self._options_dirty:
            self.status_message_label.setText(
                "Reload the results before plotting with the new options."
            )
            return
        request = PosteriorPlotRequest(
            kind=kind,
            parameters=self.selected_parameters(),
            confidence_levels=(0.68, 0.95),
            title=self.plot_title_edit.text().strip() or None,
            legend_label=self.legend_label_edit.text().strip() or None,
        )
        self.results_controller.generate_plot(request)

    def _save_current_plot(self, suffix: str) -> None:
        if self._current_plot is None:
            self.status_message_label.setText(
                "Generate a plot before exporting files."
            )
            return
        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            f"Save {suffix.upper()}",
            f"plot{suffix}",
            f"*{suffix}",
        )
        if not selected_path:
            return
        destination = Path(selected_path).expanduser()
        if destination.exists() and not self._confirm_overwrite(destination):
            return
        self.results_controller.export_current_plot(destination)

    def _clear_plot(self) -> None:
        self._current_plot = None
        self.plot_preview_label.clear_preview("Preview unavailable.")
        self.plot_info_label.setText("No plot available.")
        self._refresh_action_state()

    def _export_summary(self, export_format: str) -> None:
        if self._options_dirty:
            self.status_message_label.setText(
                "Reload the results before exporting the summary."
            )
            return
        suffix = ".json" if export_format == "json" else ".csv"
        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            f"Export summary {export_format.upper()}",
            f"summary{suffix}",
            f"*{suffix}",
        )
        if not selected_path:
            return
        destination = Path(selected_path).expanduser()
        if destination.exists() and not self._confirm_overwrite(destination):
            return
        self.results_controller.export_summary(export_format, destination)

    def _handle_controller_state(self, state: str, message: str) -> None:
        self.state_label.setText(f"State: {state}")
        self.status_message_label.setText(message)
        busy = state in {STATE_LOADING, STATE_PLOTTING, STATE_EXPORTING}
        self._set_controls_busy(busy)
        if state == STATE_FAILED:
            self._apply_results_enabled(self._loaded_results is not None)
        elif state in {STATE_READY, STATE_CLEARED, STATE_NO_RUN_LOADED}:
            self._apply_results_enabled(self._loaded_results is not None)

    def _handle_results_loaded(self, payload: object) -> None:
        loaded = payload
        assert isinstance(loaded, LoadedPosteriorResults)
        self._loaded_results = loaded
        self._current_plot = None
        self._options_dirty = False
        self.run_label_value.setText(loaded.run_analysis.run_label)
        self.run_directory_value.setText(str(loaded.run_analysis.run_directory))
        self.datasets_value.setText(", ".join(loaded.run_analysis.datasets))
        sampled_count = sum(
            1
            for item in loaded.run_analysis.parameter_metadata
            if item.kind in {"sampled", "nuisance"}
        )
        self.sampled_count_value.setText(str(sampled_count))
        self.run_directory_edit.setText(str(loaded.run_analysis.run_directory))
        self.set_output_directory(loaded.run_analysis.run_directory)
        self._populate_summary(loaded)
        self._populate_parameter_list(loaded)
        self._populate_parameter_table(loaded)
        self._clear_plot()
        self._apply_results_enabled(True)

    def _handle_plot_ready(self, payload: object) -> None:
        plot = payload
        assert isinstance(plot, PosteriorPlotArtifact)
        self._current_plot = plot
        pixmap = QPixmap(str(plot.export.png_path))
        if pixmap.isNull():
            self.plot_preview_label.clear_preview(
                "Could not load the PNG preview."
            )
        else:
            self.plot_preview_label.set_preview_pixmap(pixmap)
        self.plot_info_label.setText(
            "\n".join(
                [
                    f"Type: {plot.kind}",
                    "Parameters: " + ", ".join(plot.parameters),
                    f"Credible levels: {plot.confidence_levels}",
                    f"Ignore initial fraction: {plot.ignore_rows}",
                    f"PNG: {plot.export.png_path}",
                    f"PDF: {plot.export.pdf_path}",
                ]
            )
        )
        self._refresh_action_state()

    def _handle_summary_exported(self, payload: object) -> None:
        artifact = payload
        self.append_log_line("stdout", f"Summary exported: {artifact}")

    def _handle_plot_exported(self, path: str) -> None:
        self.append_log_line("stdout", f"Plot exported: {path}")

    def _handle_controller_failure(self, message: str, details: str) -> None:
        if self.results_controller.loaded_results() is None:
            self.reset_loaded_results()
        self.status_message_label.setText(message)
        self.append_log_line("stderr", details.strip())

    def _handle_results_cleared(self) -> None:
        self.reset_loaded_results()
        self.summary_label.setText("No run loaded.")

    def _apply_results_enabled(self, enabled: bool) -> None:
        self.reload_button.setEnabled(enabled)
        self.clear_results_button.setEnabled(
            enabled or self.results_controller.is_busy()
        )
        self.parameter_list.setEnabled(enabled)
        self.credible_level_combo.setEnabled(enabled)
        self.ignore_rows_spin.setEnabled(True)
        self.plot_title_edit.setEnabled(enabled)
        self.legend_label_edit.setEnabled(enabled)
        self.filled_contours_checkbox.setEnabled(True)
        self._refresh_export_buttons(enabled)
        self._refresh_action_state()

    def _refresh_export_buttons(self, enabled: bool) -> None:
        is_busy = self.results_controller.is_busy()
        self.export_summary_json_button.setEnabled(enabled and not is_busy)
        self.export_summary_csv_button.setEnabled(enabled and not is_busy)
        self.save_plot_png_button.setEnabled(
            enabled and self._current_plot is not None
        )
        self.save_plot_pdf_button.setEnabled(
            enabled and self._current_plot is not None
        )

    def _populate_parameter_list(self, loaded: LoadedPosteriorResults) -> None:
        self.parameter_list.clear()
        for metadata in loaded.run_analysis.parameter_metadata:
            if metadata.kind == "derived":
                continue
            label = metadata.display_name
            if metadata.unit:
                label += f" [{metadata.unit}]"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, metadata.symbol)
            self.parameter_list.addItem(item)

    def _populate_summary(self, loaded: LoadedPosteriorResults) -> None:
        summary = loaded.summary
        fixed_values = ", ".join(
            f"{item.symbol}={item.value:g}" for item in summary.fixed_parameters
        ) or "none"
        self.summary_label.setText(
            "\n".join(
                [
                    f"Run label: {loaded.run_analysis.run_label}",
                    f"Run directory: {loaded.run_analysis.run_directory}",
                    "Datasets: " + ", ".join(loaded.run_analysis.datasets),
                    f"Chain root: {summary.chain_root}",
                    f"Sample rows: {summary.diagnostics.sample_rows}",
                    f"Chain count: {summary.diagnostics.chain_count}",
                    f"Ignore initial fraction: {summary.settings.ignore_rows}",
                ]
            )
        )
        self.fixed_parameters_label.setText(f"Fixed parameters: {fixed_values}")

    def _populate_parameter_table(self, loaded: LoadedPosteriorResults) -> None:
        summary = loaded.summary
        summary_by_symbol = {item.symbol: item for item in summary.sampled_parameters}
        selected_level = _SUPPORTED_CONFIDENCE_LEVELS[
            self.credible_level_combo.currentText()
        ]
        table_rows = [
            metadata
            for metadata in loaded.run_analysis.parameter_metadata
            if metadata.kind in {"sampled", "nuisance", "derived"}
        ]
        self.parameter_summary_table.setRowCount(len(table_rows))
        for row, metadata in enumerate(table_rows):
            posterior = summary_by_symbol.get(metadata.symbol)
            interval = _find_interval(
                posterior.credible_intervals if posterior is not None else (),
                selected_level,
            )
            values = [
                metadata.symbol,
                metadata.latex_label,
                _format_float(posterior.mean if posterior else None),
                _format_float(posterior.standard_deviation if posterior else None),
                _format_float(posterior.median if posterior else None),
                _format_float(interval.lower if interval else None),
                _format_float(interval.upper if interval else None),
                _format_float(posterior.maximum_posterior if posterior else None),
                "yes" if metadata.kind == "nuisance" else "no",
                "yes" if metadata.kind == "derived" else "no",
            ]
            for column, value in enumerate(values):
                self.parameter_summary_table.setItem(
                    row,
                    column,
                    QTableWidgetItem(value),
                )
        for column in (0, 1):
            self.parameter_summary_table.resizeColumnToContents(column)
        for column in range(2, self.parameter_summary_table.columnCount()):
            width = self.parameter_summary_table.columnWidth(column)
            self.parameter_summary_table.setColumnWidth(
                column, min(max(width, 84), 120)
            )

    def _refresh_action_state(self) -> None:
        selected_count = len(self.selected_parameters())
        busy = self.results_controller.is_busy()
        has_results = self._loaded_results is not None
        options_ready = not self._options_dirty
        self.plot_1d_button.setEnabled(
            has_results and not busy and options_ready and selected_count == 1
        )
        self.plot_2d_button.setEnabled(
            has_results and not busy and options_ready and selected_count == 2
        )
        self.triangle_plot_button.setEnabled(
            has_results and not busy and options_ready and selected_count >= 2
        )
        self.export_summary_json_button.setEnabled(
            has_results and not busy and options_ready
        )
        self.export_summary_csv_button.setEnabled(
            has_results and not busy and options_ready
        )
        self.save_plot_png_button.setEnabled(
            self._current_plot is not None and not busy
        )
        self.save_plot_pdf_button.setEnabled(
            self._current_plot is not None and not busy
        )
        self.clear_plot_button.setEnabled(self._current_plot is not None)

    def _set_controls_busy(self, busy: bool) -> None:
        self.load_latest_button.setEnabled(
            not busy and self._latest_completed_run is not None
        )
        self.open_run_button.setEnabled(not busy)
        self.load_run_button.setEnabled(not busy)
        self.reload_button.setEnabled(not busy and self._loaded_results is not None)
        self.clear_results_button.setEnabled(
            not busy and self._loaded_results is not None
        )
        self.parameter_list.setEnabled(not busy and self._loaded_results is not None)
        self.credible_level_combo.setEnabled(
            not busy and self._loaded_results is not None
        )
        self.plot_title_edit.setEnabled(
            not busy and self._loaded_results is not None
        )
        self.legend_label_edit.setEnabled(
            not busy and self._loaded_results is not None
        )
        self.ignore_rows_spin.setEnabled(not busy)
        self.filled_contours_checkbox.setEnabled(not busy)
        self.select_all_button.setEnabled(not busy and self.parameter_list.count() > 0)
        self.clear_selection_button.setEnabled(
            not busy and self.parameter_list.count() > 0
        )
        self.invert_selection_button.setEnabled(
            not busy and self.parameter_list.count() > 0
        )
        self._refresh_action_state()

    def _wire_parameter_list_signals(self) -> None:
        if self._list_signals_wired:
            return
        self._list_signals_wired = True
        self.parameter_list.itemSelectionChanged.connect(self._refresh_action_state)
        self.parameter_list.currentItemChanged.connect(
            lambda _current, _previous: self._schedule_action_state_refresh()
        )
        self.parameter_list.selectionModel().selectionChanged.connect(
            lambda _selected, _deselected: self._schedule_action_state_refresh()
        )
        self.parameter_list.model().rowsInserted.connect(
            lambda *_args: self._schedule_action_state_refresh()
        )
        self.parameter_list.model().rowsRemoved.connect(
            lambda *_args: self._schedule_action_state_refresh()
        )
        self.parameter_list.model().modelReset.connect(
            self._schedule_action_state_refresh
        )

    def _schedule_action_state_refresh(self) -> None:
        if self._selection_refresh_queued:
            return
        self._selection_refresh_queued = True
        QTimer.singleShot(0, self._flush_action_state_refresh)

    def _flush_action_state_refresh(self) -> None:
        self._selection_refresh_queued = False
        self._refresh_action_state()

    def _confirm_overwrite(self, path: Path) -> bool:
        answer = QMessageBox.question(
            self,
            "Overwrite file",
            f"The file {path} already exists. Do you want to overwrite it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _options_match(self) -> bool:
        if self._loaded_results is None:
            return True
        settings = self._loaded_results.summary.settings
        return (
            abs(settings.ignore_rows - float(self.ignore_rows_spin.value())) < 1e-9
            and settings.filled_contours
            == self.filled_contours_checkbox.isChecked()
        )

    def _flush_log_lines(self) -> None:
        if not self._pending_log_lines:
            return
        self.log_area.appendPlainText("\n".join(self._pending_log_lines))
        self._pending_log_lines.clear()
        cursor = self.log_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_area.setTextCursor(cursor)


def _find_interval(
    intervals: tuple[CredibleInterval, ...],
    confidence_level: float,
) -> CredibleInterval | None:
    for interval in intervals:
        if abs(interval.confidence_level - confidence_level) < 1e-9:
            return interval
    return None


def _format_float(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.6g}"
