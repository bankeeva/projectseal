"""Безопасное создание ZIP-архива по подтверждённому списку файлов.

Ключевые гарантии:
* в архив попадают только файлы категории SAFE, выбранные пользователем;
* повторно проверяются путь, симлинки и принадлежность корню проекта;
* архив пишется во временный файл, проверяется и только потом заменяет итог;
* исходные файлы не изменяются.
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable

from .errors import ExportCancelled, ExportError
from .models import ScanResult
from .paths import is_within, sanitize_arcname, source_snapshot


@dataclass(frozen=True)
class ExportOptions:
    compress_level: int = 6
    verify: bool = True
    allow_overwrite: bool = False


@dataclass(frozen=True)
class ExportProgress:
    done: int
    total: int
    current: str = ""
    message: str = ""


@dataclass
class ExportResult:
    archive_path: Path
    included_files: int = 0
    included_bytes: int = 0
    archive_size: int = 0
    excluded_secret_files: int = 0
    excluded_junk_files: int = 0
    excluded_by_user: int = 0
    skipped_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_ms: int = 0
    verified: bool = False

    @property
    def archive_name(self) -> str:
        return self.archive_path.name


ProgressCallback = Callable[[ExportProgress], None]


class ZipExporter:
    """Экспортёр ZIP. Не зависит от PySide6."""

    def __init__(self, options: ExportOptions | None = None) -> None:
        self.options = options or ExportOptions()

    def export(
        self,
        result: ScanResult,
        destination: str | Path,
        *,
        selected_paths: set[str] | None = None,
        progress: ProgressCallback | None = None,
        cancel: "object | None" = None,
    ) -> ExportResult:
        started = time.perf_counter()
        selected = selected_paths if selected_paths is not None else result.selected_safe_paths()
        safe_items = [
            item for item in result.safe if item.relative_path in selected
        ]
        if not safe_items:
            raise ExportError(
                "Нет файлов для упаковки. Выберите хотя бы один безопасный файл."
            )

        destination_path = self._validate_destination(result, destination)
        total = len(safe_items)
        excluded_by_user = max(0, len(result.safe) - len(safe_items))
        skipped: list[str] = []
        warnings: list[str] = []

        self._emit(progress, ExportProgress(done=0, total=total, message="Готовим архив…"))

        fd, temp_name = tempfile.mkstemp(
            prefix=f".{destination_path.stem}-",
            suffix=".zip.part",
            dir=str(destination_path.parent),
        )
        os.close(fd)
        temp_path = Path(temp_name)
        expected_names: list[str] = []
        source_snapshots: dict[str, tuple[int, int]] = {}
        included_bytes = 0

        try:
            with zipfile.ZipFile(
                temp_path,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=int(self.options.compress_level),
                allowZip64=True,
            ) as archive:
                for index, item in enumerate(safe_items, start=1):
                    self._check_cancel(cancel)
                    source = self._source_path(result.root, item.relative_path)
                    arcname = self._prepare_source(
                        result.root,
                        source,
                        item.relative_path,
                        warnings,
                        skipped,
                    )
                    if arcname is None:
                        self._emit(
                            progress,
                            ExportProgress(
                                done=index,
                                total=total,
                                current=item.relative_path,
                                message="Пропускаем недоступный файл…",
                            ),
                        )
                        continue
                    if arcname in expected_names:
                        skipped.append(item.relative_path)
                        warnings.append(
                            f"Повторяющееся имя в архиве пропущено: {item.relative_path}"
                        )
                        continue

                    try:
                        snapshot = source_snapshot(source)
                        if snapshot is not None:
                            source_snapshots[arcname] = snapshot
                        file_size = self._write_entry(archive, source, arcname)
                    except ExportCancelled:
                        raise
                    except (OSError, zipfile.BadZipFile) as exc:
                        skipped.append(item.relative_path)
                        warnings.append(
                            f"Не удалось добавить {item.relative_path}: "
                            f"{getattr(exc, 'strerror', None) or type(exc).__name__}"
                        )
                        self._emit(
                            progress,
                            ExportProgress(
                                done=index,
                                total=total,
                                current=item.relative_path,
                                message="Файл пропущен",
                            ),
                        )
                        continue

                    expected_names.append(arcname)
                    included_bytes += file_size
                    self._emit(
                        progress,
                        ExportProgress(
                            done=index,
                            total=total,
                            current=item.relative_path,
                            message="Упаковываем файлы…",
                        ),
                    )

            if not expected_names:
                raise ExportError(
                    "Не удалось добавить ни одного файла. Проверьте права доступа к папке."
                )

            if self.options.verify:
                self._verify_archive(temp_path, expected_names)

            self._check_cancel(cancel)
            if destination_path.exists() and not self.options.allow_overwrite:
                raise ExportError(
                    f"Файл уже существует: {destination_path.name}. "
                    "Выберите другое имя или разрешите перезапись."
                )
            try:
                os.replace(temp_path, destination_path)
            except PermissionError as exc:
                raise ExportError(
                    f"Не удалось сохранить архив «{destination_path.name}». "
                    "Возможно, файл открыт в другой программе."
                ) from exc
            except OSError as exc:
                raise ExportError(
                    f"Не удалось сохранить архив: {exc.strerror or exc}"
                ) from exc

            self._check_sources_unchanged(source_snapshots, result.root, warnings)
            archive_size = destination_path.stat().st_size
            self._emit(
                progress,
                ExportProgress(
                    done=total,
                    total=total,
                    message="Архив готов",
                ),
            )
            return ExportResult(
                archive_path=destination_path,
                included_files=len(expected_names),
                included_bytes=included_bytes,
                archive_size=archive_size,
                excluded_secret_files=result.summary.secrets_found,
                excluded_junk_files=result.summary.junk_found,
                excluded_by_user=excluded_by_user,
                skipped_files=skipped,
                warnings=warnings,
                duration_ms=int((time.perf_counter() - started) * 1000),
                verified=bool(self.options.verify),
            )
        except ExportCancelled:
            self._safe_unlink(temp_path)
            raise
        except ExportError:
            self._safe_unlink(temp_path)
            raise
        except Exception as exc:  # noqa: BLE001 — не оставляем частичный архив
            self._safe_unlink(temp_path)
            raise ExportError(f"Не удалось создать архив: {exc}") from exc

    # ------------------------------------------------------------------
    # Проверки
    # ------------------------------------------------------------------
    def _validate_destination(self, result: ScanResult, destination: str | Path) -> Path:
        destination_path = Path(destination).expanduser()
        if destination_path.suffix.lower() != ".zip":
            if destination_path.suffix:
                destination_path = destination_path.with_suffix(".zip")
            else:
                destination_path = destination_path.with_name(destination_path.name + ".zip")
        destination_path = destination_path.absolute()
        if destination_path.exists() and destination_path.is_dir():
            raise ExportError("Выбранный путь является папкой. Укажите имя ZIP-файла.")
        if is_within(destination_path, result.root):
            raise ExportError(
                "Нельзя сохранять архив внутри проверяемой папки: "
                "исходная папка должна остаться неизменной. Выберите папку рядом."
            )
        parent = destination_path.parent
        if not parent.exists() or not parent.is_dir():
            raise ExportError("Папка для сохранения архива не найдена.")
        if not os.access(parent, os.W_OK):
            raise ExportError("Нет прав на запись в выбранную папку.")
        if destination_path.exists() and not self.options.allow_overwrite:
            raise ExportError(
                f"Файл уже существует: {destination_path.name}. "
                "Выберите другое имя или разрешите перезапись."
            )
        return destination_path

    @staticmethod
    def _source_path(root: Path, relative: str) -> Path:
        pure = PurePosixPath(relative.replace("\\", "/"))
        return root.joinpath(*pure.parts)

    def _prepare_source(
        self,
        root: Path,
        source: Path,
        relative: str,
        warnings: list[str],
        skipped: list[str],
    ) -> str | None:
        arcname = sanitize_arcname(relative)
        if arcname is None:
            skipped.append(relative)
            warnings.append(f"Небезопасный путь пропущен: {relative}")
            return None
        try:
            if source.is_symlink():
                skipped.append(relative)
                warnings.append(f"Символическая ссылка пропущена: {relative}")
                return None
            if not is_within(source, root):
                skipped.append(relative)
                warnings.append(f"Файл вне папки проекта пропущен: {relative}")
                return None
            stat_result = os.stat(source, follow_symlinks=False)
            if not stat.S_ISREG(stat_result.st_mode):
                skipped.append(relative)
                warnings.append(f"Не обычный файл, пропущен: {relative}")
                return None
            if not os.access(source, os.R_OK):
                skipped.append(relative)
                warnings.append(f"Нет доступа к файлу, пропущен: {relative}")
                return None
        except OSError as exc:
            skipped.append(relative)
            warnings.append(
                f"Не удалось проверить {relative}: "
                f"{getattr(exc, 'strerror', None) or type(exc).__name__}"
            )
            return None
        return arcname

    # ------------------------------------------------------------------
    # Запись и проверка ZIP
    # ------------------------------------------------------------------
    def _write_entry(self, archive: zipfile.ZipFile, source: Path, arcname: str) -> int:
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        fd = os.open(source, flags)
        with os.fdopen(fd, "rb", closefd=True) as source_handle:
            with archive.open(arcname, "w") as target_handle:
                shutil.copyfileobj(source_handle, target_handle, length=256 * 1024)
            try:
                size = os.fstat(source_handle.fileno()).st_size
            except OSError:
                size = 0
        return max(0, size)

    def _verify_archive(self, archive_path: Path, expected_names: list[str]) -> None:
        if not zipfile.is_zipfile(archive_path):
            raise ExportError("Созданный файл не является корректным ZIP-архивом.")
        try:
            with zipfile.ZipFile(archive_path, mode="r") as archive:
                names = archive.namelist()
                if len(names) != len(expected_names) or set(names) != set(expected_names):
                    raise ExportError(
                        "Проверка архива не пройдена: состав файлов не совпадает с ожидаемым."
                    )
                for name in names:
                    if sanitize_arcname(name) != name:
                        raise ExportError(
                            f"Проверка архива не пройдена: небезопасный путь {name}."
                        )
                bad_member = archive.testzip()
                if bad_member is not None:
                    raise ExportError(
                        f"Проверка архива не пройдена: повреждён файл {bad_member}."
                    )
        except zipfile.BadZipFile as exc:
            raise ExportError("Созданный архив повреждён и не может быть открыт.") from exc

    def _check_sources_unchanged(
        self,
        snapshots: dict[str, tuple[int, int]],
        root: Path,
        warnings: list[str],
    ) -> None:
        for arcname, before in snapshots.items():
            source = root.joinpath(*PurePosixPath(arcname).parts)
            after = source_snapshot(source)
            if after is None:
                warnings.append(f"Файл исчез во время упаковки: {arcname}")
            elif after != before:
                warnings.append(f"Файл изменился во время упаковки: {arcname}")

    @staticmethod
    def _check_cancel(cancel: object | None) -> None:
        if cancel is not None and getattr(cancel, "is_set", lambda: False)():
            raise ExportCancelled("Упаковка отменена.")

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass

    @staticmethod
    def _emit(callback: ProgressCallback | None, progress: ExportProgress) -> None:
        if callback is None:
            return
        try:
            callback(progress)
        except Exception:  # noqa: BLE001
            return
