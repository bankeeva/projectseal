"""Исключения приложения с сообщениями, понятными обычному пользователю."""

from __future__ import annotations


class ProjectSealError(Exception):
    """Базовая ошибка ProjectSeal."""


class ExportError(ProjectSealError):
    """Не удалось создать или проверить архив."""


class ExportCancelled(ProjectSealError):
    """Пользователь отменил упаковку."""
