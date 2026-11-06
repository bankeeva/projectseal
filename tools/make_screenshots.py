"""Снять скриншоты ProjectSeal для README и документации.

Запуск (без дисплея):
    QT_QPA_PLATFORM=offscreen .venv312/bin/python tools/make_screenshots.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
import zipfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "2")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "screenshots"
DEMO_SOURCE = ROOT / "demo" / "leaky_project"
DEMO = Path("/tmp/ProjectSeal Demo/leaky_project")


def wait_for(app, predicate, timeout: float = 20.0) -> bool:
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    app.processEvents()
    return bool(predicate())


def main() -> None:
    from projectseal.app import create_application
    from projectseal.core.models import ScanError
    from projectseal.core.scanner import ScanProgress
    from projectseal.ui.dialogs import ProblemsDialog, SuccessDialog
    from projectseal.ui.main_window import MainWindow

    OUT.mkdir(parents=True, exist_ok=True)
    if DEMO.parent.exists():
        shutil.rmtree(DEMO.parent)
    DEMO.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(DEMO_SOURCE, DEMO)

    app = create_application([])
    window = MainWindow()
    window.resize(1264, 840)
    window.show()
    app.processEvents()

    def shot(widget, name: str) -> None:
        pixmap = widget.grab()
        path = OUT / name
        pixmap.save(str(path))
        print(f"{name}: {pixmap.width()}x{pixmap.height()}")

    # 1. Стартовый экран
    window.welcome.set_folder(None)
    window._folder = None
    app.processEvents()
    shot(window, "01_welcome.png")

    # 2. Выбранная папка
    window._set_folder(DEMO)
    app.processEvents()
    shot(window, "02_folder_selected.png")

    # 3. Экран проверки (реальный экран, прогресс выставлен для наглядности)
    window.stack.setCurrentWidget(window.scanning)
    window.scanning.reset()
    window.scanning.set_root(DEMO)
    window._set_steps("scanning")
    window.scanning.set_progress(
        ScanProgress(
            phase="analyze",
            done=87,
            total=200,
            current="config/settings.py",
            found=87,
        )
    )
    app.processEvents()
    shot(window, "03_scanning.png")

    # 4. Реальная проверка демо-проекта
    window._start_scan()
    if not wait_for(app, lambda: window._review_page is not None and window._scan_thread is None):
        raise SystemExit("Не удалось дождаться результата проверки")
    review = window._review_page
    assert review is not None
    review.tabs.setCurrentIndex(0)
    app.processEvents()
    shot(window, "04_risks.png")

    review.tabs.setCurrentIndex(1)
    app.processEvents()
    shot(window, "05_junk.png")

    review.tabs.setCurrentIndex(2)
    app.processEvents()
    shot(window, "06_safe.png")

    # 5. Экспорт и диалог успеха
    destination = DEMO.parent / "leaky_project_clean.zip"
    if destination.exists():
        destination.unlink()
    with patch("projectseal.ui.main_window.SuccessDialog.exec", return_value=0):
        window._start_export(window._result, destination, review.selected_paths(), False)
        if not wait_for(
            app,
            lambda: review._export_result is not None and window._export_thread is None,
        ):
            raise SystemExit("Не удалось дождаться экспорта")
        app.processEvents()

    success = SuccessDialog(review._export_result)
    success.show()
    app.processEvents()
    shot(success, "07_success.png")
    success.close()

    # 6. Диалог проблем (иллюстрация обработки ошибок)
    problems = ProblemsDialog(
        [
            ScanError(
                "keys/private.pem",
                "Нет доступа к файлу — он исключён из архива, содержимое не проверено.",
                "permission",
            ),
            ScanError(
                "data/export.bin",
                "Файл больше 5 МБ: содержимое не проверялось, но файл включён в архив.",
                "skipped",
            ),
            ScanError(
                "vendor/min.js",
                "Файл больше 5 МБ: содержимое не проверялось, файл включён в архив.",
                "skipped",
            ),
            ScanError(
                "logs/error.log",
                "Нет доступа к файлу — он исключён из архива.",
                "permission",
            ),
            ScanError(
                "tmp/session.tmp",
                "Символическая ссылка: переход не выполняется, файл не включается.",
                "symlink",
            ),
            ScanError(
                "models/large.csv",
                "Файл больше 5 МБ: содержимое не проверялось, файл включён в архив.",
                "skipped",
            ),
        ]
    )
    problems.show()
    app.processEvents()
    shot(problems, "09_problems.png")
    problems.close()

    # 7. Метрики для README
    archive_names: list[str] = []
    if destination.exists():
        with zipfile.ZipFile(destination) as archive:
            archive_names = archive.namelist()
    metrics = {
        "demo_path": str(DEMO),
        "scan": {
            "total_files": review.result.summary.total_files,
            "secrets": review.result.summary.secrets_found,
            "junk": review.result.summary.junk_found,
            "safe": review.result.summary.safe_to_pack,
            "safe_bytes": review.result.summary.safe_bytes,
            "duration_ms": review.result.summary.duration_ms,
            "errors": review.result.summary.errors_count,
            "binary": review.result.summary.binary_files,
        },
        "export": {
            "path": str(destination),
            "included_files": review._export_result.included_files,
            "archive_size": review._export_result.archive_size,
            "included_bytes": review._export_result.included_bytes,
            "verified": review._export_result.verified,
            "duration_ms": review._export_result.duration_ms,
            "remote_secrets_excluded": review._export_result.excluded_secret_files,
            "junk_excluded": review._export_result.excluded_junk_files,
        },
        "archive_names": archive_names,
    }
    (OUT / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))

    window.close()
    app.processEvents()


if __name__ == "__main__":
    main()
