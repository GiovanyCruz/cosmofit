"""Sampler and runtime settings widget."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class SamplerWidget(QWidget):
    """Edit sampler settings for the first Cobaya MCMC milestone."""

    def __init__(self) -> None:
        super().__init__()

        self.sampler_kind_edit = QLineEdit("cobaya_mcmc")
        self.sampler_kind_edit.setReadOnly(True)
        self.run_label_edit = QLineEdit()
        self.output_directory_edit = QLineEdit()
        self.output_directory_button = QPushButton("Select directory")
        self.seed_edit = QLineEdit()
        self.max_samples_edit = QLineEdit()
        self.burn_in_edit = QLineEdit()
        self.rminus1_stop_edit = QLineEdit()
        self.rminus1_cl_stop_edit = QLineEdit()
        self.learn_proposal_checkbox = QCheckBox("learn proposal")
        self.overwrite_checkbox = QCheckBox("overwrite")
        self.overwrite_checkbox.setChecked(False)

        self.output_directory_button.clicked.connect(self._select_output_directory)

        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_directory_edit)
        output_layout.addWidget(self.output_directory_button)

        content = QWidget()
        form_layout = QFormLayout(content)
        form_layout.addRow("Sampler", self.sampler_kind_edit)
        form_layout.addRow("Run label", self.run_label_edit)
        form_layout.addRow("Output directory", output_layout)
        form_layout.addRow("Random seed", self.seed_edit)
        form_layout.addRow("Maximum samples", self.max_samples_edit)
        form_layout.addRow("Burn in", self.burn_in_edit)
        form_layout.addRow("Rminus1_stop", self.rminus1_stop_edit)
        form_layout.addRow("Rminus1_cl_stop", self.rminus1_cl_stop_edit)
        form_layout.addRow(self.learn_proposal_checkbox)
        form_layout.addRow(self.overwrite_checkbox)

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

    def state(self) -> dict[str, object]:
        return {
            "sampler_kind": self.sampler_kind_edit.text(),
            "run_label": self.run_label_edit.text(),
            "output_directory": self.output_directory_edit.text(),
            "seed": self.seed_edit.text(),
            "max_samples": self.max_samples_edit.text(),
            "burn_in": self.burn_in_edit.text(),
            "Rminus1_stop": self.rminus1_stop_edit.text(),
            "Rminus1_cl_stop": self.rminus1_cl_stop_edit.text(),
            "learn_proposal": self.learn_proposal_checkbox.isChecked(),
            "overwrite": self.overwrite_checkbox.isChecked(),
        }

    def set_state(self, state: dict[str, object]) -> None:
        self.sampler_kind_edit.setText(str(state.get("sampler_kind", "cobaya_mcmc")))
        self.run_label_edit.setText(str(state.get("run_label", "")))
        self.output_directory_edit.setText(str(state.get("output_directory", "")))
        self.seed_edit.setText(str(state.get("seed", "")))
        self.max_samples_edit.setText(str(state.get("max_samples", "")))
        self.burn_in_edit.setText(str(state.get("burn_in", "")))
        self.rminus1_stop_edit.setText(str(state.get("Rminus1_stop", "")))
        self.rminus1_cl_stop_edit.setText(str(state.get("Rminus1_cl_stop", "")))
        self.learn_proposal_checkbox.setChecked(
            bool(state.get("learn_proposal", False))
        )
        self.overwrite_checkbox.setChecked(bool(state.get("overwrite", False)))

    def _select_output_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select output directory",
            self.output_directory_edit.text(),
        )
        if path:
            self.output_directory_edit.setText(path)
