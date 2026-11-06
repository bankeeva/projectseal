"""Пути ресурсов, журналирование и аварийные сообщения."""

from __future__ import annotations

import logging
import logging.handlers
import os
import platform
import sys
import traceback
from pathlib import Path
from typing import Any

from .version import APP_NAME, __version__


def _resource_candidates(name: str) -> list[Path]:
    """Все разумные места, где PyInstaller может разместить data-файлы."""
    candidates: list[Path] = []
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        base = Path(bundle_dir)
        candidates.append(base / "projectseal" / "resources")
        # macOS .app: Contents/Frameworks -> Contents/Resources
        candidates.append(base.parent / "Resources" / "projectseal" / "resources")
    # macOS .app: Contents/MacOS/ProjectSeal -> Contents/Resources
    try:
        executable = Path(sys.executable).resolve()
        candidates.append(executable.parent.parent / "Resources" / "projectseal" / "resources")
    except (OSError, AttributeError):
        pass
    candidates.append(Path(__file__).resolve().parent / "resources")
    seen: set[Path] = set()
    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def resource_path(name: str) -> Path:
    """Путь к ресурсу как в исходниках, так и внутри PyInstaller-сборки."""
    candidates = _resource_candidates(name)
    for base in candidates:
        candidate = base / name
        if candidate.exists():
            return candidate
    # Если ничего не найдено, возвращаем последний (исходный) путь:
    # вызывающий код сможет обработать отсутствие файла предсказуемо.
    return candidates[-1] / name


def logs_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return root / APP_NAME / "logs"
    if system == "Darwin":
        return Path.home() / "Library" / "Logs" / APP_NAME
    state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return state / APP_NAME.lower() / "logs"


def error_log_path() -> Path:
    return logs_dir() / "error.log"


def setup_logging() -> Path:
    """Настроить ротацию журнала. Секреты и содержимое файлов не пишутся."""
    directory = logs_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Если журнал создать нельзя, приложение всё равно должно запуститься.
        return error_log_path()

    log_path = directory / "error.log"
    logger = logging.getLogger()
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers):
        try:
            handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=1_000_000,
                backupCount=3,
                encoding="utf-8",
            )
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s %(levelname)s %(name)s: %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        except OSError:
            pass
    logging.info(
        "%s %s started; platform=%s %s; python=%s",
        APP_NAME,
        __version__,
        platform.system(),
        platform.release(),
        platform.python_version(),
    )
    return log_path


def install_exception_hook() -> None:
    """Глобальный перехватчик: пишем traceback и не закрываем приложение молча."""

    def handle(exc_type: type[BaseException], exc: BaseException, tb: Any) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        logging.critical("Unhandled exception", exc_info=(exc_type, exc, tb))
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is not None:
                box = QMessageBox()
                box.setIcon(QMessageBox.Icon.Critical)
                box.setWindowTitle(APP_NAME)
                box.setText("Что-то пошло не так.")
                box.setInformativeText(
                    "ProjectSeal сохранил подробности в журнал. "
                    "Можно закрыть это окно и попробовать снова."
                )
                box.setDetailedText("".join(traceback.format_exception(exc_type, exc, tb)))
                box.setStandardButtons(QMessageBox.StandardButton.Ok)
                box.exec()
        except Exception:  # noqa: BLE001 — аварийный обработчик не должен падать
            pass
        print("".join(traceback.format_exception(exc_type, exc, tb)), file=sys.stderr)

    sys.excepthook = handle


def emergency_message(title: str, text: str) -> None:
    """Показать сообщение, даже если Qt ещё не загрузился."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, text)
        root.destroy()
        return
    except Exception:  # noqa: BLE001
        pass
    try:
        if platform.system() == "Darwin":
            import subprocess

            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display dialog "{text}" with title "{title}" buttons {{"OK"}} default button "OK" with icon stop',
                ],
                check=False,
            )
        elif platform.system() == "Windows":
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)
    except Exception:  # noqa: BLE001
        pass
