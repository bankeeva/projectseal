"""Маскирование секретов и форматирование значений для интерфейса.

Главное правило: полное значение секрета никогда не попадает в UI, лог,
отчёт или имя файла. Функции модуля не зависят от PySide6.
"""

from __future__ import annotations

import re
from typing import Final

MASK_CHAR: Final[str] = "•"
MAX_PREVIEW_LEN: Final[int] = 96

# Известные префиксы токенов помогают пользователю понять тип находки,
# не раскрывая значение. Оставляем только сам префикс.
KNOWN_PREFIXES: Final[tuple[str, ...]] = (
    "sk-proj-",
    "sk-ant-",
    "sk_live_",
    "sk_test_",
    "rk_live_",
    "rk_test_",
    "ghp_",
    "gho_",
    "ghu_",
    "ghs_",
    "ghr_",
    "xoxb-",
    "xoxp-",
    "xoxa-",
    "xoxr-",
    "xoxs-",
    "AKIA",
    "ASIA",
    "AIza",
    "npm_",
    "pypi-",
    "eyJ",
)

_QUOTES = " \t\r\n\"'`"


def clean_value(value: str) -> str:
    return value.strip(_QUOTES)


def mask_secret(value: str, *, visible_prefix: int = 0, visible_suffix: int = 0) -> str:
    """Вернуть безопасное представление значения.

    По умолчанию раскрываются не более четырёх символов, а для известных
    префиксов — только префикс. Короткие значения скрываются полностью.
    """
    cleaned = clean_value(value)
    if not cleaned:
        return MASK_CHAR * 8

    for prefix in KNOWN_PREFIXES:
        if cleaned.startswith(prefix):
            return prefix + MASK_CHAR * 8

    if visible_prefix or visible_suffix:
        prefix = cleaned[: max(0, visible_prefix)]
        suffix = cleaned[-max(0, visible_suffix) :] if visible_suffix else ""
        return f"{prefix}{MASK_CHAR * 6}{suffix}"

    if len(cleaned) <= 8:
        return MASK_CHAR * 8
    return f"{cleaned[:2]}{MASK_CHAR * 6}{cleaned[-2:]}"


def clip_preview(text: str, limit: int = MAX_PREVIEW_LEN) -> str:
    """Однострочный фрагмент для таблицы: без переводов строк и мусора."""
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) > limit:
        normalized = normalized[: limit - 1].rstrip() + "…"
    return normalized


def format_assignment_preview(key: str, value: str) -> str:
    """Превью вида ``DB_PASSWORD = ••••••••``."""
    safe_key = re.sub(r"[\r\n]+", " ", key).strip().strip("\"'`")
    safe_key = safe_key[:40]
    return clip_preview(f"{safe_key} = {mask_secret(value)}")


def format_typed_preview(title: str, value: str) -> str:
    """Превью вида ``GitHub token: ghp_••••••••``."""
    return clip_preview(f"{title}: {mask_secret(value)}")


def contains_secret(text: str, value: str) -> bool:
    """True, если полное значение всё ещё присутствует в строке (для тестов)."""
    cleaned = clean_value(value)
    return bool(cleaned) and cleaned in text
