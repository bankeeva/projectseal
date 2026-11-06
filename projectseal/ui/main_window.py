"""Главное окно ProjectSeal и управление состояниями приложения."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.exporter import ExportResult
from ..core.models import ScanResult
from ..core.paths import human_size, is_within
from ..runtime import error_log_path
from ..version import APP_NAME, __version__
from .dialogs import (
    AboutDialog,
    ErrorDialog,
    ExportProgressDialog,
    HelpDialog,
    SuccessDialog,
)
from .icons import app_icon, get_icon, get_pixmap, logo_pixmap
from .theme import GREEN
from .widgets import StepRow, Toast
from .welcome import WelcomePage
from .widgets import ReviewPage, ScanningPage
from .workers import ExportWorker, ScanWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._folder: Path | None = None
        self._result: ScanResult | None = None
        self._review_page: ReviewPage | None = None
        self._scan_thread: QThread | None = None
        self._scan_worker: ScanWorker | None = None
        self._export_thread: QThread | None = None
        self._export_worker: ExportWorker | None = None
        self._export_dialog: ExportProgressDialog | None = None
        self._shortcuts: list[QShortcut] = []

        self.setWindowTitle("ProjectSeal — безопасная передача проекта")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(1120, 720)
        self.resize(1264, 840)
        self._build_ui()
        self._install_shortcuts()
        self._set_steps("idle")
        self._center_on_screen()

    # ------------------------------------------------------------------
    # Построение интерфейса
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = self._build_sidebar()
        root_layout.addWidget(sidebar)

        self.stack = QStackedWidget()
        self.welcome = WelcomePage()
        self.scanning = ScanningPage()
        self.stack.addWidget(self.welcome)
        self.stack.addWidget(self.scanning)
        root_layout.addWidget(self.stack, 1)

        self.setCentralWidget(root)

        self.welcome.folderRequested.connect(self._choose_folder)
        self.welcome.folderDropped.connect(self._set_folder)
        self.welcome.scanRequested.connect(self._start_scan)
        self.welcome.helpRequested.connect(self._open_help)
        self.scanning.cancelRequested.connect(self._cancel_scan)

        self.toast = Toast(self)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(266)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 26, 20, 18)
        layout.setSpacing(6)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(40))
        logo.setFixedSize(40, 40)
        brand.addWidget(logo)
        brand_texts = QVBoxLayout()
        brand_texts.setSpacing(0)
        name = QLabel(APP_NAME)
        name.setObjectName("BrandTitle")
        tagline = QLabel("Безопасная передача кода")
        tagline.setObjectName("BrandTagline")
        brand_texts.addWidget(name)
        brand_texts.addWidget(tagline)
        brand.addLayout(brand_texts, 1)
        layout.addLayout(brand)
        layout.addSpacing(26)

        section = QLabel("ПРОЦЕСС")
        section.setObjectName("SidebarSection")
        layout.addWidget(section)
        layout.addSpacing(4)

        self.step_widgets = [
            StepRow(1, "Выберите папку", "Локальный диск"),
            StepRow(2, "Проверьте состав", "Риски и мусор"),
            StepRow(3, "Создайте ZIP", "Чистый архив"),
        ]
        for step in self.step_widgets:
            layout.addWidget(step)

        layout.addStretch(1)

        privacy = QFrame()
        privacy.setObjectName("PrivacyCard")
        privacy_layout = QHBoxLayout(privacy)
        privacy_layout.setContentsMargins(12, 11, 12, 11)
        privacy_layout.setSpacing(9)
        lock = QLabel()
        lock.setPixmap(get_pixmap("lock", GREEN, 18))
        lock.setFixedSize(20, 20)
        privacy_layout.addWidget(lock, 0, Qt.AlignmentFlag.AlignTop)
        privacy_texts = QVBoxLayout()
        privacy_texts.setSpacing(2)
        title = QLabel("100% локально")
        title.setObjectName("PrivacyTitle")
        text = QLabel("Файлы не покидают компьютер. Нет аккаунта, облака и сети.")
        text.setObjectName("PrivacyText")
        text.setWordWrap(True)
        privacy_texts.addWidget(title)
        privacy_texts.addWidget(text)
        privacy_layout.addLayout(privacy_texts, 1)
        layout.addWidget(privacy)
        layout.addSpacing(8)

        self.help_link = QPushButton("Как это работает")
        self.help_link.setProperty("role", "sidebarLink")
        self.help_link.setIcon(get_icon("info", "#93A8C4", 14))
        self.help_link.setIconSize(QSize(14, 14))
        self.help_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.help_link.clicked.connect(self._open_help)
        layout.addWidget(self.help_link)

        self.about_link = QPushButton("О программе")
        self.about_link.setProperty("role", "sidebarLink")
        self.about_link.setIcon(get_icon("shield", "#93A8C4", 14))
        self.about_link.setIconSize(QSize(14, 14))
        self.about_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.about_link.clicked.connect(self._open_about)
        layout.addWidget(self.about_link)

        version = QLabel(f"Версия {__version__}")
        version.setObjectName("VersionLabel")
        layout.addSpacing(2)
        layout.addWidget(version)
        return sidebar

    def _install_shortcuts(self) -> None:
        for sequence, callback in (
            (QKeySequence.StandardKey.Open, self._choose_folder),
            (QKeySequence("Ctrl+R"), self._start_scan),
            (QKeySequence("Ctrl+E"), self._export),
            (QKeySequence("Esc"), self._cancel_scan),
        ):
            shortcut = QShortcut(sequence, self)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        self.move(
            available.center().x() - self.width() // 2,
            available.center().y() - self.height() // 2,
        )

    # ------------------------------------------------------------------
    # Состояния и шаги
    # ------------------------------------------------------------------
    def _set_steps(self, state: str) -> None:
        mapping = {
            "idle": ("active", "idle", "idle"),
            "scanning": ("done", "active", "idle"),
            "review": ("done", "done", "active"),
            "exporting": ("done", "done", "active"),
            "done": ("done", "done", "done"),
        }
        states = mapping.get(state, mapping["idle"])
        for step, step_state in zip(self.step_widgets, states):
            step.set_state(step_state)

    # ------------------------------------------------------------------
    # Выбор папки и проверка
    # ------------------------------------------------------------------
    def _choose_folder(self) -> None:
        if self._scan_thread is not None or self._export_thread is not None:
            return
        start = str(self._folder or Path.home())
        selected = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку проекта",
            start,
            QFileDialog.Option.ShowDirsOnly,
        )
        if selected:
            self._set_folder(Path(selected))

    def _set_folder(self, folder: Path) -> None:
        folder = Path(folder)
        if not folder.exists() or not folder.is_dir():
            message = "Папка не найдена. Выберите существующую папку проекта."
            self.welcome.set_error(message)
            self.toast.show_message(message, "error")
            return
        self._folder = folder
        self.welcome.set_folder(folder)
        self._set_steps("idle")
        logging.info("Folder selected: %s", folder)

    def _start_scan(self) -> None:
        if self._scan_thread is not None or self._export_thread is not None:
            return
        folder = self._folder
        if folder is None:
            message = "Сначала выберите папку проекта."
            self.welcome.set_error(message)
            self.toast.show_message(message, "warning")
            return
        if not folder.exists() or not folder.is_dir():
            message = "Папка не найдена. Возможно, её переместили или удалили."
            self.welcome.set_error(message)
            self.toast.show_message(message, "error")
            return

        self._discard_review()
        self._result = None
        self.welcome.clear_error()
        self.scanning.reset()
        self.scanning.set_root(folder)
        self.stack.setCurrentWidget(self.scanning)
        self._set_steps("scanning")
        logging.info("Scan started: %s", folder)

        thread = QThread(self)
        thread.setObjectName("ScanThread")
        worker = ScanWorker(folder)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_scan_progress)
        worker.finished.connect(self._on_scan_finished)
        worker.failed.connect(self._on_scan_failed)
        worker.cancelled.connect(self._on_scan_cancelled)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        thread.finished.connect(self._on_scan_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._scan_thread = thread
        self._scan_worker = worker
        thread.start()

    def _on_scan_progress(self, progress) -> None:
        self.scanning.set_progress(progress)

    def _on_scan_finished(self, result: ScanResult) -> None:
        self._result = result
        logging.info(
            "Scan finished: root=%s total=%s secrets=%s junk=%s safe=%s errors=%s ms=%s",
            result.root,
            result.summary.total_files,
            result.summary.secrets_found,
            result.summary.junk_found,
            result.summary.safe_to_pack,
            result.summary.errors_count,
            result.summary.duration_ms,
        )
        self._show_review(result)

    def _show_review(self, result: ScanResult) -> None:
        self._discard_review()
        page = ReviewPage(result)
        page.backRequested.connect(self._back_to_welcome)
        page.exportRequested.connect(self._export)
        self.stack.addWidget(page)
        self._review_page = page
        self.stack.setCurrentWidget(page)
        self._set_steps("review")

    def _on_scan_failed(self, title: str, message: str, kind: str) -> None:
        logging.warning("Scan failed (%s): %s", kind, message)
        self.stack.setCurrentWidget(self.welcome)
        self._set_steps("idle")
        self.welcome.set_error(message)
        self.toast.show_message(message, "error")
        if kind != "input":
            ErrorDialog(title, message, detail=str(error_log_path()), parent=self).exec()

    def _on_scan_cancelled(self) -> None:
        logging.info("Scan cancelled")
        self.stack.setCurrentWidget(self.welcome)
        self._set_steps("idle")
        self.toast.show_message("Проверка отменена. Папка не изменена.", "info")

    def _on_scan_thread_finished(self) -> None:
        self._scan_thread = None
        self._scan_worker = None

    def _cancel_scan(self) -> None:
        if self.stack.currentWidget() is not self.scanning:
            return
        if self._scan_worker is not None:
            self.scanning.set_cancelling()
            self._scan_worker.cancel()

    def _discard_review(self) -> None:
        if self._review_page is not None:
            self.stack.removeWidget(self._review_page)
            self._review_page.deleteLater()
            self._review_page = None

    def _back_to_welcome(self) -> None:
        if self._export_thread is not None:
            return
        self.stack.setCurrentWidget(self.welcome)
        self._set_steps("idle")
        self.welcome.scan_button.setFocus()

    # ------------------------------------------------------------------
    # Экспорт
    # ------------------------------------------------------------------
    def _default_archive_path(self, root: Path) -> Path:
        name = root.name or "project"
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" ._")
        if not name or name in {"..", "."}:
            name = "project"
        return root.parent / f"{name}_clean.zip"

    def _export(self) -> None:
        if self._export_thread is not None or self._scan_thread is not None:
            return
        page = self._review_page
        result = self._result
        if page is None or result is None:
            return
        selected = page.selected_paths()
        if not selected:
            self.toast.show_message("Выберите хотя бы один безопасный файл.", "warning")
            return

        default_path = self._default_archive_path(result.root)
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить безопасный архив",
            str(default_path),
            "ZIP-архив (*.zip)",
        )
        if not filename:
            return
        destination = Path(filename)
        if destination.suffix.lower() != ".zip":
            destination = destination.with_name(destination.name + ".zip")

        if is_within(destination, result.root):
            ErrorDialog(
                "Нельзя сохранить архив внутри проекта",
                "Исходная папка должна остаться неизменной. Выберите папку рядом с проектом, "
                "например родительскую.",
                parent=self,
            ).exec()
            return

        overwrite = False
        if destination.exists():
            answer = QMessageBox.question(
                self,
                "Файл уже существует",
                f"Архив «{destination.name}» уже есть в этой папке.\nПерезаписать его?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            overwrite = True

        self._start_export(result, destination, selected, overwrite)

    def _start_export(
        self,
        result: ScanResult,
        destination: Path,
        selected: set[str],
        overwrite: bool,
    ) -> None:
        dialog = ExportProgressDialog(self)
        dialog.cancelRequested.connect(self._cancel_export)
        self._export_dialog = dialog
        dialog.show()
        self._set_steps("exporting")
        logging.info(
            "Export started: dest=%s selected=%s overwrite=%s",
            destination,
            len(selected),
            overwrite,
        )

        thread = QThread(self)
        thread.setObjectName("ExportThread")
        worker = ExportWorker(
            result,
            destination,
            selected,
            allow_overwrite=overwrite,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_export_progress)
        worker.finished.connect(self._on_export_finished)
        worker.failed.connect(self._on_export_failed)
        worker.cancelled.connect(self._on_export_cancelled)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        thread.finished.connect(self._on_export_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._export_thread = thread
        self._export_worker = worker
        thread.start()

    def _on_export_progress(self, progress) -> None:
        if self._export_dialog is not None:
            self._export_dialog.set_progress(progress)

    def _on_export_finished(self, result: ExportResult) -> None:
        dialog = self._export_dialog
        self._export_dialog = None
        if dialog is not None:
            dialog.finish(ExportProgressDialog.DialogCode.Accepted)
            dialog.deleteLater()
        logging.info(
            "Export finished: dest=%s files=%s size=%s verified=%s",
            result.archive_path,
            result.included_files,
            result.archive_size,
            result.verified,
        )
        if self._review_page is not None:
            self._review_page.show_export_success(result)
        self._set_steps("done")
        self.toast.show_message("Архив создан и проверен.", "success")
        SuccessDialog(result, self).exec()

    def _on_export_failed(self, title: str, message: str, kind: str) -> None:
        logging.warning("Export failed (%s): %s", kind, message)
        self._close_export_dialog()
        self._set_steps("review")
        ErrorDialog(title, message, detail=str(error_log_path()), parent=self).exec()

    def _on_export_cancelled(self) -> None:
        logging.info("Export cancelled")
        self._close_export_dialog()
        self._set_steps("review")
        self.toast.show_message("Упаковка отменена. Частичный архив удалён.", "info")

    def _close_export_dialog(self) -> None:
        dialog = self._export_dialog
        self._export_dialog = None
        if dialog is not None:
            dialog.finish(ExportProgressDialog.DialogCode.Rejected)
            dialog.deleteLater()

    def _cancel_export(self) -> None:
        if self._export_worker is not None:
            self._export_worker.cancel()

    def _on_export_thread_finished(self) -> None:
        self._export_thread = None
        self._export_worker = None

    # ------------------------------------------------------------------
    # Служебные диалоги
    # ------------------------------------------------------------------
    def _open_help(self) -> None:
        HelpDialog(self).exec()

    def _open_about(self) -> None:
        AboutDialog(self).exec()

    # ------------------------------------------------------------------
    # Закрытие и геометрия
    # ------------------------------------------------------------------
    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        try:
            self.toast.reposition()
        except (AttributeError, RuntimeError):
            pass

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._scan_thread is not None and self._scan_thread.isRunning():
            answer = QMessageBox.question(
                self,
                "Идёт проверка",
                "Проверка ещё не завершена. Остановить её и закрыть ProjectSeal?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            if self._scan_worker is not None:
                self._scan_worker.cancel()
            if not self._scan_thread.wait(10_000):
                QMessageBox.warning(
                    self,
                    "Проверка не остановилась",
                    "Дождитесь завершения проверки и попробуйте закрыть окно ещё раз.",
                )
                event.ignore()
                return

        if self._export_thread is not None and self._export_thread.isRunning():
            answer = QMessageBox.question(
                self,
                "Идёт упаковка",
                "Архив ещё создаётся. Отменить упаковку и закрыть ProjectSeal?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            if self._export_worker is not None:
                self._export_worker.cancel()
            if not self._export_thread.wait(10_000):
                QMessageBox.warning(
                    self,
                    "Упаковка не остановилась",
                    "Дождитесь завершения упаковки и попробуйте закрыть окно ещё раз.",
                )
                event.ignore()
                return

        event.accept()
