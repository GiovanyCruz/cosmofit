"""Inactive results placeholder for the first UI milestone."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ResultsWidget(QWidget):
    """Results tab placeholder until execution and analysis are added."""

    def __init__(self) -> None:
        super().__init__()
        label = QLabel(
            "Resultados aun no disponibles.\n"
            "La ejecucion y el analisis se agregan en el siguiente hito."
        )
        layout = QVBoxLayout(self)
        layout.addWidget(label)
