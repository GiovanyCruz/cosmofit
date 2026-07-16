"""Model configuration widget."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from cosmofit.application import ALLOWED_FUNCTIONS


class ModelWidget(QWidget):
    """Edit the H(z) model definition for the current run."""

    def __init__(self) -> None:
        super().__init__()

        self.model_name_edit = QLineEdit("hz_expression_flat")
        self.model_name_edit.setReadOnly(True)
        self.expression_edit = QLineEdit()
        self.geometry_label = QLabel("Geometria: plana")
        self.functions_label = QLabel(", ".join(ALLOWED_FUNCTIONS))
        self.preview_min_edit = QLineEdit("0.0")
        self.preview_max_edit = QLineEdit("2.0")
        self.validate_button = QPushButton("Validar modelo")
        self.status_area = QTextEdit()
        self.status_area.setReadOnly(True)
        self.status_area.setPlaceholderText(
            "El estado de validacion del modelo aparecera aqui."
        )

        preview_layout = QHBoxLayout()
        preview_layout.addWidget(QLabel("z minimo"))
        preview_layout.addWidget(self.preview_min_edit)
        preview_layout.addWidget(QLabel("z maximo"))
        preview_layout.addWidget(self.preview_max_edit)

        form_layout = QFormLayout()
        form_layout.addRow("Nombre del modelo", self.model_name_edit)
        form_layout.addRow("Expresion H(z)", self.expression_edit)
        form_layout.addRow("Geometria", self.geometry_label)
        form_layout.addRow("Funciones aprobadas", self.functions_label)
        form_layout.addRow("Rango opcional de vista previa", preview_layout)

        status_group = QGroupBox("Estado de validacion")
        status_layout = QVBoxLayout(status_group)
        status_layout.addWidget(self.status_area)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(self.validate_button)
        layout.addWidget(status_group)

    def state(self) -> dict[str, str]:
        return {
            "model_name": self.model_name_edit.text(),
            "expression": self.expression_edit.text(),
            "preview_min": self.preview_min_edit.text(),
            "preview_max": self.preview_max_edit.text(),
        }

    def set_state(self, state: dict[str, str]) -> None:
        self.model_name_edit.setText(state.get("model_name", "hz_expression_flat"))
        self.expression_edit.setText(state.get("expression", ""))
        self.preview_min_edit.setText(state.get("preview_min", "0.0"))
        self.preview_max_edit.setText(state.get("preview_max", "2.0"))

    def set_validation_message(self, message: str) -> None:
        self.status_area.setPlainText(message)
