"""Точка входа приложения ProjectSeal."""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from .runtime import (
    emergency_message,
    install_exception_hook,
    setup_logging,
)
from .ui.icons import app_icon
from .ui.main_window import MainWindow
from .ui.theme import apply_theme
from .version import APP_NAME, ORGANIZATION


def create_application(argv: list[str] | None = None) -> QApplication:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(ORGANIZATION)
    app.setDesktopFileName("projectseal")
    app.setWindowIcon(app_icon())
    apply_theme(app)
    return app


def run(argv: list[str] | None = None) -> int:
    log_path = setup_logging()
    install_exception_hook()
    try:
        app = create_application(argv)
        window = MainWindow()
        window.show()
        window.raise_()
        window.activateWindow()
        return app.exec()
    except Exception:  # noqa: BLE001 — запуск не должен падать молча
        logging.exception("Fatal startup error")
        emergency_message(
            APP_NAME,
            "Не удалось запустить ProjectSeal.\n\n"
            f"Подробности сохранены в журнале:\n{log_path}\n\n"
            "Попробуйте запустить приложение ещё раз.",
        )
        return 1


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
