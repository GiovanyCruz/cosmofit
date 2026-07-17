"""Parameter table widget for arbitrary cosmological parameter rows."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPalette, QPixmap
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from cosmofit.application import MathTextService

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


class MathTextPreviewCell(QFrame):
    """Compact rendered preview cell for plain labels or MathText."""

    _HEIGHT = 28

    def __init__(self, *, field_name: str, edit: QLineEdit) -> None:
        super().__init__()
        self._field_name = field_name
        self._edit = edit
        self._service = MathTextService()
        self._source_pixmap = QPixmap()

        self.preview_label = QLabel()
        self.preview_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.preview_label.setWordWrap(False)
        self.preview_label.setToolTip(_MATH_TEXT_EXAMPLES)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(
            QPalette.ColorRole.Window,
            palette.color(QPalette.ColorRole.Base),
        )
        self.setPalette(palette)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setLineWidth(1)
        self.setMinimumHeight(self._HEIGHT)
        self.setMaximumHeight(self._HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.addWidget(self.preview_label)

        self._edit.textChanged.connect(self.refresh_preview)
        self.refresh_preview(self._edit.text())

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(140, self._HEIGHT)

    def minimumSizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(96, self._HEIGHT)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_scaled_pixmap()

    def refresh_preview(self, text: str) -> None:
        if not text.strip():
            self._source_pixmap = QPixmap()
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setStyleSheet("color: palette(text);")
            self.preview_label.setText("")
            return

        try:
            preview = self._service.render_preview(text, field_name=self._field_name)
        except ValueError as error:
            self._source_pixmap = QPixmap()
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setStyleSheet("color: #9b1c1c;")
            self.preview_label.setText("Invalid MathText.")
            self.preview_label.setToolTip(f"{_MATH_TEXT_EXAMPLES}\n\n{error}")
            return

        self.preview_label.setStyleSheet("color: palette(text);")
        self.preview_label.setToolTip(_MATH_TEXT_EXAMPLES)
        if preview is None:
            self._source_pixmap = QPixmap()
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText(text)
            return
        pixmap = QPixmap()
        pixmap.loadFromData(preview.png_bytes)
        self._source_pixmap = pixmap
        self._apply_scaled_pixmap()
        self.preview_label.setText("")

    def _apply_scaled_pixmap(self) -> None:
        if self._source_pixmap.isNull():
            return
        scaled = self._source_pixmap.scaled(
            max(self.preview_label.width(), 1),
            max(self._HEIGHT - 8, 1),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)


class ParameterTableWidget(QWidget):
    """Editable parameter table with role-dependent fields."""

    COLUMN_NAME = 0
    COLUMN_LABEL = 1
    COLUMN_PREVIEW = 2
    COLUMN_ROLE = 3
    COLUMN_PRIOR_MIN = 4
    COLUMN_PRIOR_MAX = 5
    COLUMN_REFERENCE = 6
    COLUMN_PROPOSAL = 7
    COLUMN_FIXED_VALUE = 8
    COLUMN_UNIT = 9
    COLUMN_NUISANCE = 10

    def __init__(self) -> None:
        super().__init__()

        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels(
            [
                "Name",
                "Label",
                "Preview",
                "Role",
                "Prior min",
                "Prior max",
                "Reference",
                "Proposal",
                "Fixed value",
                "Unit",
                "Nuisance",
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored
        )
        self.table.setWordWrap(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.table.horizontalHeader().setMinimumSectionSize(72)
        self.table.horizontalHeader().setDefaultSectionSize(120)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)

        self.add_button = QPushButton("Add parameter")
        self.remove_button = QPushButton("Remove selected parameter")
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
        label_edit.setToolTip(_MATH_TEXT_EXAMPLES)
        preview = MathTextPreviewCell(
            field_name="parameter display label",
            edit=label_edit,
        )
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
        nuisance_box.setToolTip("Reserved for future nuisance parameters.")
        nuisance_box.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.table.setCellWidget(row, self.COLUMN_NAME, name_edit)
        self.table.setCellWidget(row, self.COLUMN_LABEL, label_edit)
        self.table.setCellWidget(row, self.COLUMN_PREVIEW, preview)
        self.table.setCellWidget(row, self.COLUMN_ROLE, role_box)
        self.table.setCellWidget(row, self.COLUMN_PRIOR_MIN, prior_min_edit)
        self.table.setCellWidget(row, self.COLUMN_PRIOR_MAX, prior_max_edit)
        self.table.setCellWidget(row, self.COLUMN_REFERENCE, reference_edit)
        self.table.setCellWidget(row, self.COLUMN_PROPOSAL, proposal_edit)
        self.table.setCellWidget(row, self.COLUMN_FIXED_VALUE, fixed_value_edit)
        self.table.setCellWidget(row, self.COLUMN_UNIT, unit_edit)
        self.table.setCellWidget(row, self.COLUMN_NUISANCE, nuisance_box)
        row_height = max(
            name_edit.sizeHint().height(),
            label_edit.sizeHint().height(),
            preview.sizeHint().height(),
            role_box.sizeHint().height(),
        )
        self.table.setRowHeight(row, row_height + 4)

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
                    "label": self._label_edit(row).text(),
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

    def _label_edit(self, row: int) -> QLineEdit:
        widget = self.table.cellWidget(row, self.COLUMN_LABEL)
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
