"""Фоновые задачи: проверка папки и упаковка ZIP.

Тяжёлые операции выполняются в QThread, поэтому главный поток Qt остаётся
отзывчивым. Сигналы доставляются в UI-поток через queued connection.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from ..core.errors import ExportCancelled, ExportError
from ..core.exporter import ExportOptions, ExportProgress, ZipExporter
from ..core.scanner import ScanInputError, ScanOptions, ScanProgress, Scanner


class ScanWorker(QObject):
    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str, str, str)
    cancelled = Signal()

    def __init__(
        self,
        root: Path,
        options: ScanOptions | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._root = root
        self._options = options or ScanOptions()
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    @Slot()
    def run(self) -> None:
        try:
            scanner = Scanner(options=self._options)
            result = scanner.scan(
                self._root,
                progress=self._emit_progress,
                cancel=self._cancel,
            )
        except ScanInputError as exc:
            self.failed.emit("Не удалось проверить папку", str(exc), "input")
        except Exception:  # noqa: BLE001 — пользователь не должен видеть traceback
            logging.exception("Scan failed for %s", self._root)
            self.failed.emit(
                "Не удалось проверить папку",
                "Произошла непредвиденная ошибка. Подробности сохранены в журнале. "
                "Попробуйте выбрать папку ещё раз.",
                "unexpected",
            )
        else:
            if result.cancelled:
                self.cancelled.emit()
            else:
                self.finished.emit(result)

    def _emit_progress(self, progress: ScanProgress) -> None:
        self.progress.emit(progress)


class ExportWorker(QObject):
    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str, str, str)
    cancelled = Signal()

    def __init__(
        self,
        result,
        destination: Path,
        selected_paths: set[str],
        *,
        allow_overwrite: bool = False,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._result = result
        self._destination = destination
        self._selected_paths = set(selected_paths)
        self._allow_overwrite = allow_overwrite
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    @Slot()
    def run(self) -> None:
        try:
            exporter = ZipExporter(
                ExportOptions(allow_overwrite=self._allow_overwrite, verify=True)
            )
            result = exporter.export(
                self._result,
                self._destination,
                selected_paths=self._selected_paths,
                progress=self._emit_progress,
                cancel=self._cancel,
            )
        except ExportCancelled:
            self.cancelled.emit()
        except ExportError as exc:
            self.failed.emit("Не удалось создать архив", str(exc), "export")
        except Exception:  # noqa: BLE001
            logging.exception("Export failed for %s", self._destination)
            self.failed.emit(
                "Не удалось создать архив",
                "Произошла непредвиденная ошибка. Подробности сохранены в журнале. "
                "Проверьте свободное место и права на папку.",
                "unexpected",
            )
        else:
            self.finished.emit(result)

    def _emit_progress(self, progress: ExportProgress) -> None:
        self.progress.emit(progress)
