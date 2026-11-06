"""Внутренние структуры данных (DTO), которыми обмениваются ядро и интерфейс.

Модуль не зависит от PySide6: сканер и экспортёр можно тестировать отдельно.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Iterable


class Category(str, Enum):
    """Категория файла в результате проверки."""

    SAFE = "safe"
    JUNK = "junk"
    SECRET = "secret"

    @property
    def title(self) -> str:
        return {
            Category.SAFE: "Будет упаковано",
            Category.JUNK: "Мусор",
            Category.SECRET: "Риски",
        }[self]

    @property
    def short_title(self) -> str:
        return {
            Category.SAFE: "Безопасно",
            Category.JUNK: "Исключено",
            Category.SECRET: "Риск",
        }[self]


SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "unknown": 4,
    "info": 5,
}

SEVERITY_TITLES = {
    "critical": "критический",
    "high": "высокий",
    "medium": "средний",
    "low": "низкий",
    "unknown": "не проверено",
    "info": "информация",
}


@dataclass
class FileItem:
    """Один элемент результата: файл, папка-мусор или символическая ссылка."""

    relative_path: str
    category: Category
    reason: str
    file_size: int = 0
    preview: str = ""
    is_dir: bool = False
    child_count: int = 0
    count_capped: bool = False
    rule_id: str = ""
    severity: str = "info"
    selected: bool = True
    title: str = ""

    def __post_init__(self) -> None:
        if not self.title:
            self.title = display_name(self.relative_path)
        if self.category is not Category.SAFE:
            self.selected = False
        if self.severity not in SEVERITY_ORDER:
            self.severity = "info"

    @property
    def is_safe(self) -> bool:
        return self.category is Category.SAFE

    @property
    def can_select(self) -> bool:
        return self.category is Category.SAFE

    @property
    def severity_title(self) -> str:
        return SEVERITY_TITLES.get(self.severity, self.severity)

    @property
    def included(self) -> bool:
        return self.category is Category.SAFE and self.selected

    @property
    def files_count(self) -> int:
        """Сколько файлов представляет элемент (для папок-мусора — содержимое)."""
        if self.is_dir:
            return max(1, self.child_count)
        return 1

    def sort_key(self) -> tuple:
        return (SEVERITY_ORDER.get(self.severity, 9), self.relative_path.lower())


def display_name(path: str) -> str:
    """Имя файла без зависимости от платформы (для отображения)."""
    cleaned = path.replace("\\", "/").rstrip("/")
    return PurePosixPath(cleaned).name if cleaned else path


@dataclass(frozen=True)
class ScanError:
    """Некритическая ошибка или предупреждение во время проверки."""

    relative_path: str
    message: str
    kind: str = "read"  # read | permission | symlink | limit | skipped | other

    def as_line(self) -> str:
        if self.relative_path:
            return f"{self.relative_path} — {self.message}"
        return self.message


@dataclass
class ScanSummary:
    """Итоговая сводка проверки."""

    total_files: int = 0
    secrets_found: int = 0
    junk_found: int = 0
    safe_to_pack: int = 0
    safe_selected: int = 0
    total_bytes: int = 0
    safe_bytes: int = 0
    safe_selected_bytes: int = 0
    junk_objects: int = 0
    dirs_scanned: int = 0
    errors_count: int = 0
    unverified_count: int = 0
    binary_files: int = 0
    large_files: int = 0
    duration_ms: int = 0
    limits_hit: list[str] = field(default_factory=list)
    junk_count_estimated: bool = False
    total_files_estimated: bool = False

    @property
    def has_risks(self) -> bool:
        return self.secrets_found > 0

    @property
    def has_limits(self) -> bool:
        return bool(self.limits_hit)


@dataclass
class ScanResult:
    """Полный результат проверки, живёт только в памяти."""

    root: Path
    items: list[FileItem] = field(default_factory=list)
    errors: list[ScanError] = field(default_factory=list)
    summary: ScanSummary = field(default_factory=ScanSummary)
    cancelled: bool = False

    def by_category(self, category: Category) -> list[FileItem]:
        return [item for item in self.items if item.category is category]

    @property
    def secrets(self) -> list[FileItem]:
        return self.by_category(Category.SECRET)

    @property
    def junk(self) -> list[FileItem]:
        return self.by_category(Category.JUNK)

    @property
    def safe(self) -> list[FileItem]:
        return self.by_category(Category.SAFE)

    @property
    def selected_safe(self) -> list[FileItem]:
        return [item for item in self.safe if item.selected]

    def selected_safe_paths(self) -> set[str]:
        return {item.relative_path for item in self.selected_safe}

    def item_by_path(self, relative_path: str) -> FileItem | None:
        for item in self.items:
            if item.relative_path == relative_path:
                return item
        return None

    def recompute_summary(self) -> ScanSummary:
        """Пересчитать сводку после изменения выбора файлов пользователем."""
        safe = self.safe
        selected = [item for item in safe if item.selected]
        self.summary.safe_to_pack = len(safe)
        self.summary.safe_selected = len(selected)
        self.summary.safe_bytes = sum(item.file_size for item in safe)
        self.summary.safe_selected_bytes = sum(item.file_size for item in selected)
        return self.summary


def iter_items(items: Iterable[FileItem]) -> Iterable[FileItem]:
    return iter(items)
