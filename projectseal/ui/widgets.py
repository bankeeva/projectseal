"""Переиспользуемые визуальные компоненты ProjectSeal."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QAbstractTableModel,
    QEvent,
    QModelIndex,
    QRect,
    QSize,
    QSortFilterProxyModel,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.models import Category, FileItem
from ..core.paths import human_size
from ..core.scanner import ScanProgress as ScanProgressDTO
from .icons import get_icon, get_pixmap
from .theme import (
    AMBER,
    AMBER_SOFT,
    BLUE,
    BLUE_SOFT,
    CATEGORY_COLORS,
    CATEGORY_SOFT,
    GREEN,
    GREEN_SOFT,
    INK,
    MUTED,
    MUTED_2,
    RED,
    RED_SOFT,
)


# ----------------------------------------------------------------------
# Вспомогательные функции
# ----------------------------------------------------------------------
def repolish(widget: QWidget) -> None:
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()


def set_prop(widget: QWidget, name: str, value: object) -> None:
    widget.setProperty(name, value)
    repolish(widget)


def plural_ru(number: int, forms: tuple[str, str, str]) -> str:
    """Русская форма слова: 1 файл, 2 файла, 5 файлов."""
    n = abs(number) % 100
    if 11 <= n <= 19:
        return forms[2]
    n %= 10
    if n == 1:
        return forms[0]
    if 2 <= n <= 4:
        return forms[1]
    return forms[2]


def elide_middle(text: str, font: QFont, width: int) -> str:
    return QFontMetrics(font).elidedText(text, Qt.TextElideMode.ElideMiddle, max(20, width))


class ElidedLabel(QLabel):
    """QLabel с корректным многоточием и полным текстом в подсказке."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.set_full_text(text)

    def set_full_text(self, text: str) -> None:
        self._full_text = (text or "").replace("\n", " ")
        self.setToolTip(self._full_text)
        self._update_elision()

    def full_text(self) -> str:
        return self._full_text

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_elision()

    def _update_elision(self) -> None:
        available = max(20, self.contentsRect().width())
        self.setText(
            QFontMetrics(self.font()).elidedText(
                self._full_text, Qt.TextElideMode.ElideMiddle, available
            )
        )


def make_icon_label(name: str, color: str, size: int = 18) -> QLabel:
    label = QLabel()
    label.setPixmap(get_pixmap(name, color, size))
    label.setFixedSize(size, size)
    label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    return label


# ----------------------------------------------------------------------
# Карточки и баннеры
# ----------------------------------------------------------------------
class Card(QFrame):
    def __init__(self, parent: QWidget | None = None, *, tone: str | None = None) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        if tone:
            self.setProperty("tone", tone)


class StatCard(QFrame):
    def __init__(
        self,
        title: str,
        value: str,
        hint: str,
        *,
        tone: str = "neutral",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("stat", True)
        self.setMinimumHeight(90)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        accent_color = {
            "red": RED,
            "amber": AMBER,
            "green": GREEN,
            "blue": BLUE,
            "neutral": "#D0D5DD",
        }.get(tone, "#D0D5DD")
        accent = QFrame()
        accent.setFixedWidth(4)
        accent.setMinimumHeight(44)
        accent.setStyleSheet(f"background: {accent_color}; border-radius: 2px;")
        layout.addWidget(accent)

        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setProperty("statLabel", True)
        self.value_label = QLabel(value)
        self.value_label.setProperty("statValue", True)
        self.value_label.setProperty("tone", tone)
        self.hint_label = QLabel(hint)
        self.hint_label.setProperty("statHint", True)
        texts.addWidget(self.title_label)
        texts.addWidget(self.value_label)
        texts.addWidget(self.hint_label)
        layout.addLayout(texts, 1)

    def set_value(self, value: str, hint: str | None = None) -> None:
        self.value_label.setText(value)
        if hint is not None:
            self.hint_label.setText(hint)


class Banner(QFrame):
    """Цветной информационный блок с иконкой и необязательным действием."""

    actionClicked = Signal()

    def __init__(
        self,
        text: str = "",
        tone: str = "info",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("banner", True)
        self.setProperty("tone", tone)
        self._tone = tone
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        self.icon = QLabel()
        self.icon.setFixedSize(18, 18)
        self.icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)

        self.label = QLabel(text)
        self.label.setProperty("bannerText", True)
        self.label.setProperty("tone", tone)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.label, 1)

        self.action = QPushButton()
        self.action.setProperty("role", "link")
        self.action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action.hide()
        self.action.clicked.connect(self.actionClicked)
        layout.addWidget(self.action, 0, Qt.AlignmentFlag.AlignTop)
        self._apply_icon()

    def _apply_icon(self) -> None:
        mapping = {
            "error": ("alert", RED),
            "warning": ("alert", AMBER),
            "success": ("check-circle", GREEN),
            "info": ("info", BLUE),
        }
        name, color = mapping.get(self._tone, ("info", BLUE))
        self.icon.setPixmap(get_pixmap(name, color, 18))

    def set_message(self, text: str, tone: str | None = None) -> None:
        self.label.setText(text)
        if tone is not None:
            self._tone = tone
            self.setProperty("tone", tone)
            self.label.setProperty("tone", tone)
            self._apply_icon()
            repolish(self)
            repolish(self.label)

    def set_action(self, text: str, visible: bool = True) -> None:
        self.action.setText(text)
        self.action.setVisible(visible and bool(text))


class Pill(QLabel):
    def __init__(self, text: str, tone: str = "green", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setProperty("role", "badge")
        self.setProperty("tone", tone)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class StepRow(QFrame):
    def __init__(
        self,
        number: int,
        title: str,
        subtitle: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("step", True)
        self.setProperty("active", False)
        self._number = number
        self.setMinimumHeight(54)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(11)

        self.number_label = QLabel(str(number))
        self.number_label.setProperty("stepNumber", True)
        self.number_label.setProperty("stepState", "idle")
        self.number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number_label.setFixedSize(27, 27)
        layout.addWidget(self.number_label, 0, Qt.AlignmentFlag.AlignTop)

        texts = QVBoxLayout()
        texts.setSpacing(1)
        self.title_label = QLabel(title)
        self.title_label.setProperty("stepTitle", True)
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setProperty("stepSubtitle", True)
        texts.addWidget(self.title_label)
        texts.addWidget(self.subtitle_label)
        layout.addLayout(texts, 1)

    def set_state(self, state: str) -> None:
        """state: idle | active | done."""
        self.number_label.setProperty("stepState", state)
        self.setProperty("active", state == "active")
        self.number_label.setText("✓" if state == "done" else str(self._number))
        repolish(self)
        repolish(self.number_label)


# ----------------------------------------------------------------------
# Зона выбора папки
# ----------------------------------------------------------------------
class DropZone(QFrame):
    folderDropped = Signal(Path)
    browseRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("dropzone", True)
        self.setProperty("hover", False)
        self.setProperty("filled", False)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(132)
        self.setAccessibleName("Выбор папки проекта")
        self._folder: Path | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 18, 18, 18)
        layout.setSpacing(18)

        self.icon_box = QFrame()
        self.icon_box.setFixedSize(64, 64)
        self.icon_box.setStyleSheet(
            "background: #F2F5F9; border-radius: 17px; border: 1px solid #E8EDF5;"
        )
        icon_layout = QVBoxLayout(self.icon_box)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        self.icon_label = QLabel()
        self.icon_label.setPixmap(get_pixmap("folder-plus", MUTED, 30))
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(self.icon_label)
        layout.addWidget(self.icon_box, 0, Qt.AlignmentFlag.AlignVCenter)

        texts = QVBoxLayout()
        texts.setSpacing(3)
        self.title_label = QLabel("Перетащите папку проекта сюда")
        self.title_label.setProperty("dropTitle", True)
        self.subtitle_label = QLabel("или нажмите, чтобы выбрать папку на компьютере")
        self.subtitle_label.setProperty("dropSubtitle", True)
        self.path_label = ElidedLabel("")
        self.path_label.setProperty("role", "path")
        self.path_label.hide()
        texts.addWidget(self.title_label)
        texts.addWidget(self.subtitle_label)
        texts.addSpacing(3)
        texts.addWidget(self.path_label)
        layout.addLayout(texts, 1)

        self.browse_button = QPushButton("Обзор…")
        self.browse_button.setProperty("role", "secondary")
        self.browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_button.clicked.connect(self.browseRequested)
        layout.addWidget(self.browse_button, 0, Qt.AlignmentFlag.AlignVCenter)

    @property
    def folder(self) -> Path | None:
        return self._folder

    def set_folder(self, folder: Path | None) -> None:
        self._folder = folder
        if folder is None:
            self.setProperty("filled", False)
            self.title_label.setText("Перетащите папку проекта сюда")
            self.subtitle_label.setText("или нажмите, чтобы выбрать папку на компьютере")
            self.path_label.hide()
            self.browse_button.setText("Обзор…")
            self.icon_label.setPixmap(get_pixmap("folder-plus", MUTED, 30))
            self.icon_box.setStyleSheet(
                "background: #F2F5F9; border-radius: 17px; border: 1px solid #E8EDF5;"
            )
        else:
            self.setProperty("filled", True)
            self.title_label.setText("Папка проекта выбрана")
            self.subtitle_label.setText("Нажмите на карточку, чтобы выбрать другую папку")
            self.path_label.set_full_text(str(folder))
            self.path_label.show()
            self.browse_button.setText("Изменить")
            self.icon_label.setPixmap(get_pixmap("folder", GREEN, 30))
            self.icon_box.setStyleSheet(
                f"background: {GREEN_SOFT}; border-radius: 17px; border: 1px solid #BFE9D8;"
            )
        repolish(self)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.browseRequested.emit()
        super().mousePressEvent(event)

    def enterEvent(self, event: QEvent) -> None:  # noqa: N802
        if not self.property("filled"):
            self.setProperty("hover", True)
            repolish(self)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802
        self.setProperty("hover", False)
        repolish(self)
        super().leaveEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if self._first_local_folder(event) is not None:
            event.acceptProposedAction()
            self.setProperty("hover", True)
            repolish(self)
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if self._first_local_folder(event) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self.setProperty("hover", False)
        repolish(self)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        folder = self._first_local_folder(event)
        self.setProperty("hover", False)
        repolish(self)
        if folder is not None:
            event.acceptProposedAction()
            self.folderDropped.emit(folder)
        else:
            event.ignore()

    @staticmethod
    def _first_local_folder(event) -> Path | None:
        mime = event.mimeData()
        if not mime.hasUrls():
            return None
        for url in mime.urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.is_dir():
                    return path
        return None


class FeatureCard(QFrame):
    def __init__(
        self,
        icon_name: str,
        color: str,
        soft_color: str,
        title: str,
        text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        self.setProperty("tone", "flat")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(9)

        icon_box = QFrame()
        icon_box.setFixedSize(36, 36)
        icon_box.setStyleSheet(f"background: {soft_color}; border-radius: 10px;")
        box_layout = QVBoxLayout(icon_box)
        box_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel()
        icon_label.setPixmap(get_pixmap(icon_name, color, 19))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_layout.addWidget(icon_label)
        layout.addWidget(icon_box)

        title_label = QLabel(title)
        title_label.setProperty("role", "h3")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)
        text_label = QLabel(text)
        text_label.setProperty("role", "subtitle")
        text_label.setWordWrap(True)
        layout.addWidget(text_label)
        layout.addStretch(1)


# ----------------------------------------------------------------------
# Модель таблицы файлов
# ----------------------------------------------------------------------
SORT_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class FileTableModel(QAbstractTableModel):
    HEADERS = ("", "Файл", "Причина", "Размер", "Фрагмент")
    COL_CHECK = 0
    COL_PATH = 1
    COL_REASON = 2
    COL_SIZE = 3
    COL_PREVIEW = 4

    selectionChanged = Signal()

    def __init__(
        self,
        items: list[FileItem],
        *,
        show_checkboxes: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._items = list(items)
        self._show_checkboxes = show_checkboxes

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._items)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 5 if not parent.isValid() else 0

    def item_at(self, row: int) -> FileItem | None:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid():
            return None
        item = self._items[index.row()]
        column = index.column()

        if role == int(Qt.ItemDataRole.DisplayRole):
            if column == self.COL_PATH:
                return item.relative_path
            if column == self.COL_REASON:
                if item.is_dir and item.child_count:
                    suffix = "+" if item.count_capped else ""
                    return f"{item.reason} ({item.child_count}{suffix} файлов)"
                return item.reason
            if column == self.COL_SIZE:
                if item.is_dir:
                    return human_size(item.file_size)
                return human_size(item.file_size)
            if column == self.COL_PREVIEW:
                return item.preview or "—"
            return ""

        if role == SORT_ROLE:
            if column == self.COL_PATH:
                return item.relative_path.lower()
            if column == self.COL_REASON:
                return item.reason.lower()
            if column == self.COL_SIZE:
                return item.file_size
            if column == self.COL_PREVIEW:
                return item.preview.lower()
            return ""

        if role == int(Qt.ItemDataRole.ToolTipRole):
            lines = [item.relative_path, item.reason]
            if item.preview:
                lines.append(f"Фрагмент: {item.preview}")
            if item.is_dir:
                lines.append(f"Исключено файлов: {item.child_count}")
            return "\n".join(lines)

        if role == int(Qt.ItemDataRole.CheckStateRole) and column == self.COL_CHECK:
            if self._show_checkboxes and item.can_select:
                return (
                    Qt.CheckState.Checked
                    if item.selected
                    else Qt.CheckState.Unchecked
                )
            return None

        if role == int(Qt.ItemDataRole.TextAlignmentRole):
            if column == self.COL_SIZE:
                return (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter).value
            if column == self.COL_CHECK:
                return Qt.AlignmentFlag.AlignCenter.value
            return (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter).value

        if role == int(Qt.ItemDataRole.ForegroundRole):
            if column == self.COL_REASON:
                if item.category is Category.SECRET:
                    return QColor("#B42318" if item.severity in ("critical", "high") else "#B54708")
                if item.category is Category.JUNK:
                    return QColor(AMBER)
                return QColor("#475467")
            if column in (self.COL_SIZE, self.COL_PREVIEW):
                return QColor(MUTED_2)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if role != int(Qt.ItemDataRole.DisplayRole):
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.HEADERS):
            return self.HEADERS[section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == self.COL_CHECK and self._show_checkboxes:
            item = self._items[index.row()]
            if item.can_select:
                flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def setData(self, index: QModelIndex, value, role: int = int(Qt.ItemDataRole.EditRole)) -> bool:  # noqa: N802
        if not index.isValid():
            return False
        if role == int(Qt.ItemDataRole.CheckStateRole) and index.column() == self.COL_CHECK:
            item = self._items[index.row()]
            if not item.can_select:
                return False
            if isinstance(value, Qt.CheckState):
                checked = value is Qt.CheckState.Checked
            else:
                checked = int(value) == Qt.CheckState.Checked.value
            item.selected = checked
            self.dataChanged.emit(index, index, [int(Qt.ItemDataRole.CheckStateRole)])
            self.selectionChanged.emit()
            return True
        return False

    def set_all_selected(self, selected: bool) -> None:
        changed = False
        for item in self._items:
            if item.can_select and item.selected != selected:
                item.selected = selected
                changed = True
        if changed:
            top = self.index(0, self.COL_CHECK)
            bottom = self.index(len(self._items) - 1, self.COL_CHECK)
            self.dataChanged.emit(top, bottom, [int(Qt.ItemDataRole.CheckStateRole)])
            self.selectionChanged.emit()

    def selected_count(self) -> int:
        return sum(1 for item in self._items if item.can_select and item.selected)

    def all_selected(self) -> bool:
        selectable = [item for item in self._items if item.can_select]
        return bool(selectable) and all(item.selected for item in selectable)

    def selected_bytes(self) -> int:
        return sum(item.file_size for item in self._items if item.can_select and item.selected)


class FileFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._needle = ""
        self.setDynamicSortFilter(True)

    def set_needle(self, text: str) -> None:
        self._needle = (text or "").strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        if not self._needle:
            return True
        model = self.sourceModel()
        if not isinstance(model, FileTableModel):
            return True
        item = model.item_at(source_row)
        if item is None:
            return True
        haystack = f"{item.relative_path} {item.reason} {item.preview}".lower()
        return self._needle in haystack


# ----------------------------------------------------------------------
# Делегат таблицы
# ----------------------------------------------------------------------
class FileTableDelegate(QStyledItemDelegate):
    def __init__(self, parent: QWidget | None = None, *, show_checkboxes: bool = False) -> None:
        super().__init__(parent)
        self._show_checkboxes = show_checkboxes

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        return QSize(120, 50)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        model = index.model()
        item = None
        source = model
        if isinstance(source, QSortFilterProxyModel):
            source = source.sourceModel()
        if isinstance(source, FileTableModel):
            item = source.item_at(index.row())
        if item is None:
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected:
            background = QColor("#F0FAF6")
        elif hover:
            background = QColor("#FAFCFE")
        elif index.row() % 2 == 1:
            background = QColor("#FCFDFE")
        else:
            background = QColor("#FFFFFF")
        painter.fillRect(rect, background)
        painter.setPen(QPen(QColor("#F1F4F9"), 1))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        column = index.column()
        if column == FileTableModel.COL_CHECK:
            self._paint_marker(painter, rect, item)
        elif column == FileTableModel.COL_PATH:
            self._paint_path(painter, rect, item)
        elif column == FileTableModel.COL_REASON:
            self._paint_text(
                painter,
                rect,
                item.reason,
                color=QColor(
                    "#B42318"
                    if item.category is Category.SECRET and item.severity in ("critical", "high")
                    else (AMBER if item.category is Category.JUNK else "#475467")
                ),
                font_size=9.3,
                padding=(8, 8),
            )
        elif column == FileTableModel.COL_SIZE:
            text = human_size(item.file_size)
            self._paint_text(
                painter,
                rect,
                text,
                color=QColor(MUTED_2),
                font_size=8.8,
                padding=(6, 8),
                align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
        elif column == FileTableModel.COL_PREVIEW:
            self._paint_text(
                painter,
                rect,
                item.preview or "—",
                color=QColor(MUTED_2),
                font_size=8.5,
                padding=(8, 8),
                monospace=True,
            )
        painter.restore()

    def _paint_marker(self, painter: QPainter, rect: QRect, item: FileItem) -> None:
        center = rect.center()
        if self._show_checkboxes and item.can_select:
            box = QRect(center.x() - 9, center.y() - 9, 18, 18)
            painter.setPen(QPen(QColor(GREEN if item.selected else "#C9D3E2"), 1.4))
            painter.setBrush(QColor(GREEN if item.selected else "#FFFFFF"))
            painter.drawRoundedRect(box, 5, 5)
            if item.selected:
                path = QPainterPath()
                path.moveTo(box.left() + 4.5, box.center().y() + 0.5)
                path.lineTo(box.center().x() - 1.5, box.bottom() - 5.2)
                path.lineTo(box.right() - 4.0, box.top() + 5.0)
                painter.setPen(QPen(QColor("#FFFFFF"), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)
            return

        color = QColor(CATEGORY_COLORS.get(item.category.value, MUTED))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(center, 4, 4)

    def _paint_path(self, painter: QPainter, rect: QRect, item: FileItem) -> None:
        icon_name = {
            Category.SECRET: "alert",
            Category.JUNK: "trash",
            Category.SAFE: "file",
        }[item.category]
        color = CATEGORY_COLORS.get(item.category.value, MUTED)
        icon_size = 16
        icon_rect = QRect(rect.left() + 9, rect.center().y() - icon_size // 2, icon_size, icon_size)
        painter.drawPixmap(icon_rect, get_pixmap(icon_name, color, icon_size))

        font = QFont(option_font(painter))
        font.setPointSizeF(9.8)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(INK))
        text_rect = rect.adjusted(34, 0, -8, 0)
        text = QFontMetrics(font).elidedText(
            item.relative_path,
            Qt.TextElideMode.ElideMiddle,
            max(30, text_rect.width()),
        )
        painter.drawText(text_rect, (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter).value, text)

    def _paint_text(
        self,
        painter: QPainter,
        rect: QRect,
        text: str,
        *,
        color: QColor,
        font_size: float,
        padding: tuple[int, int],
        align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        monospace: bool = False,
    ) -> None:
        font = QFont(option_font(painter))
        font.setPointSizeF(font_size)
        if monospace:
            font.setFamilies(["SF Mono", "Menlo", "Consolas", "Courier New"])
        painter.setFont(font)
        painter.setPen(color)
        left, right = padding
        text_rect = rect.adjusted(left, 0, -right, 0)
        elided = QFontMetrics(font).elidedText(
            text, Qt.TextElideMode.ElideRight, max(20, text_rect.width())
        )
        painter.drawText(text_rect, int(align), elided)


def option_font(painter: QPainter) -> QFont:
    font = painter.font()
    if font.pointSizeF() <= 0:
        font.setPointSizeF(9.5)
    return font


# ----------------------------------------------------------------------
# Вкладка со списком файлов
# ----------------------------------------------------------------------
class FileTab(QWidget):
    selectionChanged = Signal()

    def __init__(
        self,
        category: Category,
        items: list[FileItem],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.category = category
        self.model = FileTableModel(
            items,
            show_checkboxes=category is Category.SAFE,
            parent=self,
        )
        self.proxy = FileFilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self._build_ui()
        self.model.selectionChanged.connect(self._on_selection_changed)
        self.update_empty()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setItemDelegate(
            FileTableDelegate(self.table, show_checkboxes=self.category is Category.SAFE)
        )
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.table.setMouseTracking(True)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setFrameShape(QFrame.Shape.NoFrame)
        self.table.verticalHeader().hide()
        header = self.table.horizontalHeader()
        header.setHighlightSections(False)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(28)
        header.setSectionResizeMode(FileTableModel.COL_CHECK, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(FileTableModel.COL_PATH, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(FileTableModel.COL_REASON, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(FileTableModel.COL_SIZE, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(FileTableModel.COL_PREVIEW, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(FileTableModel.COL_CHECK, 38)
        self.table.setColumnWidth(FileTableModel.COL_REASON, 350)
        self.table.setColumnWidth(FileTableModel.COL_SIZE, 82)
        self.table.setColumnWidth(FileTableModel.COL_PREVIEW, 190)
        self.table.verticalHeader().setDefaultSectionSize(50)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.empty = QWidget()
        empty_layout = QVBoxLayout(self.empty)
        empty_layout.setContentsMargins(24, 40, 24, 40)
        empty_layout.setSpacing(8)
        empty_layout.addStretch(1)
        self.empty_icon = QLabel()
        self.empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.empty_icon)
        self.empty_title = QLabel("")
        self.empty_title.setProperty("role", "h3")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.empty_title)
        self.empty_text = QLabel("")
        self.empty_text.setProperty("role", "subtitle")
        self.empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_text.setWordWrap(True)
        empty_layout.addWidget(self.empty_text)
        empty_layout.addStretch(1)

        self.stack.addWidget(self.table)
        self.stack.addWidget(self.empty)
        layout.addWidget(self.stack)

    def apply_filter(self, text: str) -> None:
        self.proxy.set_needle(text)
        self.update_empty()

    def update_empty(self) -> None:
        source_count = self.model.rowCount()
        visible = self.proxy.rowCount()
        if visible > 0:
            self.stack.setCurrentWidget(self.table)
            return
        self.stack.setCurrentWidget(self.empty)
        if source_count == 0:
            if self.category is Category.SECRET:
                title, text, icon, color = (
                    "Рисков не найдено",
                    "В этой папке не обнаружено типовых секретов и файлов с ключами.",
                    "shield-check",
                    GREEN,
                )
            elif self.category is Category.JUNK:
                title, text, icon, color = (
                    "Мусора не найдено",
                    "Не нашлось папок зависимостей, кэшей и служебных файлов.",
                    "check-circle",
                    GREEN,
                )
            else:
                title, text, icon, color = (
                    "Нет файлов для упаковки",
                    "Проверьте другую папку или измените запрос.",
                    "folder-open",
                    MUTED,
                )
        else:
            title, text, icon, color = (
                "Ничего не найдено",
                "Попробуйте изменить поисковый запрос.",
                "search",
                MUTED,
            )
        self.empty_icon.setPixmap(get_pixmap(icon, color, 38))
        self.empty_title.setText(title)
        self.empty_text.setText(text)

    def select_all(self, selected: bool) -> None:
        self.model.set_all_selected(selected)

    def selected_count(self) -> int:
        return self.model.selected_count()

    def selected_bytes(self) -> int:
        return self.model.selected_bytes()

    def all_selected(self) -> bool:
        return self.model.all_selected()

    def _on_selection_changed(self) -> None:
        self.selectionChanged.emit()


# ----------------------------------------------------------------------
# Экран проверки
# ----------------------------------------------------------------------
class ScanningPage(QWidget):
    cancelRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 32)
        outer.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)
        self.card = QFrame()
        self.card.setProperty("card", True)
        self.card.setMaximumWidth(620)
        self.card.setMinimumWidth(480)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(36, 32, 36, 30)
        card_layout.setSpacing(12)

        self.spinner = Spinner()
        card_layout.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignHCenter)
        card_layout.addSpacing(6)

        title = QLabel("Проверяем проект…")
        title.setProperty("role", "h2")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title)

        subtitle = QLabel(
            "Читаем файлы локально. Содержимое не отправляется в интернет, "
            "исходная папка не изменяется."
        )
        subtitle.setProperty("role", "subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(10)

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        path_row.addWidget(make_icon_label("folder", GREEN, 16))
        self.path_label = ElidedLabel("")
        self.path_label.setProperty("role", "path")
        path_row.addWidget(self.path_label, 1)
        card_layout.addLayout(path_row)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(9)
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 0)
        card_layout.addWidget(self.progress)
        card_layout.addSpacing(2)

        self.status_label = QLabel("Ищем файлы…")
        self.status_label.setProperty("role", "muted")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.status_label)
        card_layout.addSpacing(10)

        self.cancel_button = QPushButton("Отменить проверку")
        self.cancel_button.setProperty("role", "secondary")
        self.cancel_button.setIcon(get_icon("x", MUTED, 15))
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.clicked.connect(self._on_cancel)
        card_layout.addWidget(self.cancel_button, 0, Qt.AlignmentFlag.AlignHCenter)

        row.addWidget(self.card, 0)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

    def set_root(self, path: Path | str) -> None:
        self.path_label.set_full_text(str(path))

    def set_cancelling(self) -> None:
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Отмена…")
        self.status_label.setText("Останавливаем проверку…")

    def reset(self) -> None:
        self.cancel_button.setEnabled(True)
        self.cancel_button.setText("Отменить проверку")
        self.status_label.setText("Ищем файлы…")
        self.progress.setRange(0, 0)

    def set_progress(self, progress: ScanProgressDTO) -> None:
        if progress.phase == "walk":
            self.progress.setRange(0, 0)
            found = progress.found or progress.done
            self.status_label.setText(
                f"Сканируем папку… найдено {found} {plural_ru(found, ('объект', 'объекта', 'объектов'))}"
            )
            if progress.current:
                self.path_label.set_full_text(progress.current)
        elif progress.phase == "analyze":
            total = max(1, progress.total)
            self.progress.setRange(0, total)
            self.progress.setValue(min(progress.done, total))
            self.status_label.setText(
                f"Проверено {progress.done} из {progress.total} файлов"
            )
            if progress.current:
                self.path_label.set_full_text(progress.current)
        elif progress.phase == "done":
            self.progress.setRange(0, 100)
            self.progress.setValue(100)
            self.status_label.setText("Готово. Открываем результаты…")
        if self.spinner.isHidden():
            self.spinner.start()

    def showEvent(self, event) -> None:  # noqa: N802
        self.spinner.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802
        self.spinner.stop()
        super().hideEvent(event)

    def _on_cancel(self) -> None:
        self.set_cancelling()
        self.cancelRequested.emit()


class Spinner(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(54, 54)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        self._angle = (self._angle + 7) % 360
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(5, 5, -5, -5)
        painter.setPen(QPen(QColor("#E8EDF5"), 5))
        painter.drawArc(rect, 0, 360 * 16)
        pen = QPen(QColor(GREEN), 5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, -self._angle * 16, 110 * 16)


# ----------------------------------------------------------------------
# Обзор результата
# ----------------------------------------------------------------------
class ReviewPage(QWidget):
    backRequested = Signal()
    exportRequested = Signal()

    def __init__(self, result, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.result = result
        self._export_result = None
        self._build_ui()
        self._populate()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 20)
        layout.setSpacing(13)

        # Заголовок
        header = QHBoxLayout()
        header.setSpacing(10)
        self.back_button = QPushButton()
        self.back_button.setProperty("role", "icon")
        self.back_button.setIcon(get_icon("arrow-left", MUTED, 20))
        self.back_button.setIconSize(QSize(20, 20))
        self.back_button.setToolTip("Выбрать другую папку")
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.clicked.connect(self.backRequested)
        header.addWidget(self.back_button, 0, Qt.AlignmentFlag.AlignTop)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("Проверка завершена")
        title.setProperty("role", "h2")
        titles.addWidget(title)
        subtitle_row = QHBoxLayout()
        subtitle_row.setSpacing(8)
        self.path_label = ElidedLabel("")
        self.path_label.setProperty("role", "subtitle")
        subtitle_row.addWidget(self.path_label, 1)
        self.meta_label = QLabel("")
        self.meta_label.setProperty("role", "tiny")
        subtitle_row.addWidget(self.meta_label, 0)
        titles.addLayout(subtitle_row)
        header.addLayout(titles, 1)

        self.problems_button = QPushButton("Проблемы")
        self.problems_button.setProperty("role", "secondary")
        self.problems_button.setIcon(get_icon("alert", AMBER, 16))
        self.problems_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.problems_button.clicked.connect(self._show_problems)
        header.addWidget(self.problems_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        # Статистика
        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.risk_stat = StatCard("Риски", "0", "файлов с секретами", tone="red")
        self.junk_stat = StatCard("Мусор", "0", "файлов исключено", tone="amber")
        self.safe_stat = StatCard("Будет упаковано", "0", "безопасных файлов", tone="green")
        self.total_stat = StatCard("Всего", "0", "файлов проверено", tone="neutral")
        for card in (self.risk_stat, self.junk_stat, self.safe_stat, self.total_stat):
            stats.addWidget(card, 1)
        layout.addLayout(stats)

        # Баннеры
        self.banner = Banner("", "success")
        layout.addWidget(self.banner)
        self.limits_banner = Banner("", "warning")
        self.limits_banner.hide()
        layout.addWidget(self.limits_banner)

        # Карточка с вкладками
        self.tabs_card = QFrame()
        self.tabs_card.setProperty("card", True)
        tabs_layout = QVBoxLayout(self.tabs_card)
        tabs_layout.setContentsMargins(8, 8, 8, 8)
        tabs_layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.tabBar().setExpanding(False)

        self.secret_tab = FileTab(Category.SECRET, self.result.secrets)
        self.junk_tab = FileTab(Category.JUNK, self.result.junk)
        self.safe_tab = FileTab(Category.SAFE, self.result.safe)
        self.safe_tab.selectionChanged.connect(self._update_footer)

        self.tabs.addTab(self.secret_tab, "Риски")
        self.tabs.addTab(self.junk_tab, "Мусор")
        self.tabs.addTab(self.safe_tab, "Будет упаковано")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Строка поиска над вкладками: так подписи вкладок не обрезаются.
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 0)
        toolbar.setSpacing(8)
        hint = QLabel("Проверьте, что попадёт в архив")
        hint.setProperty("role", "tiny")
        toolbar.addWidget(hint)
        toolbar.addStretch(1)
        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText("Поиск по файлам и причинам")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(280)
        self.search.addAction(
            get_icon("search", MUTED_2, 15),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.search.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search)
        tabs_layout.addLayout(toolbar)

        tabs_layout.addWidget(self.tabs)
        layout.addWidget(self.tabs_card, 1)

        # Нижняя панель
        footer = QFrame()
        footer.setProperty("card", True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 12, 14, 12)
        footer_layout.setSpacing(12)

        self.footer_icon = QLabel()
        self.footer_icon.setPixmap(get_pixmap("archive", GREEN, 22))
        self.footer_icon.setFixedSize(38, 38)
        self.footer_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer_icon.setStyleSheet(
            f"background: {GREEN_SOFT}; border: 1px solid #BFE9D8; border-radius: 11px;"
        )
        footer_layout.addWidget(self.footer_icon)

        footer_texts = QVBoxLayout()
        footer_texts.setSpacing(1)
        self.footer_title = QLabel("В архив войдут 0 файлов")
        self.footer_title.setProperty("role", "h3")
        self.footer_sub = QLabel("Выберите хотя бы один файл")
        self.footer_sub.setProperty("role", "tiny")
        footer_texts.addWidget(self.footer_title)
        footer_texts.addWidget(self.footer_sub)
        footer_layout.addLayout(footer_texts, 1)

        self.select_all_button = QPushButton("Снять все")
        self.select_all_button.setProperty("role", "link")
        self.select_all_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_all_button.clicked.connect(self._toggle_select_all)
        footer_layout.addWidget(self.select_all_button, 0)

        self.export_button = QPushButton("Создать безопасный ZIP")
        self.export_button.setProperty("role", "primary")
        self.export_button.setIcon(get_icon("archive", "#FFFFFF", 18))
        self.export_button.setIconSize(QSize(18, 18))
        self.export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_button.clicked.connect(self.exportRequested)
        footer_layout.addWidget(self.export_button, 0)
        layout.addWidget(footer)

    def _populate(self) -> None:
        result = self.result
        summary = result.summary
        self.path_label.set_full_text(str(result.root))
        duration = summary.duration_ms / 1000.0
        duration_text = f"{duration:.1f}".replace(".", ",") + " с" if duration >= 0.1 else "< 0,1 с"
        file_word = plural_ru(summary.total_files, ("файл", "файла", "файлов"))
        self.meta_label.setText(
            f"{summary.total_files} {file_word}  •  {duration_text}  •  локально"
        )
        self.risk_stat.set_value(
            str(summary.secrets_found),
            "файлов с секретами" if summary.secrets_found else "секретов не найдено",
        )
        junk_hint = "файлов исключено"
        if summary.junk_count_estimated:
            junk_hint = "не менее файлов"
        self.junk_stat.set_value(str(summary.junk_found), junk_hint)
        self.safe_stat.set_value(
            str(summary.safe_to_pack),
            f"{human_size(summary.safe_bytes)} безопасных данных",
        )
        total_hint = "файлов проверено"
        if summary.total_files_estimated:
            total_hint = "файлов, оценка"
        self.total_stat.set_value(str(summary.total_files), total_hint)

        if summary.secrets_found:
            text = (
                f"Найдено {summary.secrets_found} "
                f"{plural_ru(summary.secrets_found, ('файл', 'файла', 'файлов'))} "
                "с потенциальными секретами. Они исключены из архива, значения замаскированы."
            )
            if summary.unverified_count:
                text += (
                    f" {summary.unverified_count} "
                    f"{plural_ru(summary.unverified_count, ('файл', 'файла', 'файлов'))} "
                    "не удалось прочитать — они тоже исключены."
                )
            self.banner.set_message(text, "error")
        else:
            text = "Потенциальных секретов не найдено. Проверьте список перед упаковкой."
            if summary.binary_files:
                text += (
                    f" {summary.binary_files} "
                    f"{plural_ru(summary.binary_files, ('бинарный файл', 'бинарных файла', 'бинарных файлов'))} "
                    "не проверялись по содержимому."
                )
            self.banner.set_message(text, "success")

        if summary.limits_hit:
            self.limits_banner.set_message(" ".join(summary.limits_hit), "warning")
            self.limits_banner.show()
        elif summary.large_files:
            self.limits_banner.set_message(
                f"{summary.large_files} "
                f"{plural_ru(summary.large_files, ('большой файл', 'больших файла', 'больших файлов'))} "
                "больше 5 МБ: содержимое не проверялось, файлы включены в архив.",
                "warning",
            )
            self.limits_banner.show()

        self.tabs.setTabText(0, f"Риски  {summary.secrets_found}")
        self.tabs.setTabText(1, f"Мусор  {summary.junk_found}")
        self.tabs.setTabText(2, f"В архив  {summary.safe_to_pack}")
        self.tabs.setTabToolTip(0, "Потенциальные секреты — исключены из архива")
        self.tabs.setTabToolTip(1, "Мусорные файлы и папки — исключены из архива")
        self.tabs.setTabToolTip(2, "Файлы, которые попадут в ZIP")
        self.tabs.setCurrentIndex(0 if summary.secrets_found else 2)
        self._update_footer()
        self.problems_button.setText(f"Проблемы  {summary.errors_count}")
        self.problems_button.setVisible(bool(result.errors))

    def _on_search(self, text: str) -> None:
        for tab in (self.secret_tab, self.junk_tab, self.safe_tab):
            tab.apply_filter(text)

    def _on_tab_changed(self, index: int) -> None:
        current = self.tabs.widget(index)
        is_safe = current is self.safe_tab
        self.select_all_button.setVisible(is_safe)
        self._update_footer()

    def _toggle_select_all(self) -> None:
        if self.safe_tab.all_selected():
            self.safe_tab.select_all(False)
        else:
            self.safe_tab.select_all(True)
        self._update_footer()

    def _update_footer(self) -> None:
        count = self.safe_tab.selected_count()
        total = self.safe_tab.model.rowCount()
        size = self.safe_tab.selected_bytes()
        word = plural_ru(count, ("файл", "файла", "файлов"))
        self.footer_title.setText(f"В архив войдут {count} {word}")
        if count:
            self.footer_sub.setText(
                f"{human_size(size)}  •  из {total} безопасных файлов"
            )
        else:
            self.footer_sub.setText("Выберите хотя бы один файл")
        self.export_button.setEnabled(count > 0)
        self.select_all_button.setText("Снять все" if self.safe_tab.all_selected() else "Выбрать все")
        self.select_all_button.setVisible(self.tabs.currentWidget() is self.safe_tab)
        if self._export_result is not None:
            self.export_button.setText("Создать ZIP ещё раз")
        else:
            self.export_button.setText("Создать безопасный ZIP")

    def selected_paths(self) -> set[str]:
        return {
            item.relative_path
            for item in self.result.safe
            if item.selected
        }

    def show_export_success(self, export_result) -> None:
        self._export_result = export_result
        self.banner.set_message(
            f"Архив «{export_result.archive_name}» создан и проверен. "
            f"{export_result.included_files} "
            f"{plural_ru(export_result.included_files, ('файл', 'файла', 'файлов'))}, "
            f"{human_size(export_result.archive_size)}.",
            "success",
        )
        self.banner.set_action("Показать в папке", True)
        if not getattr(self, "_banner_action_connected", False):
            self.banner.actionClicked.connect(self._open_archive_folder)
            self._banner_action_connected = True

    def _open_archive_folder(self) -> None:
        if self._export_result is None:
            return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self._export_result.archive_path.parent))
        )

    def _show_problems(self) -> None:
        from .dialogs import ProblemsDialog

        dialog = ProblemsDialog(self.result.errors, self)
        dialog.exec()



# ----------------------------------------------------------------------
# Всплывающее уведомление
# ----------------------------------------------------------------------
class Toast(QFrame):
    """Короткое сообщение поверх окна, не блокирующее работу."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setMaximumWidth(620)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 16, 10)
        layout.setSpacing(9)
        self.icon = QLabel()
        self.icon.setFixedSize(18, 18)
        layout.addWidget(self.icon)
        self.label = QLabel("")
        self.label.setObjectName("ToastText")
        self.label.setWordWrap(True)
        layout.addWidget(self.label, 1)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, text: str, tone: str = "info", duration: int = 3400) -> None:
        icon_name = {"success": "check-circle", "error": "alert", "warning": "alert"}.get(
            tone, "info"
        )
        self.icon.setPixmap(get_pixmap(icon_name, "#FFFFFF", 18))
        self.label.setText(text)
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self._timer.start(duration)

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        x = max(16, (parent.width() - self.width()) // 2)
        y = max(16, parent.height() - self.height() - 26)
        self.move(x, y)
