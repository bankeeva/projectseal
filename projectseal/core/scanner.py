"""Движок локальной проверки папки.

Сканер работает в обычном Python-потоке (UI запускает его в QThread):
* обходит дерево, не переходя по символическим ссылкам;
* сразу исключает типовые папки-мусор, не читая их содержимое;
* проверяет текстовые файлы regex-правилами с ограничением размера;
* возвращает неизменяемый снимок результата в памяти.
"""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .models import Category, FileItem, ScanError, ScanResult, ScanSummary
from .paths import decode_text, human_size, looks_binary, read_limited
from .rules import FileRule, RuleSet, load_rules


class ScanInputError(ValueError):
    """Проблема с выбранной папкой: не найдена, нет прав, это файл."""


@dataclass(frozen=True)
class ScanOptions:
    max_files: int = 5000
    max_total_bytes: int = 500 * 1024 * 1024
    max_text_bytes: int = 5 * 1024 * 1024
    max_depth: int = 48
    max_workers: int = field(default_factory=lambda: min(8, max(2, (os.cpu_count() or 4))))
    junk_count_cap: int = 20000


@dataclass(frozen=True)
class ScanProgress:
    phase: str  # walk | analyze | done
    done: int = 0
    total: int = 0
    current: str = ""
    found: int = 0
    message: str = ""


@dataclass(frozen=True)
class FileCandidate:
    relative_path: str
    path: Path
    size: int
    rule: FileRule | None = None


@dataclass
class ClassifyOutcome:
    item: FileItem
    errors: list[ScanError] = field(default_factory=list)
    binary: bool = False
    large: bool = False
    unverified: bool = False


ProgressCallback = Callable[[ScanProgress], None]


class Scanner:
    """Проверка одной папки. Экземпляр можно переиспользовать."""

    def __init__(self, rules: RuleSet | None = None, options: ScanOptions | None = None) -> None:
        self.rules = rules or load_rules()
        self.options = options or ScanOptions()

    # ------------------------------------------------------------------
    # Публичный API
    # ------------------------------------------------------------------
    def scan(
        self,
        root: str | Path,
        *,
        progress: ProgressCallback | None = None,
        cancel: threading.Event | None = None,
    ) -> ScanResult:
        started = time.perf_counter()
        cancel = cancel or threading.Event()
        root_abs = self._validate_root(root)

        items: list[FileItem] = []
        candidates: list[FileCandidate] = []
        errors: list[ScanError] = []
        limits_hit: list[str] = []

        self._emit(progress, ScanProgress(phase="walk", message="Ищем файлы в папке…"))

        walk_result = self._walk(
            root_abs,
            progress=progress,
            cancel=cancel,
            errors=errors,
            limits_hit=limits_hit,
        )
        items.extend(walk_result.junk_items)
        candidates.extend(walk_result.candidates)
        discovered = walk_result.discovered
        scanned_bytes = walk_result.scanned_bytes
        dirs_scanned = walk_result.dirs_scanned

        if cancel.is_set():
            summary = self._build_summary(
                items,
                errors,
                limits_hit,
                started,
                binary_files=0,
                large_files=0,
                unverified_files=0,
                dirs_scanned=dirs_scanned,
            )
            return ScanResult(
                root=root_abs,
                items=self._sorted_items(items),
                errors=errors,
                summary=summary,
                cancelled=True,
            )

        analyzed, analyze_errors, counters = self._analyze(
            candidates, progress=progress, cancel=cancel
        )
        errors.extend(analyze_errors)
        items.extend(analyzed)

        if cancel.is_set():
            summary = self._build_summary(
                items,
                errors,
                limits_hit,
                started,
                dirs_scanned=dirs_scanned,
                **counters,
            )
            return ScanResult(
                root=root_abs,
                items=self._sorted_items(items),
                errors=errors,
                summary=summary,
                cancelled=True,
            )

        summary = self._build_summary(
            items, errors, limits_hit, started, dirs_scanned=dirs_scanned, **counters
        )
        self._emit(
            progress,
            ScanProgress(
                phase="done",
                done=len(candidates),
                total=len(candidates),
                found=summary.total_files,
                message="Проверка завершена",
            ),
        )

        # discovered/scanned_bytes/dirs_scanned используются в отладочных
        # сообщениях и оставлены в локальных переменных; сводка считается
        # по фактическим элементам, чтобы не зависеть от лимитов.
        _ = (discovered, scanned_bytes, dirs_scanned)
        return ScanResult(
            root=root_abs,
            items=self._sorted_items(items),
            errors=errors,
            summary=summary,
            cancelled=False,
        )

    # ------------------------------------------------------------------
    # Валидация и обход
    # ------------------------------------------------------------------
    def _validate_root(self, root: str | Path) -> Path:
        path = Path(root).expanduser()
        try:
            if not path.exists():
                raise ScanInputError("Папка не найдена. Выберите существующую папку проекта.")
            if not path.is_dir():
                raise ScanInputError("Это не папка. Выберите папку с проектом.")
            resolved = path.resolve(strict=True)
        except ScanInputError:
            raise
        except OSError as exc:
            raise ScanInputError(f"Не удалось открыть папку: {exc.strerror or exc}") from exc

        try:
            with os.scandir(resolved) as iterator:
                next(iterator, None)
        except PermissionError as exc:
            raise ScanInputError(
                "Нет доступа к выбранной папке. Проверьте права или выберите другую папку."
            ) from exc
        except OSError as exc:
            raise ScanInputError(f"Не удалось прочитать папку: {exc.strerror or exc}") from exc
        return resolved

    def _walk(
        self,
        root: Path,
        *,
        progress: ProgressCallback | None,
        cancel: threading.Event,
        errors: list[ScanError],
        limits_hit: list[str],
    ) -> "_WalkResult":
        junk_items: list[FileItem] = []
        candidates: list[FileCandidate] = []
        stack: list[tuple[Path, str, int]] = [(root, "", 0)]
        discovered = 0
        scanned_bytes = 0
        dirs_scanned = 0
        entries_seen = 0
        stop = False

        while stack and not stop:
            if cancel.is_set():
                break
            directory, rel_dir, depth = stack.pop()
            try:
                entries = list(os.scandir(directory))
            except PermissionError:
                errors.append(
                    ScanError(
                        rel_dir or ".",
                        "Нет доступа к папке — её содержимое не проверялось.",
                        "permission",
                    )
                )
                continue
            except OSError as exc:
                errors.append(
                    ScanError(
                        rel_dir or ".",
                        f"Не удалось прочитать папку: {exc.strerror or exc}",
                        "read",
                    )
                )
                continue

            entries.sort(key=lambda entry: entry.name.lower())
            dirs_scanned += 1

            for entry in entries:
                if cancel.is_set():
                    break
                entries_seen += 1
                relative = f"{rel_dir}/{entry.name}" if rel_dir else entry.name
                try:
                    if entry.is_symlink():
                        junk_items.append(
                            FileItem(
                                relative_path=relative,
                                category=Category.JUNK,
                                reason="Символическая ссылка: переход не выполняется, файл не включается.",
                                file_size=0,
                                rule_id="symlink",
                                severity="info",
                            )
                        )
                        continue

                    if entry.is_dir(follow_symlinks=False):
                        rule = self.rules.junk_dir_rule(entry.name)
                        if rule is not None:
                            child_count, child_size, capped = self._count_children(
                                Path(entry.path),
                                cap=self.options.junk_count_cap,
                                cancel=cancel,
                            )
                            reason = rule.reason
                            if capped:
                                reason += f" В папке не менее {child_count:,} файлов.".replace(",", " ")
                            junk_items.append(
                                FileItem(
                                    relative_path=relative,
                                    category=Category.JUNK,
                                    reason=reason,
                                    file_size=child_size,
                                    is_dir=True,
                                    child_count=child_count,
                                    count_capped=capped,
                                    rule_id=rule.id,
                                    severity="info",
                                )
                            )
                            continue

                        if depth >= self.options.max_depth:
                            errors.append(
                                ScanError(
                                    relative,
                                    "Слишком глубокая вложенность — папка пропущена.",
                                    "limit",
                                )
                            )
                            continue
                        stack.append((Path(entry.path), relative, depth + 1))
                        continue

                    if entry.is_file(follow_symlinks=False):
                        stat = entry.stat(follow_symlinks=False)
                        if discovered >= self.options.max_files:
                            limits_hit.append(
                                f"Достигнут лимит {self.options.max_files:,} файлов. "
                                "Проверены первые файлы, остальные не анализировались.".replace(",", " ")
                            )
                            stop = True
                            break
                        if scanned_bytes + stat.st_size > self.options.max_total_bytes:
                            limits_hit.append(
                                "Достигнут лимит объёма "
                                f"{human_size(self.options.max_total_bytes)}. "
                                "Сканирование остановлено."
                            )
                            stop = True
                            break
                        discovered += 1
                        scanned_bytes += max(0, stat.st_size)
                        candidates.append(
                            FileCandidate(
                                relative_path=relative,
                                path=Path(entry.path),
                                size=max(0, stat.st_size),
                                rule=self.rules.classify_filename(entry.name),
                            )
                        )
                        continue

                    # Сокеты, FIFO и другие специальные файлы не читаем.
                    junk_items.append(
                        FileItem(
                            relative_path=relative,
                            category=Category.JUNK,
                            reason="Специальный файл: не является обычным файлом и не включается.",
                            file_size=0,
                            rule_id="special-file",
                            severity="info",
                        )
                    )
                except OSError as exc:
                    errors.append(
                        ScanError(
                            relative,
                            f"Не удалось получить информацию о файле: {exc.strerror or exc}",
                            "read",
                        )
                    )

            if entries_seen % 150 == 0 or entries_seen < 150:
                self._emit(
                    progress,
                    ScanProgress(
                        phase="walk",
                        done=discovered,
                        total=0,
                        current=rel_dir or ".",
                        found=discovered + len(junk_items),
                        message="Ищем файлы в папке…",
                    ),
                )

        return _WalkResult(
            junk_items=junk_items,
            candidates=candidates,
            discovered=discovered,
            scanned_bytes=scanned_bytes,
            dirs_scanned=dirs_scanned,
        )

    def _count_children(
        self, path: Path, *, cap: int, cancel: threading.Event
    ) -> tuple[int, int, bool]:
        """Посчитать содержимое исключённой папки без чтения файлов."""
        count = 0
        size = 0
        stack = [path]
        while stack and count <= cap:
            if cancel.is_set():
                break
            current = stack.pop()
            try:
                iterator = os.scandir(current)
            except OSError:
                continue
            try:
                with iterator:
                    for entry in iterator:
                        if cancel.is_set():
                            break
                        try:
                            if entry.is_symlink():
                                count += 1
                            elif entry.is_dir(follow_symlinks=False):
                                stack.append(Path(entry.path))
                            elif entry.is_file(follow_symlinks=False):
                                count += 1
                                try:
                                    size += max(0, entry.stat(follow_symlinks=False).st_size)
                                except OSError:
                                    pass
                            else:
                                count += 1
                        except OSError:
                            count += 1
                        if count > cap:
                            return cap, size, True
            except OSError:
                continue
        return min(count, cap), size, count > cap

    # ------------------------------------------------------------------
    # Анализ содержимого
    # ------------------------------------------------------------------
    def _analyze(
        self,
        candidates: list[FileCandidate],
        *,
        progress: ProgressCallback | None,
        cancel: threading.Event,
    ) -> tuple[list[FileItem], list[ScanError], dict[str, int]]:
        analyzed: list[FileItem] = []
        errors: list[ScanError] = []
        counters = {"binary_files": 0, "large_files": 0, "unverified_files": 0}
        total = len(candidates)
        if total == 0:
            return analyzed, errors, counters

        workers = max(1, min(self.options.max_workers, total))
        executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="seal-scan")
        futures = {executor.submit(self._classify, candidate): candidate for candidate in candidates}
        last_emit = 0.0
        try:
            for done, future in enumerate(as_completed(futures), start=1):
                if cancel.is_set():
                    break
                candidate = futures[future]
                try:
                    outcome = future.result()
                except Exception as exc:  # noqa: BLE001 — изолируем сбой одного файла
                    outcome = ClassifyOutcome(
                        item=FileItem(
                            relative_path=candidate.relative_path,
                            category=Category.SECRET,
                            reason="Внутренняя ошибка проверки — файл исключён из архива.",
                            file_size=candidate.size,
                            rule_id="internal-error",
                            severity="unknown",
                        ),
                        errors=[
                            ScanError(
                                candidate.relative_path,
                                f"Внутренняя ошибка проверки: {type(exc).__name__}.",
                                "other",
                            )
                        ],
                        unverified=True,
                    )

                analyzed.append(outcome.item)
                errors.extend(outcome.errors)
                if outcome.binary:
                    counters["binary_files"] += 1
                if outcome.large:
                    counters["large_files"] += 1
                if outcome.unverified:
                    counters["unverified_files"] += 1

                now = time.monotonic()
                if done == total or done % 5 == 0 or now - last_emit > 0.08:
                    last_emit = now
                    self._emit(
                        progress,
                        ScanProgress(
                            phase="analyze",
                            done=done,
                            total=total,
                            current=candidate.relative_path,
                            found=done,
                            message="Проверяем содержимое файлов…",
                        ),
                    )
        finally:
            if cancel.is_set():
                executor.shutdown(wait=False, cancel_futures=True)
            else:
                executor.shutdown(wait=True)

        return analyzed, errors, counters

    def _classify(self, candidate: FileCandidate) -> ClassifyOutcome:
        rule = candidate.rule
        if rule is not None and rule.kind == "junk":
            return ClassifyOutcome(
                item=FileItem(
                    relative_path=candidate.relative_path,
                    category=Category.JUNK,
                    reason=rule.reason,
                    file_size=candidate.size,
                    rule_id=rule.id,
                    severity="info",
                )
            )

        if rule is not None and rule.kind == "secret":
            return self._classify_secret_name(candidate, rule)

        return self._classify_content(candidate)

    def _classify_secret_name(
        self, candidate: FileCandidate, rule: FileRule
    ) -> ClassifyOutcome:
        if candidate.size > self.options.max_text_bytes:
            return ClassifyOutcome(
                item=FileItem(
                    relative_path=candidate.relative_path,
                    category=Category.SECRET,
                    reason=rule.reason + " Файл больше 5 МБ: содержимое не проверялось.",
                    file_size=candidate.size,
                    preview="Содержимое скрыто: файл больше 5 МБ.",
                    rule_id=rule.id,
                    severity=rule.severity,
                ),
                errors=[
                    ScanError(
                        candidate.relative_path,
                        "Файл с потенциальными секретами больше 5 МБ: "
                        "содержимое не проверялось, файл исключён.",
                        "skipped",
                    )
                ],
                large=True,
            )

        data, error = self._read(candidate)
        if error is not None:
            return ClassifyOutcome(
                item=FileItem(
                    relative_path=candidate.relative_path,
                    category=Category.SECRET,
                    reason="Не удалось прочитать файл — он исключён из архива, содержимое не проверено.",
                    file_size=candidate.size,
                    preview="Содержимое недоступно.",
                    rule_id=rule.id,
                    severity="unknown",
                ),
                errors=[error],
                unverified=True,
            )

        if looks_binary(data):
            return ClassifyOutcome(
                item=FileItem(
                    relative_path=candidate.relative_path,
                    category=Category.SECRET,
                    reason=rule.reason,
                    file_size=candidate.size,
                    preview="Бинарное хранилище: содержимое скрыто.",
                    rule_id=rule.id,
                    severity=rule.severity,
                ),
                binary=True,
            )

        match = self.rules.find_secret(decode_text(data))
        preview = match.preview if match else "Файл с потенциальными секретами (содержимое скрыто)."
        return ClassifyOutcome(
            item=FileItem(
                relative_path=candidate.relative_path,
                category=Category.SECRET,
                reason=rule.reason,
                file_size=candidate.size,
                preview=preview,
                rule_id=rule.id,
                severity=rule.severity,
            )
        )

    def _classify_content(self, candidate: FileCandidate) -> ClassifyOutcome:
        if candidate.size > self.options.max_text_bytes:
            return ClassifyOutcome(
                item=FileItem(
                    relative_path=candidate.relative_path,
                    category=Category.SAFE,
                    reason=(
                        "Файл больше 5 МБ: содержимое не проверялось, "
                        "файл включён в архив."
                    ),
                    file_size=candidate.size,
                    rule_id="large-file",
                ),
                errors=[
                    ScanError(
                        candidate.relative_path,
                        "Файл больше 5 МБ: содержимое не проверялось, но файл включён в архив.",
                        "skipped",
                    )
                ],
                large=True,
            )

        data, error = self._read(candidate)
        if error is not None:
            return ClassifyOutcome(
                item=FileItem(
                    relative_path=candidate.relative_path,
                    category=Category.SECRET,
                    reason="Не удалось прочитать файл — он исключён из архива, содержимое не проверено.",
                    file_size=candidate.size,
                    preview="Содержимое недоступно.",
                    rule_id="unreadable",
                    severity="unknown",
                ),
                errors=[error],
                unverified=True,
            )

        if not data:
            return ClassifyOutcome(
                item=FileItem(
                    relative_path=candidate.relative_path,
                    category=Category.SAFE,
                    reason="Пустой файл.",
                    file_size=candidate.size,
                    rule_id="empty",
                )
            )

        if looks_binary(data):
            return ClassifyOutcome(
                item=FileItem(
                    relative_path=candidate.relative_path,
                    category=Category.SAFE,
                    reason="Бинарный файл: содержимое не проверяется.",
                    file_size=candidate.size,
                    rule_id="binary",
                ),
                binary=True,
            )

        match = self.rules.find_secret(decode_text(data))
        if match is not None:
            return ClassifyOutcome(
                item=FileItem(
                    relative_path=candidate.relative_path,
                    category=Category.SECRET,
                    reason=f"Найден шаблон: {match.title} ({match.location}).",
                    file_size=candidate.size,
                    preview=match.preview,
                    rule_id=match.rule_id,
                    severity=match.severity,
                )
            )

        return ClassifyOutcome(
            item=FileItem(
                relative_path=candidate.relative_path,
                category=Category.SAFE,
                reason="Проверено: секретов не найдено.",
                file_size=candidate.size,
                rule_id="checked",
            )
        )

    def _read(self, candidate: FileCandidate) -> tuple[bytes, ScanError | None]:
        try:
            data, _truncated = read_limited(candidate.path, self.options.max_text_bytes)
            return data, None
        except PermissionError:
            return b"", ScanError(
                candidate.relative_path,
                "Нет доступа к файлу — он исключён из архива.",
                "permission",
            )
        except OSError as exc:
            return b"", ScanError(
                candidate.relative_path,
                f"Не удалось прочитать файл: {exc.strerror or type(exc).__name__}. "
                "Файл исключён из архива.",
                "read",
            )

    # ------------------------------------------------------------------
    # Сводка
    # ------------------------------------------------------------------
    def _build_summary(
        self,
        items: list[FileItem],
        errors: list[ScanError],
        limits_hit: list[str],
        started: float,
        *,
        binary_files: int = 0,
        large_files: int = 0,
        unverified_files: int = 0,
        dirs_scanned: int = 0,
    ) -> ScanSummary:
        safe = [item for item in items if item.category is Category.SAFE]
        secret = [item for item in items if item.category is Category.SECRET]
        junk = [item for item in items if item.category is Category.JUNK]

        junk_files = sum(item.files_count for item in junk)
        total_files = len(safe) + len(secret) + junk_files
        total_bytes = sum(item.file_size for item in items)
        safe_bytes = sum(item.file_size for item in safe)
        selected = [item for item in safe if item.selected]
        return ScanSummary(
            total_files=total_files,
            secrets_found=len(secret),
            junk_found=junk_files,
            safe_to_pack=len(safe),
            safe_selected=len(selected),
            total_bytes=total_bytes,
            safe_bytes=safe_bytes,
            safe_selected_bytes=sum(item.file_size for item in selected),
            junk_objects=len(junk),
            dirs_scanned=dirs_scanned,
            errors_count=len(errors),
            unverified_count=unverified_files or sum(
                1 for item in secret if item.severity == "unknown"
            ),
            binary_files=binary_files,
            large_files=large_files,
            duration_ms=int((time.perf_counter() - started) * 1000),
            limits_hit=list(limits_hit),
            junk_count_estimated=any(item.count_capped for item in junk),
            total_files_estimated=any(item.count_capped for item in junk)
            or bool(limits_hit),
        )

    @staticmethod
    def _sorted_items(items: list[FileItem]) -> list[FileItem]:
        category_order = {Category.SECRET: 0, Category.JUNK: 1, Category.SAFE: 2}
        return sorted(
            items,
            key=lambda item: (
                category_order[item.category],
                item.sort_key(),
                item.relative_path.lower(),
            ),
        )

    @staticmethod
    def _emit(callback: ProgressCallback | None, progress: ScanProgress) -> None:
        if callback is None:
            return
        try:
            callback(progress)
        except Exception:  # noqa: BLE001 — прогресс не должен ломать проверку
            return


@dataclass
class _WalkResult:
    junk_items: list[FileItem]
    candidates: list[FileCandidate]
    discovered: int
    scanned_bytes: int
    dirs_scanned: int
