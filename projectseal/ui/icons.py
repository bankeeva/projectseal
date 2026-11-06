"""Векторные иконки интерфейса без внешних зависимостей.

SVG-строки рисуются через QtSvg и тонируются в нужный цвет. Это позволяет
сохранять единый стиль на Windows и macOS и не тащить PNG-наборы.
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from ..runtime import resource_path


def _svg(body: str, color: str, width: int = 2) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="none" stroke="{color}" '
        f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round">'
        f"{body}</svg>"
    ).replace("{color}", color)


_SVG_BODIES: dict[str, str] = {
    "shield": '<path d="M12 3 20 6v6c0 5-3.4 8.3-8 9.8C7.4 20.3 4 17 4 12V6l8-3Z"/>',
    "shield-check": (
        '<path d="M12 3 20 6v6c0 5-3.4 8.3-8 9.8C7.4 20.3 4 17 4 12V6l8-3Z"/>'
        '<path d="m8.4 12.1 2.4 2.4 4.8-4.9"/>'
    ),
    "folder": (
        '<path d="M3.5 7.5A2.5 2.5 0 0 1 6 5h3.4l2 2H18a2.5 2.5 0 0 1 2.5 2.5v7A2.5 2.5 0 0 1 18 19H6a2.5 2.5 0 0 1-2.5-2.5Z"/>'
    ),
    "folder-plus": (
        '<path d="M3.5 7.5A2.5 2.5 0 0 1 6 5h3.4l2 2H18a2.5 2.5 0 0 1 2.5 2.5v7A2.5 2.5 0 0 1 18 19H6a2.5 2.5 0 0 1-2.5-2.5Z"/>'
        '<path d="M12 10.8v5.4M9.3 13.5h5.4"/>'
    ),
    "folder-open": (
        '<path d="M3.5 8V6.8A1.8 1.8 0 0 1 5.3 5h3.5l1.8 1.8h6.8a1.8 1.8 0 0 1 1.8 1.8v1.2"/>'
        '<path d="M4.2 19.5 6.7 11h15l-2.6 8.5Z"/>'
    ),
    "search": '<circle cx="11" cy="11" r="6.2"/><path d="m16 16 4 4"/>',
    "alert": (
        '<path d="M10.3 4.3 2.8 17.2A1.4 1.4 0 0 0 4 19.3h16a1.4 1.4 0 0 0 1.2-2.1L13.7 4.3a2 2 0 0 0-3.4 0Z"/>'
        '<path d="M12 9v4.2M12 16.6h.01"/>'
    ),
    "trash": (
        '<path d="M4 7h16M9 7V5.3A1.3 1.3 0 0 1 10.3 4h3.4A1.3 1.3 0 0 1 15 5.3V7"/>'
        '<path d="m6.5 7 .8 11.2A1.8 1.8 0 0 0 9.1 20h5.8a1.8 1.8 0 0 0 1.8-1.8L17.5 7"/>'
        '<path d="M10 11v5M14 11v5"/>'
    ),
    "archive": (
        '<rect x="3.5" y="4" width="17" height="5" rx="1.5"/>'
        '<path d="M5 9v8.8A2.2 2.2 0 0 0 7.2 20h9.6A2.2 2.2 0 0 0 19 17.8V9"/>'
        '<path d="M10 13h4"/>'
    ),
    "check-circle": '<circle cx="12" cy="12" r="8.6"/><path d="m8.2 12.2 2.5 2.5 5.2-5.3"/>',
    "x": '<path d="M6 6l12 12M18 6 6 18"/>',
    "arrow-left": '<path d="M20 12H4M10 6l-6 6 6 6"/>',
    "arrow-right": '<path d="M4 12h16M14 6l6 6-6 6"/>',
    "chevron-right": '<path d="m9 5 7 7-7 7"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "info": '<circle cx="12" cy="12" r="8.6"/><path d="M12 11v5M12 8h.01"/>',
    "lock": (
        '<rect x="4.2" y="10.5" width="15.6" height="9.5" rx="2"/>'
        '<path d="M8 10.5V7.8a4 4 0 0 1 8 0v2.7"/>'
    ),
    "file": (
        '<path d="M6 3.8h7.2L19 9.6v10.6H6Z"/>'
        '<path d="M13 3.8V10h6M9 13h5M9 16.5h6"/>'
    ),
    "external": (
        '<path d="M14 4h6v6M20 4l-8.5 8.5"/>'
        '<path d="M18 13.5V19a1.5 1.5 0 0 1-1.5 1.5H5A1.5 1.5 0 0 1 3.5 19V7.5A1.5 1.5 0 0 1 5 6h5.5"/>'
    ),
    "refresh": '<path d="M20 11a8 8 0 1 0-2.3 6.2M20 4v7h-7"/>',
    "key": (
        '<circle cx="8" cy="15.5" r="3.5"/>'
        '<path d="m10.7 12.8 8.6-8.6M16.5 7l2 2M14.2 9.3l2 2"/>'
    ),
    "clock": '<circle cx="12" cy="12" r="8.6"/><path d="M12 7.5V12l3 2"/>',
    "hard-drive": (
        '<rect x="3" y="5" width="18" height="14" rx="2.2"/>'
        '<path d="M3 14h18M7 17h.01M11 17h.01"/>'
    ),
    "eye-off": (
        '<path d="M3 3l18 18"/>'
        '<path d="M10.6 6.3A9.7 9.7 0 0 1 12 6.2c5.4 0 9 5.8 9 5.8a16 16 0 0 1-3 3.4M6.1 7.1A16.4 16.4 0 0 0 3 12s3.6 5.8 9 5.8c1 0 2-.2 2.9-.5"/>'
        '<path d="M10.1 10.2a2.7 2.7 0 0 0 3.8 3.8"/>'
    ),
    "list": '<path d="M8 6h13M8 12h13M8 18h13"/><path d="M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>',
    "download": (
        '<path d="M12 3v12M7 10l5 5 5-5"/>'
        '<path d="M4 19.5h16"/>'
    ),
    "play": '<path d="M8 5.5v13l11-6.5Z"/>',
    "sparkle": (
        '<path d="M12 3.5 13.7 9l5.5 1.7-5.5 1.7L12 18l-1.7-5.6L4.8 10.7 10.3 9Z"/>'
        '<path d="M19 16.5v3M17.5 18h3"/>'
    ),
}


def get_pixmap(name: str, color: str = "#667085", size: int = 20) -> QPixmap:
    key = (name, color, size)
    return _pixmap_cached(*key)


@lru_cache(maxsize=256)
def _pixmap_cached(name: str, color: str, size: int) -> QPixmap:
    body = _SVG_BODIES.get(name)
    if body is None:
        body = _SVG_BODIES["file"]
    svg = _svg(body, color)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size * 2, size * 2))
    painter.end()
    pixmap.setDevicePixelRatio(2.0)
    return pixmap


def get_icon(name: str, color: str = "#667085", size: int = 20) -> QIcon:
    return QIcon(get_pixmap(name, color, size))


@lru_cache(maxsize=4)
def app_icon() -> QIcon:
    """Иконка приложения из основного SVG."""
    from PySide6.QtCore import QSize

    renderer = QSvgRenderer(str(resource_path("icon.svg")))
    if not renderer.isValid():
        return QIcon()
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        icon.addPixmap(pixmap)
    _ = QSize(0, 0)
    return icon


def logo_pixmap(size: int = 40) -> QPixmap:
    renderer = QSvgRenderer(str(resource_path("icon.svg")))
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size * 2, size * 2))
    painter.end()
    pixmap.setDevicePixelRatio(2.0)
    return pixmap
