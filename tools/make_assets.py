"""Сгенерировать PNG-ресурсы из SVG (иконка приложения и галочка)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "projectseal" / "resources"


def render(svg_name: str, png_name: str, size: int, *, background: bool = False) -> None:
    renderer = QSvgRenderer(str(RES / svg_name))
    if not renderer.isValid():
        raise SystemExit(f"Не удалось открыть {svg_name}")
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    image.save(str(RES / png_name))
    print("saved", RES / png_name, size)


def main() -> None:
    app = QApplication(sys.argv)  # noqa: F841 — нужен для QImage/шрифтов
    render("icon.svg", "icon_1024.png", 1024)
    render("icon.svg", "icon_512.png", 512)
    render("check.svg", "check.png", 36)
    _ = app


if __name__ == "__main__":
    main()
