#!/usr/bin/env python3
"""Двойной клик по этому файлу запускает ProjectSeal без консоли.

На Windows файл .pyw открывается через pythonw.exe, поэтому терминал не
появляется. В готовой сборке этот файл заменяется на ProjectSeal.exe.
"""

from __future__ import annotations

import logging
import os
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _fatal(message: str) -> None:
    try:
        from projectseal.runtime import emergency_message

        emergency_message("ProjectSeal", message)
    except Exception:  # noqa: BLE001
        print(message, file=sys.stderr)


def main() -> int:
    if "--self-check" in sys.argv:
        from projectseal.selfcheck import run_self_check

        return run_self_check(os.environ.get("PROJECTSEAL_SELF_CHECK_OUT"))
    if "--ui-smoke-test" in sys.argv:
        from projectseal.selfcheck import run_ui_smoke_test

        return run_ui_smoke_test(os.environ.get("PROJECTSEAL_UI_SMOKE_OUT"))
    try:
        from projectseal.app import run
    except ImportError as exc:
        _fatal(
            "Не удалось загрузить ProjectSeal.\n\n"
            "Похоже, не установлен графический модуль PySide6.\n"
            "Для обычного запуска используйте готовый ProjectSeal.exe "
            "(Windows) или ProjectSeal.app (macOS).\n\n"
            f"Техническая информация: {exc}"
        )
        return 2
    except Exception:  # noqa: BLE001
        logging.exception("Startup import failed")
        _fatal("Не удалось запустить ProjectSeal. Подробности в журнале приложения.")
        return 1
    try:
        return run()
    except Exception:  # noqa: BLE001
        logging.exception("Startup failed")
        _fatal(
            "Не удалось запустить ProjectSeal.\n\n"
            "Подробности сохранены в журнале приложения."
        )
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        _fatal("Критическая ошибка запуска ProjectSeal.")
        raise SystemExit(1)
