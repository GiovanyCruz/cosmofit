"""Execution log and placeholder-results panel for the desktop UI."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ResultsWidget(QWidget):
    """Display run lifecycle, logs, and a placeholder summary."""

    def __init__(self) -> None:
        super().__init__()
        self._pending_log_lines: list[str] = []

        self.state_label = QLabel("Estado: Idle")
        self.output_directory_label = QLabel("Directorio final: sin ejecucion")
        self.summary_label = QLabel(
            "Resultados completos aun no disponibles.\n"
            "El siguiente hito cargara los posteriores de GetDist."
        )
        self.summary_label.setWordWrap(True)
        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.document().setMaximumBlockCount(5000)
        self.clear_log_button = QPushButton("Limpiar log")
        self.open_output_button = QPushButton("Abrir carpeta de salida")
        self.open_output_button.setEnabled(False)
        self._log_flush_timer = QTimer(self)
        self._log_flush_timer.setSingleShot(True)
        self._log_flush_timer.setInterval(25)
        self._log_flush_timer.timeout.connect(self._flush_log_lines)

        buttons = QHBoxLayout()
        buttons.addWidget(self.clear_log_button)
        buttons.addWidget(self.open_output_button)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(self.state_label)
        layout.addWidget(self.output_directory_label)
        layout.addWidget(self.summary_label)
        layout.addLayout(buttons)
        layout.addWidget(self.log_area)

    def append_log_line(self, stream: str, line: str) -> None:
        prefix = "[stderr] " if stream == "stderr" else ""
        self._pending_log_lines.append(prefix + line)
        if not self._log_flush_timer.isActive():
            self._log_flush_timer.start()

    def clear_log(self) -> None:
        self._pending_log_lines.clear()
        self._log_flush_timer.stop()
        self.log_area.clear()

    def set_execution_state(self, state: str) -> None:
        self._flush_log_lines()
        self.state_label.setText(f"Estado: {state}")

    def set_output_directory(self, path: Path | None) -> None:
        label = "sin ejecucion" if path is None else str(path)
        self.output_directory_label.setText(f"Directorio final: {label}")
        self.open_output_button.setEnabled(path is not None)

    def set_placeholder_summary(
        self,
        *,
        run_label: str,
        completion_state: str,
        output_directory: Path,
        datasets: tuple[str, ...],
        sampled_parameters: tuple[str, ...],
    ) -> None:
        self.summary_label.setText(
            "\n".join(
                [
                    f"Etiqueta: {run_label}",
                    f"Estado final: {completion_state}",
                    f"Directorio: {output_directory}",
                    "Datasets: " + ", ".join(datasets),
                    "Parametros muestreados: " + ", ".join(sampled_parameters),
                    "Posteriores de GetDist: pendiente del siguiente hito.",
                ]
            )
        )

    def _flush_log_lines(self) -> None:
        if not self._pending_log_lines:
            return
        self.log_area.appendPlainText("\n".join(self._pending_log_lines))
        self._pending_log_lines.clear()
        cursor = self.log_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_area.setTextCursor(cursor)
