from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt

from projectseal.ui.main_window import MainWindow


def _make_project(root: Path) -> Path:
    (root / "src").mkdir(parents=True)
    (root / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    (root / ".env").write_text("DB_PASSWORD=SuperSecret123!\n", encoding="utf-8")
    (root / ".env.example").write_text("DB_PASSWORD=your_password_here\n", encoding="utf-8")
    (root / "node_modules").mkdir()
    for index in range(8):
        (root / "node_modules" / f"pkg_{index}.js").write_text("x", encoding="utf-8")
    (root / "app.log").write_text("log\n", encoding="utf-8")
    return root


def test_welcome_requires_folder(qapp) -> None:
    window = MainWindow()
    window.show()
    qapp.processEvents()
    assert window.stack.currentWidget() is window.welcome
    assert window.welcome.scan_button.isEnabled() is False
    window.close()
    qapp.processEvents()


def test_invalid_folder_shows_error(qapp, tmp_path: Path) -> None:
    window = MainWindow()
    window.show()
    window._set_folder(tmp_path / "missing")
    qapp.processEvents()
    assert window.welcome.error_banner.isVisible() is True
    window.close()
    qapp.processEvents()


def test_scan_review_and_export_flow(qapp, tmp_path: Path, wait_until) -> None:
    root = _make_project(tmp_path / "demo_project")
    window = MainWindow()
    window.show()
    qapp.processEvents()

    window._set_folder(root)
    assert window.welcome.scan_button.isEnabled() is True
    window._start_scan()
    assert wait_until(
        lambda: window._review_page is not None and window._scan_thread is None,
        timeout=20,
    )

    review = window._review_page
    assert review is not None
    assert window.stack.currentWidget() is review
    assert review.tabs.count() == 3
    assert review.tabs.tabText(0).startswith("Риски")
    assert review.tabs.tabText(1).startswith("Мусор")
    assert review.tabs.tabText(2).startswith("В архив")
    assert review.risk_stat.value_label.text() == "1"
    assert review.junk_stat.value_label.text() == "9"  # 8 node_modules + app.log
    assert review.safe_stat.value_label.text() == "3"
    assert review.export_button.isEnabled() is True

    # Вкладка «В архив»: чекбоксы и пересчёт нижней панели.
    review.tabs.setCurrentIndex(2)
    qapp.processEvents()
    assert review.select_all_button.isVisible() is True
    assert review.safe_tab.selected_count() == 3
    model = review.safe_tab.model
    first = model.index(0, 0)
    assert model.setData(
        first,
        Qt.CheckState.Unchecked,
        Qt.ItemDataRole.CheckStateRole,
    )
    qapp.processEvents()
    assert review.safe_tab.selected_count() == 2
    assert "2 файла" in review.footer_title.text()
    model.setData(first, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
    qapp.processEvents()
    assert review.safe_tab.selected_count() == 3

    destination = tmp_path / "clean.zip"
    with patch("projectseal.ui.main_window.SuccessDialog.exec", return_value=0):
        window._start_export(window._result, destination, review.selected_paths(), False)
        assert wait_until(
            lambda: window._export_thread is None and destination.exists(),
            timeout=20,
        )
        qapp.processEvents()

    assert destination.exists()
    with zipfile.ZipFile(destination) as archive:
        names = set(archive.namelist())
        assert "src/main.py" in names
        assert ".env" not in names
        assert "app.log" not in names
        assert not any(name.startswith("node_modules/") for name in names)
        assert archive.testzip() is None
    assert review._export_result is not None
    assert review._export_result.verified is True

    window.close()
    qapp.processEvents()


def test_problems_dialog_does_not_crash(qapp, tmp_path: Path) -> None:
    from projectseal.core.models import ScanError
    from projectseal.ui.dialogs import ProblemsDialog

    dialog = ProblemsDialog(
        [ScanError("secret.txt", "Нет доступа к файлу.", "permission")],
        parent=None,
    )
    dialog.show()
    qapp.processEvents()
    assert dialog.list.count() == 1
    dialog.close()
    qapp.processEvents()
