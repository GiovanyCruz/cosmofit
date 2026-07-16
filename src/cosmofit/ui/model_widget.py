"""Model configuration widget."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
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
        self.geometry_label = QLabel("Geometry: flat")
        self.functions_label = QLabel(", ".join(ALLOWED_FUNCTIONS))
        self.functions_label.setWordWrap(True)
        self.preview_min_edit = QLineEdit("0.0")
        self.preview_max_edit = QLineEdit("2.0")
        self.validate_button = QPushButton("Validate model")
        self.status_area = QTextEdit()
        self.status_area.setReadOnly(True)
        self.status_area.setPlaceholderText(
            "Model validation status will appear here."
        )

        preview_layout = QHBoxLayout()
        preview_layout.addWidget(QLabel("z minimum"))
        preview_layout.addWidget(self.preview_min_edit)
        preview_layout.addWidget(QLabel("z maximum"))
        preview_layout.addWidget(self.preview_max_edit)

        form_layout = QFormLayout()
        form_layout.addRow("Model name", self.model_name_edit)
        form_layout.addRow("H(z) expression", self.expression_edit)
        form_layout.addRow("Geometry", self.geometry_label)
        form_layout.addRow("Approved functions", self.functions_label)
        form_layout.addRow("Optional preview range", preview_layout)

        status_group = QGroupBox("Validation status")
        status_layout = QVBoxLayout(status_group)
        status_layout.addWidget(self.status_area)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.addLayout(form_layout)
        content_layout.addWidget(self.validate_button)
        content_layout.addWidget(status_group)
        content_layout.addStretch(1)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setWidget(content)

        layout = QVBoxLayout(self)
        layout.addWidget(self.scroll_area)

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
