"""Main desktop window for the first PySide6 milestone."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from cosmofit.ui.datasets_widget import DatasetsWidget
from cosmofit.ui.model_widget import ModelWidget
from cosmofit.ui.parameter_table import ParameterTableWidget
from cosmofit.ui.project_controller import ProjectController
from cosmofit.ui.results_widget import ResultsWidget
from cosmofit.ui.sampler_widget import SamplerWidget
from cosmofit.ui.validation_presenter import ValidationFeedback, ValidationPresenter


class MainWindow(QMainWindow):
    """Usable desktop window for defining and validating a run configuration."""

    def __init__(self) -> None:
        super().__init__()

        self.controller = ProjectController()
        self.validation_presenter = ValidationPresenter()
        self.current_project_path: Path | None = None

        self.setWindowTitle("CosmoFit")
        self.resize(1200, 760)

        self.model_widget = ModelWidget()
        self.parameter_table = ParameterTableWidget()
        self.datasets_widget = DatasetsWidget()
        self.sampler_widget = SamplerWidget()
        self.results_widget = ResultsWidget()
        self.results_widget.setEnabled(False)

        self.validate_configuration_button = QPushButton("Validar configuracion")
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

        button_layout = QHBoxLayout()
        for button in (
            self.validate_configuration_button,
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
        self.save_project_button.clicked.connect(self.save_project)
        self.open_project_button.clicked.connect(self.open_project)
        self.reset_form_button.clicked.connect(self.reset_form)
        self.load_lcdm_button.clicked.connect(self.load_lcdm_example)
        self.details_toggle_button.toggled.connect(self.details_text.setVisible)

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
        try:
            result = self.controller.validate_model(self.current_state())
        except Exception as error:
            feedback = self.validation_presenter.present_error(
                error,
                fallback="No se pudo validar el modelo H(z).",
            )
            self.model_widget.set_validation_message(feedback.summary)
            self._apply_feedback(feedback)
            return

        feedback = self.validation_presenter.present_success(result.summary)
        self.model_widget.set_validation_message(feedback.summary)
        self._apply_feedback(feedback)

    def validate_configuration(self) -> None:
        try:
            result = self.controller.validate_configuration(self.current_state())
        except Exception as error:
            feedback = self.validation_presenter.present_error(
                error,
                fallback="No se pudo validar la configuracion.",
            )
            self._apply_feedback(feedback)
            return

        feedback = self.validation_presenter.present_success(result.summary)
        self._apply_feedback(feedback)

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


def build_main_window() -> MainWindow:
    """Construct the main application window."""

    window = MainWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    return window
