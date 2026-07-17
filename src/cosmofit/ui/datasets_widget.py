"""Dataset selection widget for the first desktop milestone."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class DatasetsWidget(QWidget):
    """Edit dataset selections while preventing conflicting SN choices."""

    def __init__(self) -> None:
        super().__init__()

        self.cosmic_chronometers_checkbox = QCheckBox("cosmic chronometers")
        self.cosmic_chronometers_path_edit = QLineEdit()
        self.cosmic_chronometers_browse_button = QPushButton("Select CSV")
        self.pantheonplus_checkbox = QCheckBox("sn.pantheonplus")
        self.pantheonplusshoes_checkbox = QCheckBox("sn.pantheonplusshoes")
        self.union3_checkbox = QCheckBox("sn.union3")
        self.use_abs_mag_label = QLabel(
            "Supernova likelihoods currently marginalize over the "
            "absolute-magnitude calibration internally."
        )
        self.use_abs_mag_label.setWordWrap(True)
        self.use_abs_mag_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.use_abs_mag_label.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred,
        )
        self.packages_path_edit = QLineEdit()
        self.packages_path_edit.setReadOnly(True)
        self.packages_path_edit.setPlaceholderText("Unavailable")
        self.packages_path_edit.setToolTip("Cobaya packages path unavailable.")
        self.conflict_message = QTextEdit()
        self.conflict_message.setReadOnly(True)
        self.conflict_message.setPlaceholderText(
            "Dataset conflict messages will appear here."
        )

        self.cosmic_chronometers_browse_button.clicked.connect(
            self._select_cosmic_chronometer_csv
        )
        for checkbox in self._supernova_checkboxes():
            checkbox.clicked.connect(
                lambda checked, current=checkbox: self._handle_supernova_toggle(
                    current,
                    checked,
                )
            )

        chronometer_layout = QHBoxLayout()
        chronometer_layout.addWidget(self.cosmic_chronometers_path_edit)
        chronometer_layout.addWidget(self.cosmic_chronometers_browse_button)

        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form_layout.addRow(self.cosmic_chronometers_checkbox, chronometer_layout)
        form_layout.addRow(self.pantheonplus_checkbox)
        form_layout.addRow(self.pantheonplusshoes_checkbox)
        form_layout.addRow(self.union3_checkbox)
        form_layout.addRow("Supernovae", self.use_abs_mag_label)
        packages_row = QWidget()
        packages_layout = QGridLayout(packages_row)
        packages_layout.setContentsMargins(0, 0, 0, 0)
        packages_layout.addWidget(self.packages_path_edit, 0, 0)
        packages_layout.setColumnStretch(0, 1)
        form_layout.addRow("Cobaya packages", packages_row)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.addLayout(form_layout)
        content_layout.addWidget(QLabel("Messages"))
        content_layout.addWidget(self.conflict_message)
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

    def state(self) -> dict[str, object]:
        return {
            "cosmic_chronometers_selected": (
                self.cosmic_chronometers_checkbox.isChecked()
            ),
            "cosmic_chronometers_path": self.cosmic_chronometers_path_edit.text(),
            "sn.pantheonplus": self.pantheonplus_checkbox.isChecked(),
            "sn.pantheonplusshoes": self.pantheonplusshoes_checkbox.isChecked(),
            "sn.union3": self.union3_checkbox.isChecked(),
        }

    def set_state(self, state: dict[str, object]) -> None:
        self.cosmic_chronometers_checkbox.setChecked(
            bool(state.get("cosmic_chronometers_selected", False))
        )
        self.cosmic_chronometers_path_edit.setText(
            str(state.get("cosmic_chronometers_path", ""))
        )
        self.pantheonplus_checkbox.setChecked(bool(state.get("sn.pantheonplus", False)))
        self.pantheonplusshoes_checkbox.setChecked(
            bool(state.get("sn.pantheonplusshoes", False))
        )
        self.union3_checkbox.setChecked(bool(state.get("sn.union3", False)))
        self.conflict_message.clear()

    def set_packages_path(self, path: Path | None) -> None:
        if path is None:
            self.packages_path_edit.clear()
            self.packages_path_edit.setToolTip("Cobaya packages path unavailable.")
            return
        text = str(path)
        self.packages_path_edit.setText(text)
        self.packages_path_edit.setCursorPosition(0)
        self.packages_path_edit.setToolTip(text)

    def set_conflict_message(self, message: str) -> None:
        self.conflict_message.setPlainText(message)

    def _handle_supernova_toggle(self, toggled: QCheckBox, checked: bool) -> None:
        if not checked:
            return
        for checkbox in self._supernova_checkboxes():
            if checkbox is toggled:
                continue
            if checkbox.isChecked():
                toggled.setChecked(False)
                self.set_conflict_message(
                    "You can select only one default supernova dataset "
                    "to avoid overlap."
                )
                return
        self.conflict_message.clear()

    def _select_cosmic_chronometer_csv(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Select cosmic chronometer CSV",
            self.cosmic_chronometers_path_edit.text(),
            "CSV (*.csv);;All files (*)",
        )
        if path:
            self.cosmic_chronometers_path_edit.setText(path)

    def _supernova_checkboxes(self) -> tuple[QCheckBox, ...]:
        return (
            self.pantheonplus_checkbox,
            self.pantheonplusshoes_checkbox,
            self.union3_checkbox,
        )
