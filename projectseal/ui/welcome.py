"""Стартовый экран ProjectSeal."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .icons import get_icon, get_pixmap
from .theme import (
    AMBER,
    AMBER_SOFT,
    BLUE,
    BLUE_SOFT,
    GREEN,
    GREEN_SOFT,
    MUTED,
)
from .widgets import Banner, DropZone, FeatureCard, Pill


class WelcomePage(QWidget):
    folderRequested = Signal()
    folderDropped = Signal(Path)
    scanRequested = Signal()
    helpRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._folder: Path | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(38, 28, 38, 26)
        layout.setSpacing(16)

        # Верхняя строка
        top = QHBoxLayout()
        badge = Pill("●  Локальная проверка · без облака", "green")
        top.addWidget(badge)
        top.addStretch(1)
        version = QLabel("MVP 1.0")
        version.setProperty("role", "tiny")
        top.addWidget(version)
        layout.addLayout(top)

        title = QLabel("Подготовьте проект к передаче")
        title.setProperty("role", "h1")
        layout.addWidget(title)

        subtitle = QLabel(
            "ProjectSeal проверит папку на типовые секреты и мусор, покажет состав "
            "и соберёт чистый ZIP. Исходные файлы останутся на месте."
        )
        subtitle.setProperty("role", "subtitle")
        subtitle.setWordWrap(True)
        subtitle.setMaximumWidth(760)
        layout.addWidget(subtitle)

        self.dropzone = DropZone()
        self.dropzone.browseRequested.connect(self.folderRequested)
        self.dropzone.folderDropped.connect(self._on_folder_dropped)
        layout.addWidget(self.dropzone)

        self.error_banner = Banner("", "error")
        self.error_banner.hide()
        layout.addWidget(self.error_banner)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.scan_button = QPushButton("Проверить проект")
        self.scan_button.setProperty("role", "primary")
        self.scan_button.setProperty("big", True)
        self.scan_button.setIcon(get_icon("play", "#FFFFFF", 18))
        self.scan_button.setIconSize(QSize(18, 18))
        self.scan_button.setEnabled(False)
        self.scan_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_button.clicked.connect(self.scanRequested)
        actions.addWidget(self.scan_button)

        self.help_button = QPushButton("Как это работает")
        self.help_button.setProperty("role", "secondary")
        self.help_button.setIcon(get_icon("info", MUTED, 17))
        self.help_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.help_button.clicked.connect(self.helpRequested)
        actions.addWidget(self.help_button)
        actions.addStretch(1)

        self.hint_label = QLabel("Сначала выберите папку проекта")
        self.hint_label.setProperty("role", "tiny")
        actions.addWidget(self.hint_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(actions)

        # Три преимущества
        cards = QHBoxLayout()
        cards.setSpacing(12)
        cards.addWidget(
            FeatureCard(
                "shield-check",
                GREEN,
                GREEN_SOFT,
                "Секреты под контролем",
                "Ищем .env, приватные ключи и типовые токены. "
                "Значения маскируются и не попадают в архив.",
            ),
            1,
        )
        cards.addWidget(
            FeatureCard(
                "trash",
                AMBER,
                AMBER_SOFT,
                "Мусор не попадёт в ZIP",
                "node_modules, venv, __pycache__, .git, кэши, сборки и логи "
                "исключаются автоматически.",
            ),
            1,
        )
        cards.addWidget(
            FeatureCard(
                "archive",
                BLUE,
                BLUE_SOFT,
                "Готовый архив",
                "Чистый ZIP с сохранением структуры папок. "
                "Исходная папка не изменяется.",
            ),
            1,
        )
        layout.addLayout(cards)

        note = QHBoxLayout()
        note.setSpacing(7)
        note_icon = QLabel()
        note_icon.setPixmap(get_pixmap("info", MUTED, 15))
        note.addWidget(note_icon)
        note_text = QLabel(
            "ProjectSeal — предварительная проверка, а не гарантия безопасности. "
            "Не заменяет аудит и профессиональные сканеры вроде Gitleaks."
        )
        note_text.setProperty("role", "tiny")
        note_text.setWordWrap(True)
        note.addWidget(note_text, 1)
        layout.addLayout(note)

        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)

    @property
    def folder(self) -> Path | None:
        return self._folder

    def set_folder(self, folder: Path | None) -> None:
        self._folder = folder
        self.dropzone.set_folder(folder)
        self.scan_button.setEnabled(folder is not None)
        if folder is None:
            self.hint_label.setText("Сначала выберите папку проекта")
        else:
            self.hint_label.setText("Папка готова. Обычно проверка занимает меньше минуты.")
        self.clear_error()

    def set_error(self, message: str) -> None:
        self.error_banner.set_message(message, "error")
        self.error_banner.show()

    def clear_error(self) -> None:
        self.error_banner.hide()

    def _on_folder_dropped(self, folder: Path) -> None:
        self.folderDropped.emit(folder)
