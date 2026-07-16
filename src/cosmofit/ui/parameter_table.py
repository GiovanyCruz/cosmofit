"""Parameter table widget for arbitrary cosmological parameter rows."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)


class ParameterTableWidget(QWidget):
    """Editable parameter table with role-dependent fields."""

    COLUMN_NAME = 0
    COLUMN_LABEL = 1
    COLUMN_ROLE = 2
    COLUMN_PRIOR_MIN = 3
    COLUMN_PRIOR_MAX = 4
    COLUMN_REFERENCE = 5
    COLUMN_PROPOSAL = 6
    COLUMN_FIXED_VALUE = 7
    COLUMN_UNIT = 8
    COLUMN_NUISANCE = 9

    def __init__(self) -> None:
        super().__init__()

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            [
                "Nombre",
                "Etiqueta",
                "Rol",
                "Prior min",
                "Prior max",
                "Referencia",
                "Propuesta",
                "Valor fijo",
                "Unidad",
                "Nuisance",
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)

        self.add_button = QPushButton("Agregar parametro")
        self.remove_button = QPushButton("Eliminar parametro seleccionado")
        self.add_button.clicked.connect(self.add_parameter_row)
        self.remove_button.clicked.connect(self.remove_selected_parameter)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(button_layout)

    def add_parameter_row(self, state: dict[str, Any] | None = None) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        name_edit = QLineEdit(state.get("name", "") if state else "")
        label_edit = QLineEdit(state.get("label", "") if state else "")
        role_box = QComboBox()
        role_box.addItems(["sampled", "fixed"])
        role_box.setCurrentText(state.get("role", "sampled") if state else "sampled")
        prior_min_edit = QLineEdit(state.get("prior_min", "") if state else "")
        prior_max_edit = QLineEdit(state.get("prior_max", "") if state else "")
        reference_edit = QLineEdit(state.get("reference", "") if state else "")
        proposal_edit = QLineEdit(state.get("proposal", "") if state else "")
        fixed_value_edit = QLineEdit(state.get("fixed_value", "") if state else "")
        unit_edit = QLineEdit(state.get("unit", "") if state else "")
        nuisance_box = QCheckBox()
        nuisance_box.setChecked(bool(state.get("nuisance", False)) if state else False)
        nuisance_box.setEnabled(False)
        nuisance_box.setToolTip("Reservado para futuros parametros de nuisance.")
        nuisance_box.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.table.setCellWidget(row, self.COLUMN_NAME, name_edit)
        self.table.setCellWidget(row, self.COLUMN_LABEL, label_edit)
        self.table.setCellWidget(row, self.COLUMN_ROLE, role_box)
        self.table.setCellWidget(row, self.COLUMN_PRIOR_MIN, prior_min_edit)
        self.table.setCellWidget(row, self.COLUMN_PRIOR_MAX, prior_max_edit)
        self.table.setCellWidget(row, self.COLUMN_REFERENCE, reference_edit)
        self.table.setCellWidget(row, self.COLUMN_PROPOSAL, proposal_edit)
        self.table.setCellWidget(row, self.COLUMN_FIXED_VALUE, fixed_value_edit)
        self.table.setCellWidget(row, self.COLUMN_UNIT, unit_edit)
        self.table.setCellWidget(row, self.COLUMN_NUISANCE, nuisance_box)

        role_box.currentTextChanged.connect(
            lambda _value, target=role_box: self._update_role_widgets_for_box(target)
        )
        self._update_role_widgets(row)

    def remove_selected_parameter(self) -> None:
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)

    def parameters_state(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in range(self.table.rowCount()):
            rows.append(
                {
                    "name": self._line_edit(row, self.COLUMN_NAME).text(),
                    "label": self._line_edit(row, self.COLUMN_LABEL).text(),
                    "role": self._role_box(row).currentText(),
                    "prior_min": self._line_edit(row, self.COLUMN_PRIOR_MIN).text(),
                    "prior_max": self._line_edit(row, self.COLUMN_PRIOR_MAX).text(),
                    "reference": self._line_edit(row, self.COLUMN_REFERENCE).text(),
                    "proposal": self._line_edit(row, self.COLUMN_PROPOSAL).text(),
                    "fixed_value": self._line_edit(
                        row, self.COLUMN_FIXED_VALUE
                    ).text(),
                    "unit": self._line_edit(row, self.COLUMN_UNIT).text(),
                    "nuisance": self._nuisance_box(row).isChecked(),
                }
            )
        return rows

    def set_parameters_state(self, rows: list[dict[str, Any]]) -> None:
        self.table.setRowCount(0)
        for row in rows:
            self.add_parameter_row(row)

    def is_sampled_fields_enabled(self, row: int) -> bool:
        return self._line_edit(row, self.COLUMN_PRIOR_MIN).isEnabled()

    def is_fixed_field_enabled(self, row: int) -> bool:
        return self._line_edit(row, self.COLUMN_FIXED_VALUE).isEnabled()

    def _update_role_widgets(self, row: int) -> None:
        is_sampled = self._role_box(row).currentText() == "sampled"
        for column in (
            self.COLUMN_PRIOR_MIN,
            self.COLUMN_PRIOR_MAX,
            self.COLUMN_REFERENCE,
            self.COLUMN_PROPOSAL,
        ):
            self._line_edit(row, column).setEnabled(is_sampled)
        self._line_edit(row, self.COLUMN_FIXED_VALUE).setEnabled(not is_sampled)

    def _update_role_widgets_for_box(self, role_box: QComboBox) -> None:
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, self.COLUMN_ROLE) is role_box:
                self._update_role_widgets(row)
                return

    def _line_edit(self, row: int, column: int) -> QLineEdit:
        widget = self.table.cellWidget(row, column)
        assert isinstance(widget, QLineEdit)
        return widget

    def _role_box(self, row: int) -> QComboBox:
        widget = self.table.cellWidget(row, self.COLUMN_ROLE)
        assert isinstance(widget, QComboBox)
        return widget

    def _nuisance_box(self, row: int) -> QCheckBox:
        widget = self.table.cellWidget(row, self.COLUMN_NUISANCE)
        assert isinstance(widget, QCheckBox)
        return widget
