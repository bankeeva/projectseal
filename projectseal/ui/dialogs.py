"""Диалоговые окна ProjectSeal."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core.errors import ExportError
from ..core.exporter import ExportProgress, ExportResult
from ..core.models import ScanError
from ..core.paths import human_size
from ..runtime import error_log_path, logs_dir
from ..version import APP_DESCRIPTION, APP_NAME, COPYRIGHT, __version__
from .icons import app_icon, get_icon, get_pixmap
from .theme import (
    AMBER,
    AMBER_SOFT,
    BLUE,
    BLUE_SOFT,
    BORDER,
    CARD,
    GREEN,
    GREEN_SOFT,
    INK,
    MUTED,
    MUTED_2,
    NAVY,
    RED,
    RED_SOFT,
)
from .widgets import Banner, ElidedLabel, plural_ru


def _dialog_base(title: str, parent: QWidget | None, width: int = 620) -> tuple[QDialog, QVBoxLayout]:
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.setWindowIcon(app_icon())
    dialog.setMinimumWidth(width)
    dialog.setStyleSheet(f"QDialog {{ background: {CARD}; }}")
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(24, 22, 24, 20)
    layout.setSpacing(14)
    return dialog, layout


def reveal_in_file_manager(path: Path) -> None:
    """Открыть папку и, по возможности, выделить файл."""
    path = Path(path)
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
            return
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", str(path)])
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
    except OSError:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))


def open_logs_folder() -> None:
    directory = logs_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))


class ProblemsDialog(QDialog):
    def __init__(self, errors: list[ScanError], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Проблемы и предупреждения")
        self.setModal(True)
        self.setMinimumSize(700, 520)
        self.setWindowIcon(app_icon())
        self.setStyleSheet(f"QDialog {{ background: {CARD}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        icon_box = QLabel()
        icon_box.setFixedSize(44, 44)
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {AMBER_SOFT}; border-radius: 12px;")
        icon_box.setPixmap(get_pixmap("alert", AMBER, 24))
        header.addWidget(icon_box, 0, Qt.AlignmentFlag.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("Проблемы и предупреждения")
        title.setProperty("role", "h2")
        titles.addWidget(title)
        subtitle = QLabel(
            "Эти файлы не удалось прочитать, они пропущены или проверены не полностью. "
            "Файлы с риском не попадают в архив."
        )
        subtitle.setProperty("role", "subtitle")
        subtitle.setWordWrap(True)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)
        layout.addLayout(header)

        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.list.setSpacing(2)
        self.list.setStyleSheet(
            f"QListWidget {{ background: #FAFBFD; border: 1px solid {BORDER}; "
            "border-radius: 10px; padding: 6px; } "
            "QListWidget::item { padding: 8px; border-bottom: 1px solid #EEF2F7; }"
        )
        for error in errors:
            prefix = error.relative_path or "Проект"
            item = QListWidgetItem(f"{prefix}\n{error.message}")
            item.setIcon(get_icon("alert", AMBER, 16))
            font = item.font()
            font.setPointSizeF(9.2)
            item.setFont(font)
            item.setSizeHint(QSize(100, 52))
            self.list.addItem(item)
        if not errors:
            self.list.addItem("Проблем не обнаружено.")
        layout.addWidget(self.list, 1)

        footer = QHBoxLayout()
        log_button = QPushButton("Открыть журнал")
        log_button.setProperty("role", "ghost")
        log_button.setIcon(get_icon("external", MUTED, 15))
        log_button.setCursor(Qt.CursorShape.PointingHandCursor)
        log_button.clicked.connect(open_logs_folder)
        footer.addWidget(log_button)
        footer.addStretch(1)
        close_button = QPushButton("Закрыть")
        close_button.setProperty("role", "secondary")
        close_button.clicked.connect(self.accept)
        footer.addWidget(close_button)
        layout.addLayout(footer)


class ExportProgressDialog(QDialog):
    cancelRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Создание архива")
        self.setModal(True)
        self.setFixedWidth(560)
        self.setWindowIcon(app_icon())
        self.setStyleSheet(f"QDialog {{ background: {CARD}; }}")
        self._finished = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon_box = QLabel()
        icon_box.setFixedSize(48, 48)
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_box.setStyleSheet(f"background: {GREEN_SOFT}; border-radius: 13px;")
        icon_box.setPixmap(get_pixmap("archive", GREEN, 26))
        header.addWidget(icon_box, 0, Qt.AlignmentFlag.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("Создаём безопасный архив")
        title.setProperty("role", "h2")
        titles.addWidget(title)
        subtitle = QLabel(
            "В архив попадут только выбранные безопасные файлы. "
            "Исходная папка не изменяется."
        )
        subtitle.setProperty("role", "subtitle")
        subtitle.setWordWrap(True)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)
        layout.addLayout(header)
        layout.addSpacing(6)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(9)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.status = QLabel("Готовим архив…")
        self.status.setProperty("role", "muted")
        layout.addWidget(self.status)

        self.current = ElidedLabel("")
        self.current.setProperty("role", "path")
        self.current.hide()
        layout.addWidget(self.current)

        layout.addSpacing(6)
        self.cancel_button = QPushButton("Отменить упаковку")
        self.cancel_button.setProperty("role", "secondary")
        self.cancel_button.setIcon(get_icon("x", MUTED, 15))
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.clicked.connect(self._on_cancel)
        layout.addWidget(self.cancel_button, 0, Qt.AlignmentFlag.AlignHCenter)

    def set_progress(self, progress: ExportProgress) -> None:
        if progress.total > 0:
            self.progress.setRange(0, progress.total)
            self.progress.setValue(min(progress.done, progress.total))
            self.status.setText(
                f"Упаковано {progress.done} из {progress.total} "
                f"{plural_ru(progress.total, ('файла', 'файлов', 'файлов'))}"
            )
        else:
            self.progress.setRange(0, 0)
            self.status.setText(progress.message or "Готовим архив…")
        if progress.current:
            self.current.set_full_text(progress.current)
            self.current.show()
        elif progress.message:
            self.status.setText(progress.message)

    def set_indeterminate(self, text: str = "Проверяем архив…") -> None:
        self.progress.setRange(0, 0)
        self.status.setText(text)
        self.current.hide()

    def _on_cancel(self) -> None:
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Отмена…")
        self.status.setText("Останавливаем упаковку…")
        self.cancelRequested.emit()

    def finish(self, result: int = QDialog.DialogCode.Accepted) -> None:
        self._finished = True
        self.done(result)

    def reject(self) -> None:
        if self._finished:
            super().reject()
            return
        self._on_cancel()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._finished:
            super().closeEvent(event)
        else:
            event.ignore()


class SuccessDialog(QDialog):
    def __init__(self, result: ExportResult, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.export_result = result
        self.setWindowTitle("Архив готов")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setWindowIcon(app_icon())
        self.setStyleSheet(f"QDialog {{ background: {CARD}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 22)
        layout.setSpacing(12)

        top = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(get_pixmap("check-circle", GREEN, 54))
        icon.setFixedSize(58, 58)
        top.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("Архив готов")
        title.setProperty("role", "h2")
        titles.addWidget(title)
        subtitle = QLabel(
            "Чистый ZIP создан и проверен. Исходная папка осталась без изменений."
        )
        subtitle.setProperty("role", "subtitle")
        subtitle.setWordWrap(True)
        titles.addWidget(subtitle)
        top.addLayout(titles, 1)
        layout.addLayout(top)
        layout.addSpacing(4)

        info = QFrame()
        info.setProperty("card", True)
        info.setProperty("tone", "flat")
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(16, 14, 16, 14)
        info_layout.setSpacing(8)

        name = QLabel(result.archive_name)
        name.setProperty("role", "h3")
        info_layout.addWidget(name)
        path = ElidedLabel(str(result.archive_path.parent))
        path.setProperty("role", "tiny")
        info_layout.addWidget(path)

        stats = QHBoxLayout()
        stats.setSpacing(20)
        stats.addWidget(self._stat("Размер", human_size(result.archive_size)))
        stats.addWidget(self._stat("Файлов", str(result.included_files)))
        excluded = result.excluded_secret_files + result.excluded_junk_files
        stats.addWidget(self._stat("Исключено", str(excluded)))
        stats.addStretch(1)
        info_layout.addLayout(stats)
        layout.addWidget(info)

        if result.verified:
            verified = QHBoxLayout()
            verified.setSpacing(7)
            check = QLabel()
            check.setPixmap(get_pixmap("check-circle", GREEN, 16))
            verified.addWidget(check)
            label = QLabel("Целостность архива проверена")
            label.setProperty("role", "muted")
            verified.addWidget(label)
            verified.addStretch(1)
            layout.addLayout(verified)

        if result.skipped_files or result.warnings:
            warning = Banner(
                f"Некоторые файлы пропущены: {len(result.skipped_files) or len(result.warnings)}. "
                "Подробности можно посмотреть в журнале.",
                "warning",
            )
            layout.addWidget(warning)

        layout.addSpacing(4)
        buttons = QHBoxLayout()
        show_button = QPushButton("Показать в папке")
        show_button.setProperty("role", "primary")
        show_button.setIcon(get_icon("folder-open", "#FFFFFF", 17))
        show_button.setCursor(Qt.CursorShape.PointingHandCursor)
        show_button.clicked.connect(self._show_in_folder)
        buttons.addWidget(show_button)
        buttons.addStretch(1)
        details_button = QPushButton("Подробнее")
        details_button.setProperty("role", "ghost")
        details_button.setVisible(bool(result.warnings or result.skipped_files))
        details_button.clicked.connect(self._show_details)
        buttons.addWidget(details_button)
        done_button = QPushButton("Готово")
        done_button.setProperty("role", "secondary")
        done_button.clicked.connect(self.accept)
        buttons.addWidget(done_button)
        layout.addLayout(buttons)

    @staticmethod
    def _stat(title: str, value: str) -> QWidget:
        widget = QWidget()
        vbox = QVBoxLayout(widget)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        value_label = QLabel(value)
        font = QFont(value_label.font())
        font.setPointSizeF(12.5)
        font.setWeight(QFont.Weight.DemiBold)
        value_label.setFont(font)
        value_label.setStyleSheet(f"color: {INK};")
        title_label = QLabel(title)
        title_label.setProperty("role", "tiny")
        vbox.addWidget(value_label)
        vbox.addWidget(title_label)
        return widget

    def _show_in_folder(self) -> None:
        reveal_in_file_manager(self.export_result.archive_path)

    def _show_details(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        lines = list(self.export_result.warnings) + [
            f"Пропущен: {path}" for path in self.export_result.skipped_files
        ]
        box = QMessageBox(self)
        box.setWindowTitle("Подробности упаковки")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText("Некоторые файлы не попали в архив.")
        box.setDetailedText("\n".join(lines) if lines else "Подробностей нет.")
        box.exec()


class HelpDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Как работает ProjectSeal")
        self.setModal(True)
        self.setMinimumSize(660, 600)
        self.setWindowIcon(app_icon())
        self.setStyleSheet(f"QDialog {{ background: {CARD}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(get_pixmap("shield-check", GREEN, 32))
        header.addWidget(logo)
        title = QLabel("Как работает ProjectSeal")
        title.setProperty("role", "h2")
        header.addWidget(title)
        header.addStretch(1)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(0, 0, 8, 0)
        vbox.setSpacing(12)

        steps = [
            (
                "1",
                "Выберите папку",
                "Нажмите на карточку выбора или перетащите папку с проектом. "
                "Можно выбрать любую локальную папку — права администратора не нужны.",
            ),
            (
                "2",
                "Проверьте состав",
                "ProjectSeal покажет три списка: потенциальные секреты, мусор и файлы, "
                "которые попадут в архив. У каждого файла есть причина и замаскированный фрагмент.",
            ),
            (
                "3",
                "Создайте ZIP",
                "Снимите галочки с файлов, которые не хотите отправлять, и нажмите "
                "«Создать безопасный ZIP». Архив сохранится рядом с проектом.",
            ),
        ]
        for number, heading, text in steps:
            row = QHBoxLayout()
            badge = QLabel(number)
            badge.setFixedSize(28, 28)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                f"background: {GREEN_SOFT}; color: #067647; border-radius: 14px; "
                "font-weight: 700;"
            )
            row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
            block = QVBoxLayout()
            block.setSpacing(2)
            h = QLabel(heading)
            h.setProperty("role", "h3")
            block.addWidget(h)
            p = QLabel(text)
            p.setProperty("role", "subtitle")
            p.setWordWrap(True)
            block.addWidget(p)
            row.addLayout(block, 1)
            vbox.addLayout(row)

        vbox.addSpacing(6)
        vbox.addWidget(self._section(
            "Что проверяется",
            "Файлы .env, приватные ключи, хранилища ключей и типовые токены "
            "(AWS, GitHub, OpenAI, Stripe, Slack, Google, JWT). Отдельно исключаются "
            "папки node_modules, venv, __pycache__, .git, кэши, сборки и логи.",
        ))
        vbox.addWidget(self._section(
            "Границы проверки",
            "ProjectSeal выполняет предварительную проверку. Он не анализирует историю Git, "
            "содержимое бинарных файлов и не знает все возможные форматы секретов. "
            "Это не гарантия безопасности и не замена аудиту или Gitleaks.",
            "warning",
        ))
        vbox.addWidget(self._section(
            "Приватность",
            "Вся обработка идёт на вашем компьютере. Приложение не отправляет файлы в сеть, "
            "не требует аккаунта и не изменяет исходную папку. Архив создаётся только по "
            "явной команде.",
            "success",
        ))
        vbox.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_button = QPushButton("Понятно")
        close_button.setProperty("role", "primary")
        close_button.clicked.connect(self.accept)
        footer.addWidget(close_button)
        layout.addLayout(footer)

    @staticmethod
    def _section(title: str, text: str, tone: str = "info") -> QFrame:
        frame = QFrame()
        frame.setProperty("banner", True)
        frame.setProperty("tone", tone)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(3)
        h = QLabel(title)
        h.setProperty("bannerText", True)
        h.setProperty("tone", tone)
        font = QFont(h.font())
        font.setWeight(QFont.Weight.DemiBold)
        h.setFont(font)
        layout.addWidget(h)
        p = QLabel(text)
        p.setProperty("bannerText", True)
        p.setProperty("tone", tone)
        p.setWordWrap(True)
        layout.addWidget(p)
        return frame


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"О программе {APP_NAME}")
        self.setModal(True)
        self.setFixedWidth(520)
        self.setWindowIcon(app_icon())
        self.setStyleSheet(f"QDialog {{ background: {CARD}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 22)
        layout.setSpacing(10)

        top = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(get_pixmap("shield-check", GREEN, 42))
        top.addWidget(logo)
        titles = QVBoxLayout()
        name = QLabel(APP_NAME)
        name.setProperty("role", "h2")
        titles.addWidget(name)
        version = QLabel(f"Версия {__version__}")
        version.setProperty("role", "tiny")
        titles.addWidget(version)
        top.addLayout(titles, 1)
        layout.addLayout(top)

        description = QLabel(APP_DESCRIPTION)
        description.setWordWrap(True)
        description.setProperty("role", "subtitle")
        layout.addWidget(description)
        layout.addSpacing(4)

        tech = QLabel(
            "Python 3.12 · PySide6 · zipfile · стандартная библиотека. "
            "Локальное приложение без сервера и облака."
        )
        tech.setWordWrap(True)
        tech.setProperty("role", "muted")
        layout.addWidget(tech)

        license_note = QLabel(
            "PySide6 используется по лицензии LGPL с динамической линковкой. "
            "Перед коммерческим выпуском необходима отдельная проверка лицензии."
        )
        license_note.setWordWrap(True)
        license_note.setProperty("role", "tiny")
        layout.addWidget(license_note)

        copyright_label = QLabel(COPYRIGHT)
        copyright_label.setProperty("role", "tiny")
        layout.addWidget(copyright_label)
        layout.addSpacing(4)

        close_button = QPushButton("Закрыть")
        close_button.setProperty("role", "secondary")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, 0, Qt.AlignmentFlag.AlignRight)


class ErrorDialog(QDialog):
    """Понятная ошибка без технического traceback на первом плане."""

    def __init__(
        self,
        title: str,
        message: str,
        *,
        detail: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setWindowIcon(app_icon())
        self.setStyleSheet(f"QDialog {{ background: {CARD}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 20)
        layout.setSpacing(12)

        header = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(get_pixmap("alert", RED, 38))
        icon.setFixedSize(40, 40)
        header.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        title_label = QLabel(title)
        title_label.setProperty("role", "h2")
        title_label.setWordWrap(True)
        header.addWidget(title_label, 1)
        layout.addLayout(header)

        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setProperty("role", "subtitle")
        layout.addWidget(message_label)

        if detail:
            details = QLabel(f"Подробности сохранены в журнале:\n{error_log_path()}")
            details.setProperty("role", "tiny")
            details.setWordWrap(True)
            layout.addWidget(details)

        buttons = QHBoxLayout()
        log_button = QPushButton("Открыть журнал")
        log_button.setProperty("role", "ghost")
        log_button.clicked.connect(open_logs_folder)
        buttons.addWidget(log_button)
        buttons.addStretch(1)
        ok = QPushButton("Закрыть")
        ok.setProperty("role", "secondary")
        ok.clicked.connect(self.accept)
        buttons.addWidget(ok)
        layout.addLayout(buttons)
