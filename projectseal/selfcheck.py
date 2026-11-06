"""Скрытая самопроверка собранного приложения.

Запускается только с флагом ``--self-check``. Проверяет, что в frozen-сборке
доступны ресурсы, правила, сканер и экспортёр. Не является пользовательской
функцией и не влияет на обычный запуск.
"""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from pathlib import Path


def run_self_check(output: str | Path | None = None) -> int:
    report: dict = {"ok": False, "checks": {}}
    try:
        from .core.exporter import ZipExporter
        from .core.rules import load_rules
        from .core.scanner import Scanner
        from .runtime import resource_path

        rules_path = resource_path("rules.json")
        icon_path = resource_path("icon.svg")
        check_png = resource_path("check.png")
        report["checks"].update(
            {
                "rules_path": str(rules_path),
                "rules_exists": rules_path.exists(),
                "icon_exists": icon_path.exists(),
                "check_png_exists": check_png.exists(),
            }
        )
        rules = load_rules()
        report["checks"]["rules_loaded"] = len(rules.content_patterns)

        root = Path(tempfile.mkdtemp()) / "selfcheck_project"
        (root / "src").mkdir(parents=True)
        (root / "src" / "main.py").write_text("print('ok')\n", encoding="utf-8")
        (root / ".env").write_text("DB_PASSWORD=SuperSecret123!\n", encoding="utf-8")
        (root / "node_modules").mkdir()
        (root / "node_modules" / "pkg.js").write_text("x", encoding="utf-8")
        result = Scanner(rules).scan(root)
        report["checks"].update(
            {
                "scanned": result.summary.total_files,
                "secrets": result.summary.secrets_found,
                "junk": result.summary.junk_found,
                "safe": result.summary.safe_to_pack,
            }
        )

        destination = root.parent / "selfcheck_clean.zip"
        export = ZipExporter().export(result, destination)
        with zipfile.ZipFile(destination) as archive:
            names = archive.namelist()
            bad = archive.testzip()
        report["checks"].update(
            {
                "archive": str(destination),
                "archive_names": names,
                "archive_bad_member": bad,
                "export_verified": export.verified,
                "source_untouched": (root / "src" / "main.py").read_text(encoding="utf-8")
                == "print('ok')\n",
            }
        )
        report["ok"] = bool(
            rules_path.exists()
            and icon_path.exists()
            and check_png.exists()
            and result.summary.secrets_found == 1
            and result.summary.safe_to_pack == 1
            and export.verified
            and bad is None
            and ".env" not in names
            and not any(name.startswith("node_modules/") for name in names)
        )
    except Exception as exc:  # noqa: BLE001 — самопроверка должна вернуть отчёт
        report["error"] = f"{type(exc).__name__}: {exc}"

    target = Path(output) if output else Path(tempfile.gettempdir()) / "projectseal_selfcheck.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        print(json.dumps(report, ensure_ascii=False))
    except Exception:  # noqa: BLE001 — в windowed-сборке stdout может отсутствовать
        pass
    return 0 if report.get("ok") else 1


def run_ui_smoke_test(output: str | Path | None = None) -> int:
    """Проверить, что Qt и главное окно собираются в frozen-сборке."""
    report: dict = {"ok": False}
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from .app import create_application
        from .ui.main_window import MainWindow

        app = create_application([])
        window = MainWindow()
        window.show()
        app.processEvents()
        report.update(
            {
                "ok": bool(window.welcome is not None and window.scanning is not None),
                "window_size": [window.width(), window.height()],
                "tabs_at_start": window.stack.count(),
                "platform": os.environ.get("QT_QPA_PLATFORM"),
            }
        )
        window.close()
        app.processEvents()
    except Exception as exc:  # noqa: BLE001
        report["error"] = f"{type(exc).__name__}: {exc}"

    target = Path(output) if output else Path(tempfile.gettempdir()) / "projectseal_ui_smoke.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        print(json.dumps(report, ensure_ascii=False))
    except Exception:  # noqa: BLE001
        pass
    return 0 if report.get("ok") else 1
