"""Ponto de entrada da GUI."""

from __future__ import annotations

import sys


def main() -> int:
    import pyqtgraph as pg
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication, QMessageBox

    from ..infrastructure.logging_setup import install_excepthook, setup_logging
    from .app_state import AppState
    from .main_window import MainWindow
    from .theme import Theme

    log_path = setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Mangue Logger")
    app.setOrganizationName("MangueBaja")
    app.setStyleSheet(Theme.qss())
    font = QFont("Segoe UI", 10)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    app.setFont(font)

    pg.setConfigOption("background", Theme.BG_BASE)
    pg.setConfigOption("foreground", Theme.TEXT_SEC)
    pg.setConfigOption("antialias", True)
    pg.setConfigOption("useOpenGL", False)

    install_excepthook(lambda msg: QMessageBox.critical(None, "Erro inesperado", f"{msg}\n\nDetalhes em:\n{log_path}"))

    window = MainWindow(AppState())
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
