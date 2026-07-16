"""PySide6 application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from cosmofit.ui.main_window import build_main_window


def main(argv: list[str] | None = None) -> int:
    """Launch the first CosmoFit desktop milestone."""

    arguments = list(sys.argv if argv is None else argv)
    app = QApplication.instance() or QApplication(arguments)
    app.setApplicationName("CosmoFit")
    app.setOrganizationName("CosmoFit")
    window = build_main_window()
    window.show()
    return app.exec()
