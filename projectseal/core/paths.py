"""Безопасная работа с путями, чтение файлов и форматирование размеров."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
from typing import Final

_BINARY_SAMPLE: Final[int] = 8192


def human_size(size: int | float) -> str:
    """Человекочитаемый размер с запятой как десятичным разделителем."""
    value = float(max(0, size))
    if value < 1024:
        return f"{int(value)} Б"
    for unit in ("КБ", "МБ", "ГБ", "ТБ"):
        value /= 1024.0
        if value < 1024 or unit == "ТБ":
            if value >= 100:
                text = f"{value:.0f}"
            elif value >= 10:
                text = f"{value:.1f}"
            else:
                text = f"{value:.1f}"
            return f"{text.replace('.', ',')} {unit}"
    return f"{value:.1f} ТБ"


def is_within(path: str | Path, root: str | Path) -> bool:
    """Проверить, находится ли реальный путь внутри корня (без обхода ..)."""
    try:
        real_path = os.path.realpath(os.fspath(path))
        real_root = os.path.realpath(os.fspath(root))
        return os.path.commonpath([real_path, real_root]) == real_root
    except (ValueError, OSError):
        return False


def normalize_relative(relative: str) -> str:
    return relative.replace("\\", "/").strip("/")


def sanitize_arcname(relative: str) -> str | None:
    """Безопасное имя внутри ZIP: без абсолютных путей, ``..`` и дисков."""
    normalized = normalize_relative(relative)
    if not normalized:
        return None
    if "\x00" in normalized:
        return None
    pure = PurePosixPath(normalized)
    if pure.is_absolute():
        return None
    parts = pure.parts
    if not parts:
        return None
    for part in parts:
        if part in ("", ".", ".."):
            return None
        if part.endswith(":"):
            return None
    return str(pure)


def read_limited(path: str | Path, max_bytes: int) -> tuple[bytes, bool]:
    """Прочитать не более ``max_bytes`` байт, не переходя по симлинкам.

    Возвращает ``(data, truncated)``. ``O_NOFOLLOW`` защищает от гонки, когда
    файл подменили символической ссылкой после обхода каталога.
    """
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = os.open(path, flags)
    try:
        with os.fdopen(fd, "rb", closefd=True) as handle:
            data = handle.read(max_bytes + 1)
    except Exception:
        # fdopen уже закрыл дескриптор; повторное закрытие не требуется.
        raise
    truncated = len(data) > max_bytes
    return (data[:max_bytes] if truncated else data, truncated)


def looks_binary(data: bytes) -> bool:
    """Эвристика текстового файла: NUL-байты и доля управляющих символов."""
    sample = data[:_BINARY_SAMPLE]
    if not sample:
        return False
    if b"\x00" in sample:
        return True
    try:
        sample.decode("utf-8")
        return False
    except UnicodeDecodeError:
        pass
    control = sum(1 for byte in sample if byte < 9 or 13 < byte < 32)
    return (control / len(sample)) > 0.05


def decode_text(data: bytes) -> str:
    return data.decode("utf-8-sig", errors="replace")


def source_snapshot(path: str | Path) -> tuple[int, int] | None:
    try:
        stat = os.stat(path, follow_symlinks=False)
        return (stat.st_size, stat.st_mtime_ns)
    except OSError:
        return None


def display_path(path: str | Path, root: str | Path | None = None) -> str:
    """Короткий путь для заголовка: имя проекта и родительская папка."""
    p = Path(path)
    if root is not None:
        try:
            return str(p.relative_to(root))
        except ValueError:
            pass
    return str(p)
