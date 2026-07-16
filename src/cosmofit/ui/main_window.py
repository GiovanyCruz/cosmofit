"""Main desktop window for the first PySide6 milestone."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from cosmofit.ui.datasets_widget import DatasetsWidget
from cosmofit.ui.execution_controller import (
    STATE_CANCELLED,
    STATE_CANCELLING,
    STATE_COMPLETED,
    STATE_FAILED,
    STATE_IDLE,
    STATE_RUNNING,
    STATE_STARTING,
    STATE_VALIDATING,
    ExecutionController,
)
from cosmofit.ui.model_widget import ModelWidget
from cosmofit.ui.parameter_table import ParameterTableWidget
from cosmofit.ui.project_controller import ProjectController
from cosmofit.ui.results_widget import ResultsWidget
from cosmofit.ui.sampler_widget import SamplerWidget
from cosmofit.ui.validation_presenter import ValidationFeedback, ValidationPresenter


class MainWindow(QMainWindow):
    """Usable desktop window for defining and validating a run configuration."""

    INITIAL_WINDOW_SIZE = (1200, 800)
    MINIMUM_PRACTICAL_WINDOW_SIZE = (800, 600)

    def __init__(
        self,
        *,
        execution_controller: ExecutionController | None = None,
    ) -> None:
        super().__init__()

        self.controller = ProjectController()
        self.validation_presenter = ValidationPresenter()
        self.execution_controller = execution_controller or ExecutionController(
            parent=self
        )
        self.current_project_path: Path | None = None
        self.current_run_directory: Path | None = None
        self.current_output_root: Path | None = None
        self.current_run_config = None
        self._close_after_cancel = False

        self.setWindowTitle("CosmoFit")
        self.resize(*self.INITIAL_WINDOW_SIZE)
        self.setMinimumSize(*self.MINIMUM_PRACTICAL_WINDOW_SIZE)

        self.model_widget = ModelWidget()
        self.parameter_table = ParameterTableWidget()
        self.datasets_widget = DatasetsWidget()
        self.sampler_widget = SamplerWidget()
        self.results_widget = ResultsWidget()

        self.validate_configuration_button = QPushButton("Validate configuration")
        self.run_fit_button = QPushButton("Run fit")
        self.cancel_run_button = QPushButton("Cancel run")
        self.cancel_run_button.setEnabled(False)
        self.save_project_button = QPushButton("Save project")
        self.open_project_button = QPushButton("Open project")
        self.reset_form_button = QPushButton("Reset form")
        self.load_lcdm_button = QPushButton("Load LCDM example")

        self.validation_summary_label = QLabel("Not validated.")
        self.validation_summary_label.setWordWrap(True)
        self.details_toggle_button = QToolButton()
        self.details_toggle_button.setText("Show technical details")
        self.details_toggle_button.setCheckable(True)
        self.details_toggle_button.setChecked(False)
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setVisible(False)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.model_widget, "Model")
        self.tabs.addTab(self.parameter_table, "Parameters")
        self.tabs.addTab(self.datasets_widget, "Datasets")
        self.tabs.addTab(self.sampler_widget, "Sampler")
        self.tabs.addTab(self.results_widget, "Results")
        self.tabs.setTabEnabled(self.tabs.indexOf(self.results_widget), False)

        button_layout = QGridLayout()
        top_buttons = (
            self.validate_configuration_button,
            self.run_fit_button,
            self.cancel_run_button,
            self.save_project_button,
            self.open_project_button,
            self.reset_form_button,
            self.load_lcdm_button,
        )
        for index, button in enumerate(top_buttons):
            button_layout.addWidget(button, index // 4, index % 4)
        button_layout.setColumnStretch(3, 1)

        validation_group = QGroupBox("Validation")
        validation_layout = QVBoxLayout(validation_group)
        validation_layout.addWidget(self.validation_summary_label)
        validation_layout.addWidget(self.details_toggle_button)
        validation_layout.addWidget(self.details_text)
        self.details_text.setMinimumHeight(0)

        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.addLayout(button_layout)
        central_layout.addWidget(self.tabs)
        central_layout.addWidget(validation_group)
        self.setCentralWidget(central_widget)

        self.model_widget.validate_button.clicked.connect(self.validate_model)
        self.validate_configuration_button.clicked.connect(self.validate_configuration)
        self.run_fit_button.clicked.connect(self.start_run)
        self.cancel_run_button.clicked.connect(self.cancel_run)
        self.save_project_button.clicked.connect(self.save_project)
        self.open_project_button.clicked.connect(self.open_project)
        self.reset_form_button.clicked.connect(self.reset_form)
        self.load_lcdm_button.clicked.connect(self.load_lcdm_example)
        self.details_toggle_button.toggled.connect(self.details_text.setVisible)
        self.results_widget.clear_log_button.clicked.connect(self.results_widget.clear_log)
        self.results_widget.open_output_button.clicked.connect(self.open_output_folder)

        self.execution_controller.state_changed.connect(self._handle_execution_state)
        self.execution_controller.log_message.connect(self.results_widget.append_log_line)
        self.execution_controller.completed.connect(self._handle_run_completed)
        self.execution_controller.failed.connect(self._handle_run_failed)
        self.execution_controller.cancelled.connect(self._handle_run_cancelled)
        self.execution_controller.final_run_directory.connect(
            self._handle_final_run_directory
        )
        self.execution_controller.request_rejected.connect(self._handle_request_rejected)
        self.results_widget.results_controller.results_loaded.connect(
            self._handle_results_run_loaded
        )

        self.reset_form()
        self.datasets_widget.set_packages_path(self.controller.cobaya_packages_path())

    def current_state(self) -> dict[str, object]:
        return {
            "model": self.model_widget.state(),
            "parameters": self.parameter_table.parameters_state(),
            "datasets": self.datasets_widget.state(),
            "sampler": self.sampler_widget.state(),
        }

    def apply_state(self, state: dict[str, object]) -> None:
        self.model_widget.set_state(state["model"])
        self.parameter_table.set_parameters_state(state["parameters"])
        self.datasets_widget.set_state(state["datasets"])
        self.sampler_widget.set_state(state["sampler"])

    def validate_model(self) -> None:
        self._set_ui_state(STATE_VALIDATING)
        try:
            result = self.controller.validate_model(self.current_state())
        except Exception as error:
            feedback = self.validation_presenter.present_error(
                error,
                fallback="Configuration validation failed.",
            )
            self.model_widget.set_validation_message(feedback.summary)
            self._apply_feedback(feedback)
            self._set_ui_state(STATE_IDLE)
            return

        feedback = self.validation_presenter.present_success(result.summary)
        self.model_widget.set_validation_message(feedback.summary)
        self._apply_feedback(feedback)
        self._set_ui_state(STATE_IDLE)

    def validate_configuration(self) -> None:
        self._set_ui_state(STATE_VALIDATING)
        try:
            result = self.controller.validate_configuration(self.current_state())
        except Exception as error:
            feedback = self.validation_presenter.present_error(
                error,
                fallback="Configuration validation failed.",
            )
            self._apply_feedback(feedback)
            self._set_ui_state(STATE_IDLE)
            return

        feedback = self.validation_presenter.present_success(result.summary)
        self._apply_feedback(feedback)
        self._set_ui_state(STATE_IDLE)

    def start_run(self) -> None:
        self._set_ui_state(STATE_VALIDATING)
        try:
            result = self.controller.validate_configuration(self.current_state())
        except Exception as error:
            feedback = self.validation_presenter.present_error(
                error,
                fallback="Could not start the execution.",
            )
            self._apply_feedback(feedback)
            self._set_ui_state(STATE_IDLE)
            return

        self.current_run_config = result.run_config
        self.current_output_root = result.run_config.runtime.output_directory.resolve()
        self.current_run_directory = None
        self.results_widget.clear_log()
        self.results_widget.reset_loaded_results()
        self.results_widget.set_output_directory(None)
        self.tabs.setTabEnabled(self.tabs.indexOf(self.results_widget), True)
        self.tabs.setCurrentWidget(self.results_widget)
        if self.execution_controller.start_run(result.run_config):
            self._apply_feedback(
                self.validation_presenter.present_success(
                    "Configuration is valid. Starting execution."
                )
            )
        else:
            self._set_ui_state(STATE_IDLE)

    def cancel_run(self) -> None:
        if self.execution_controller.cancel_run():
            self.statusBar().showMessage("Requesting cancellation...", 5000)

    def save_project(self) -> None:
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save project",
            str(self.current_project_path or Path("cosmofit_project.json")),
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            self.controller.save_project(Path(path), self.current_state())
        except Exception as error:
            feedback = self.validation_presenter.present_error(
                error,
                fallback="Could not save the project.",
            )
            self._apply_feedback(feedback)
            return

        self.current_project_path = Path(path)
        feedback = self.validation_presenter.present_success(
            f"Project saved to {self.current_project_path}."
        )
        self._apply_feedback(feedback)

    def open_project(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Open project",
            str(self.current_project_path or Path(".")),
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            state = self.controller.load_project(Path(path))
        except Exception as error:
            feedback = self.validation_presenter.present_error(
                error,
                fallback="Could not open the project.",
            )
            self._apply_feedback(feedback)
            return

        self.current_project_path = Path(path)
        self.apply_state(state)
        self.current_run_directory = None
        self.results_widget.reset_loaded_results()
        self.results_widget.set_latest_completed_run(None)
        self.results_widget.set_output_directory(None)
        feedback = self.validation_presenter.present_success(
            f"Project loaded from {self.current_project_path}."
        )
        self._apply_feedback(feedback)

    def reset_form(self) -> None:
        state = self.controller.default_state()
        self.apply_state(state)
        self.model_widget.set_validation_message("")
        self.datasets_widget.set_packages_path(self.controller.cobaya_packages_path())
        self.datasets_widget.set_conflict_message("")
        self._apply_feedback(
            self.validation_presenter.present_success(
                "Form reset."
            )
        )
        self.current_run_directory = None
        self.results_widget.set_execution_state(STATE_IDLE)
        self.results_widget.reset_loaded_results()
        self.results_widget.set_latest_completed_run(None)
        self.results_widget.set_output_directory(None)

    def load_lcdm_example(self) -> None:
        state = self.controller.lcdm_example_state()
        self.apply_state(state)
        feedback = self.validation_presenter.present_success(
            "Loaded the predefined LCDM example."
        )
        self._apply_feedback(feedback)

    def _apply_feedback(self, feedback: ValidationFeedback) -> None:
        self.validation_summary_label.setText(feedback.summary)
        color = "#0d652d" if feedback.success else "#9b1c1c"
        self.validation_summary_label.setStyleSheet(f"color: {color};")
        self.details_text.setPlainText(feedback.details)
        self.statusBar().showMessage(feedback.summary, 5000)

    def open_output_folder(self) -> None:
        if self.current_run_directory is None:
            self._apply_feedback(
                self.validation_presenter.present_error(
                    ValueError("No output directory is available."),
                    fallback="No output folder is available.",
                )
            )
            return
        if not self.current_run_directory.is_dir():
            self._apply_feedback(
                self.validation_presenter.present_error(
                    FileNotFoundError(str(self.current_run_directory)),
                    fallback="The output folder does not exist.",
                )
            )
            return
        if self.current_output_root is not None:
            try:
                self.current_run_directory.resolve().relative_to(
                    self.current_output_root.resolve()
                )
            except ValueError:
                self._apply_feedback(
                    self.validation_presenter.present_error(
                        ValueError(
                            "Run directory is outside the configured output root."
                        ),
                        fallback="The final folder is outside the configured path.",
                    )
                )
                return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.current_run_directory)))

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self.execution_controller.has_active_run():
            event.accept()
            return

        answer = QMessageBox.question(
            self,
            "Close CosmoFit",
            (
                "An execution is active. "
                "Do you want to cancel it and close the application?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            event.ignore()
            return

        self._close_after_cancel = True
        self.execution_controller.cancel_run()
        event.ignore()

    def _handle_execution_state(self, state: str, message: str) -> None:
        self._set_ui_state(state)
        self.results_widget.set_execution_state(state)
        summary = {
            STATE_STARTING: "Starting the Cobaya worker.",
            STATE_RUNNING: "The run is in progress.",
            STATE_CANCELLING: "Cancelling the active run.",
            STATE_COMPLETED: "The run completed successfully.",
            STATE_FAILED: "The run failed.",
            STATE_CANCELLED: "The run was cancelled.",
            STATE_IDLE: "No active execution.",
            STATE_VALIDATING: "Validating the configuration.",
        }.get(state, message)
        self.statusBar().showMessage(summary, 5000)

    def _handle_run_completed(self, run_directory: str) -> None:
        self.current_run_directory = Path(run_directory)
        self.results_widget.set_latest_completed_run(self.current_run_directory)
        if self.current_run_config is not None:
            sampled = tuple(
                parameter.symbol
                for parameter in self.current_run_config.parameters
                if parameter.role == "sampled"
            )
            datasets = tuple(
                dataset.kind for dataset in self.current_run_config.datasets
            )
            self.results_widget.set_placeholder_summary(
                run_label=self.current_run_config.runtime.run_label,
                completion_state=STATE_COMPLETED,
                output_directory=self.current_run_directory,
                datasets=datasets,
                sampled_parameters=sampled,
            )
        self.results_widget.set_output_directory(self.current_run_directory)
        self.tabs.setTabEnabled(self.tabs.indexOf(self.results_widget), True)
        if self._close_after_cancel:
            self._close_after_cancel = False
            self.close()

    def _handle_run_failed(self, message: str) -> None:
        self.results_widget.reset_loaded_results()
        self._apply_feedback(
            self.validation_presenter.present_error(
                RuntimeError(message),
                fallback="Cobaya execution failed.",
            )
        )
        if self._close_after_cancel:
            self._close_after_cancel = False
            self.close()

    def _handle_run_cancelled(self) -> None:
        self.results_widget.set_execution_state(STATE_CANCELLED)
        self.results_widget.reset_loaded_results()
        if self._close_after_cancel:
            self._close_after_cancel = False
            self.close()

    def _handle_final_run_directory(self, run_directory: str) -> None:
        self.current_run_directory = Path(run_directory)
        self.results_widget.set_output_directory(self.current_run_directory)

    def _handle_results_run_loaded(self, payload: object) -> None:
        run_analysis = getattr(payload, "run_analysis", None)
        if run_analysis is None:
            return
        self.current_run_directory = Path(run_analysis.run_directory)

    def _handle_request_rejected(self, message: str) -> None:
        self._apply_feedback(
            self.validation_presenter.present_error(
                RuntimeError(message),
                fallback="Could not start the run.",
            )
        )
        self._set_ui_state(STATE_IDLE)

    def _set_ui_state(self, state: str) -> None:
        is_active = state in {STATE_STARTING, STATE_RUNNING, STATE_CANCELLING}
        can_cancel = state in {STATE_STARTING, STATE_RUNNING}
        for widget in (
            self.model_widget,
            self.parameter_table,
            self.datasets_widget,
            self.sampler_widget,
        ):
            widget.setEnabled(not is_active)
        self.model_widget.validate_button.setEnabled(not is_active)
        self.validate_configuration_button.setEnabled(not is_active)
        self.run_fit_button.setEnabled(not is_active)
        self.save_project_button.setEnabled(not is_active)
        self.open_project_button.setEnabled(not is_active)
        self.reset_form_button.setEnabled(not is_active)
        self.load_lcdm_button.setEnabled(not is_active)
        self.cancel_run_button.setEnabled(can_cancel)
        self.tabs.setTabEnabled(
            self.tabs.indexOf(self.results_widget),
            is_active or state in {STATE_COMPLETED, STATE_FAILED, STATE_CANCELLED},
        )


def build_main_window() -> MainWindow:
    """Construct the main application window."""

    window = MainWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    return window
