"""Dataset selection widget for the first desktop milestone."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
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
        self.cosmic_chronometers_browse_button = QPushButton("Seleccionar CSV")
        self.pantheonplus_checkbox = QCheckBox("sn.pantheonplus")
        self.pantheonplusshoes_checkbox = QCheckBox("sn.pantheonplusshoes")
        self.union3_checkbox = QCheckBox("sn.union3")
        self.use_abs_mag_label = QLabel("use_abs_mag = false en esta version")
        self.packages_path_label = QLabel("Ruta de paquetes Cobaya: no disponible")
        self.conflict_message = QTextEdit()
        self.conflict_message.setReadOnly(True)
        self.conflict_message.setPlaceholderText(
            "Los conflictos de conjuntos de datos se mostraran aqui."
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
        form_layout.addRow(self.cosmic_chronometers_checkbox, chronometer_layout)
        form_layout.addRow(self.pantheonplus_checkbox)
        form_layout.addRow(self.pantheonplusshoes_checkbox)
        form_layout.addRow(self.union3_checkbox)
        form_layout.addRow("Supernovas", self.use_abs_mag_label)
        form_layout.addRow("Paquetes Cobaya", self.packages_path_label)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(QLabel("Mensajes"))
        layout.addWidget(self.conflict_message)

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
            self.packages_path_label.setText("Ruta de paquetes Cobaya: no disponible")
            return
        self.packages_path_label.setText(f"Ruta de paquetes Cobaya: {path}")

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
                    "Solo puedes seleccionar un conjunto de supernovas "
                    "por defecto para evitar solapamientos."
                )
                return
        self.conflict_message.clear()

    def _select_cosmic_chronometer_csv(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Seleccionar CSV de cronometros cosmicos",
            self.cosmic_chronometers_path_edit.text(),
            "CSV (*.csv);;Todos los archivos (*)",
        )
        if path:
            self.cosmic_chronometers_path_edit.setText(path)

    def _supernova_checkboxes(self) -> tuple[QCheckBox, ...]:
        return (
            self.pantheonplus_checkbox,
            self.pantheonplusshoes_checkbox,
            self.union3_checkbox,
        )
