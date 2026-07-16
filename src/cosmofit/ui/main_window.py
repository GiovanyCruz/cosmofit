"""Main desktop window for the first PySide6 milestone."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
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
        self.resize(1200, 760)

        self.model_widget = ModelWidget()
        self.parameter_table = ParameterTableWidget()
        self.datasets_widget = DatasetsWidget()
        self.sampler_widget = SamplerWidget()
        self.results_widget = ResultsWidget()

        self.validate_configuration_button = QPushButton("Validar configuracion")
        self.run_fit_button = QPushButton("Run fit")
        self.cancel_run_button = QPushButton("Cancel run")
        self.cancel_run_button.setEnabled(False)
        self.save_project_button = QPushButton("Guardar proyecto")
        self.open_project_button = QPushButton("Abrir proyecto")
        self.reset_form_button = QPushButton("Restablecer formulario")
        self.load_lcdm_button = QPushButton("Cargar ejemplo LCDM")

        self.validation_summary_label = QLabel("Sin validar.")
        self.validation_summary_label.setWordWrap(True)
        self.details_toggle_button = QToolButton()
        self.details_toggle_button.setText("Mostrar detalles tecnicos")
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

        button_layout = QHBoxLayout()
        for button in (
            self.validate_configuration_button,
            self.run_fit_button,
            self.cancel_run_button,
            self.save_project_button,
            self.open_project_button,
            self.reset_form_button,
            self.load_lcdm_button,
        ):
            button_layout.addWidget(button)
        button_layout.addStretch(1)

        validation_group = QGroupBox("Validacion")
        validation_layout = QVBoxLayout(validation_group)
        validation_layout.addWidget(self.validation_summary_label)
        validation_layout.addWidget(self.details_toggle_button)
        validation_layout.addWidget(self.details_text)

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
                fallback="No se pudo validar el modelo H(z).",
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
                fallback="No se pudo validar la configuracion.",
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
                fallback="No se pudo iniciar la ejecucion.",
            )
            self._apply_feedback(feedback)
            self._set_ui_state(STATE_IDLE)
            return

        self.current_run_config = result.run_config
        self.current_output_root = result.run_config.runtime.output_directory.resolve()
        self.current_run_directory = None
        self.results_widget.clear_log()
        self.results_widget.set_output_directory(None)
        self.tabs.setTabEnabled(self.tabs.indexOf(self.results_widget), True)
        self.tabs.setCurrentWidget(self.results_widget)
        if self.execution_controller.start_run(result.run_config):
            self._apply_feedback(
                self.validation_presenter.present_success(
                    "Configuracion validada. Iniciando la ejecucion."
                )
            )
        else:
            self._set_ui_state(STATE_IDLE)

    def cancel_run(self) -> None:
        if self.execution_controller.cancel_run():
            self.statusBar().showMessage("Solicitando cancelacion...", 5000)

    def save_project(self) -> None:
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Guardar proyecto",
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
                fallback="No se pudo guardar el proyecto.",
            )
            self._apply_feedback(feedback)
            return

        self.current_project_path = Path(path)
        feedback = self.validation_presenter.present_success(
            f"Proyecto guardado en {self.current_project_path}."
        )
        self._apply_feedback(feedback)

    def open_project(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Abrir proyecto",
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
                fallback="No se pudo abrir el proyecto.",
            )
            self._apply_feedback(feedback)
            return

        self.current_project_path = Path(path)
        self.apply_state(state)
        feedback = self.validation_presenter.present_success(
            f"Proyecto cargado desde {self.current_project_path}."
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
                "Formulario restablecido."
            )
        )
        self.results_widget.set_execution_state(STATE_IDLE)
        self.results_widget.set_output_directory(None)

    def load_lcdm_example(self) -> None:
        state = self.controller.lcdm_example_state()
        self.apply_state(state)
        feedback = self.validation_presenter.present_success(
            "Se cargo el ejemplo LCDM predefinido."
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
                    fallback="No hay una carpeta de salida disponible.",
                )
            )
            return
        if not self.current_run_directory.is_dir():
            self._apply_feedback(
                self.validation_presenter.present_error(
                    FileNotFoundError(str(self.current_run_directory)),
                    fallback="La carpeta de salida no existe.",
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
                        fallback="La carpeta final esta fuera de la ruta configurada.",
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
            "Cerrar CosmoFit",
            (
                "Hay una ejecucion activa. "
                "Quieres cancelarla y cerrar la aplicacion?"
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
            STATE_STARTING: "Iniciando el worker de Cobaya.",
            STATE_RUNNING: "La corrida esta en progreso.",
            STATE_CANCELLING: "Cancelando la corrida activa.",
            STATE_COMPLETED: "La corrida termino correctamente.",
            STATE_FAILED: "La corrida fallo.",
            STATE_CANCELLED: "La corrida fue cancelada.",
            STATE_IDLE: "Sin ejecucion activa.",
            STATE_VALIDATING: "Validando la configuracion.",
        }.get(state, message)
        self.statusBar().showMessage(summary, 5000)

    def _handle_run_completed(self, run_directory: str) -> None:
        self.current_run_directory = Path(run_directory)
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
        self._apply_feedback(
            self.validation_presenter.present_error(
                RuntimeError(message),
                fallback="La ejecucion de Cobaya fallo.",
            )
        )
        if self._close_after_cancel:
            self._close_after_cancel = False
            self.close()

    def _handle_run_cancelled(self) -> None:
        self.results_widget.set_execution_state(STATE_CANCELLED)
        if self._close_after_cancel:
            self._close_after_cancel = False
            self.close()

    def _handle_final_run_directory(self, run_directory: str) -> None:
        self.current_run_directory = Path(run_directory)
        self.results_widget.set_output_directory(self.current_run_directory)

    def _handle_request_rejected(self, message: str) -> None:
        self._apply_feedback(
            self.validation_presenter.present_error(
                RuntimeError(message),
                fallback="No se pudo iniciar la corrida.",
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
