"""Правила сканирования: имена файлов, папки-мусор и regex-шаблоны секретов.

Все правила вынесены в ``projectseal/resources/rules.json``. Файл можно
исправить без изменения кода; путь можно переопределить переменной окружения
``PROJECTSEAL_RULES``.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Iterable

from .masking import (
    clean_value,
    format_assignment_preview,
    format_typed_preview,
    mask_secret,
)


class RuleConfigError(RuntimeError):
    """Некорректная конфигурация правил."""


@dataclass(frozen=True)
class FileRule:
    """Правило для имени файла или папки."""

    id: str
    kind: str  # secret | junk | junk_dir
    title: str
    reason: str
    severity: str = "info"
    pattern: str = ""


@dataclass(frozen=True)
class SecretPattern:
    """Скомпилированный шаблон содержимого."""

    id: str
    title: str
    severity: str
    regex: re.Pattern[str]
    value_group: int = 0
    kind: str = "typed"  # typed | assignment | database | block

    def finditer(self, text: str) -> Iterable[re.Match[str]]:
        return self.regex.finditer(text)


@dataclass(frozen=True)
class SecretMatch:
    """Найденный секрет. Полное значение намеренно не хранится."""

    rule_id: str
    title: str
    severity: str
    preview: str
    line_number: int

    @property
    def location(self) -> str:
        return f"строка {self.line_number}"


@dataclass
class RuleSet:
    """Набор правил, готовый к применению."""

    version: str = "1.0"
    junk_dirs: dict[str, FileRule] = field(default_factory=dict)
    junk_file_names: dict[str, FileRule] = field(default_factory=dict)
    junk_file_globs: list[FileRule] = field(default_factory=list)
    secret_file_names: dict[str, FileRule] = field(default_factory=dict)
    secret_file_globs: list[FileRule] = field(default_factory=list)
    ignore_globs: tuple[str, ...] = ()
    content_patterns: tuple[SecretPattern, ...] = ()
    placeholders: tuple[str, ...] = ()

    # ------------------------------------------------------------------
    # Классификация имён
    # ------------------------------------------------------------------
    def is_ignored_name(self, name: str) -> bool:
        lowered = name.lower()
        return any(fnmatch.fnmatchcase(lowered, pattern.lower()) for pattern in self.ignore_globs)

    def junk_dir_rule(self, name: str) -> FileRule | None:
        return self.junk_dirs.get(name.lower())

    def classify_filename(self, name: str) -> FileRule | None:
        """Правило для файла по имени. Секреты приоритетнее мусора."""
        lowered = name.lower()
        if self.is_ignored_name(name):
            return None

        exact_secret = self.secret_file_names.get(lowered)
        if exact_secret:
            return exact_secret

        for rule in self.secret_file_globs:
            if fnmatch.fnmatchcase(lowered, rule.pattern.lower()):
                return rule

        exact_junk = self.junk_file_names.get(lowered)
        if exact_junk:
            return exact_junk

        for rule in self.junk_file_globs:
            if fnmatch.fnmatchcase(lowered, rule.pattern.lower()):
                return rule
        return None

    def is_secret_filename(self, name: str) -> bool:
        rule = self.classify_filename(name)
        return bool(rule and rule.kind == "secret")

    # ------------------------------------------------------------------
    # Поиск секретов в тексте
    # ------------------------------------------------------------------
    def is_placeholder(self, value: str) -> bool:
        """Отсечь заведомо учебные значения и ссылки на переменные."""
        cleaned = clean_value(value)
        if not cleaned:
            return True
        if len(cleaned) < 8:
            return True

        lowered = cleaned.lower()
        for marker in self.placeholders:
            if marker and marker in lowered:
                return True

        if any(ch in cleaned for ch in "()[]{}<>"):
            return True
        if cleaned.startswith(("/", "\\", "http://", "https://", "ftp://")):
            return True
        if cleaned in {"password", "passwd", "pwd", "token", "secret", "api_key", "apikey"}:
            return True
        if re.fullmatch(r"[.\-_*•]+", cleaned):
            return True
        if len(set(cleaned)) <= 2:
            return True
        return False

    def find_secret(self, text: str) -> SecretMatch | None:
        """Найти первый подтверждённый шаблон. Полное значение не возвращается."""
        if not text:
            return None
        # Ограничиваем количество проверок на один шаблон, чтобы патология
        # вроде длинной строки из одинаковых символов не тормозила UI.
        for pattern in self.content_patterns:
            checked = 0
            for match in pattern.finditer(text):
                checked += 1
                if checked > 100:
                    break
                try:
                    value = match.group(pattern.value_group)
                except IndexError:
                    continue
                if value is None or self.is_placeholder(value):
                    continue

                preview = self._build_preview(pattern, match, value)
                line_number = text.count("\n", 0, match.start()) + 1
                return SecretMatch(
                    rule_id=pattern.id,
                    title=pattern.title,
                    severity=pattern.severity,
                    preview=preview,
                    line_number=line_number,
                )
        return None

    def _build_preview(self, pattern: SecretPattern, match: re.Match[str], value: str) -> str:
        if pattern.kind == "block" or pattern.id == "private_key_block":
            return "Блок приватного ключа: ••••••••"
        if pattern.kind == "database":
            return "Пароль в строке подключения: " + mask_secret(value)
        if pattern.kind == "assignment":
            assignment = match.group(0)
            key = re.split(r"[:=]", assignment, maxsplit=1)[0]
            return format_assignment_preview(key, value)
        return format_typed_preview(pattern.title, value)


# ----------------------------------------------------------------------
# Загрузка конфигурации
# ----------------------------------------------------------------------
def default_rules_path() -> Path:
    override = os.environ.get("PROJECTSEAL_RULES")
    if override:
        return Path(override).expanduser()
    # В frozen-сборке importlib.resources может не видеть data-пакет,
    # поэтому сначала используем общий runtime-поиск ресурсов.
    try:
        from ..runtime import resource_path

        candidate = resource_path("rules.json")
        if candidate.exists():
            return candidate
    except Exception:  # noqa: BLE001 — fallback ниже обязателен
        pass
    resource = files("projectseal.resources").joinpath("rules.json")
    try:
        return Path(str(resource))
    except (TypeError, ValueError):
        return Path(__file__).resolve().parents[1] / "resources" / "rules.json"


def load_rules(path: str | Path | None = None) -> RuleSet:
    rules_path = Path(path) if path else default_rules_path()
    try:
        raw = json.loads(rules_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuleConfigError(f"Не найден файл правил: {rules_path}") from exc
    except json.JSONDecodeError as exc:
        raise RuleConfigError(f"Ошибка JSON в правилах {rules_path}: {exc}") from exc

    version = str(raw.get("version", "1.0"))
    junk = raw.get("junk", {})
    secret = raw.get("secret", {})

    rules = RuleSet(
        version=version,
        ignore_globs=tuple(secret.get("ignore_globs", [])),
        placeholders=tuple(raw.get("placeholders", [])),
    )

    for name, data in junk.get("directories", {}).items():
        rules.junk_dirs[name.lower()] = FileRule(
            id=f"junk-dir:{name}",
            kind="junk_dir",
            title=str(data.get("title") or name),
            reason=str(data.get("reason") or "Служебная папка исключена из архива."),
            severity="info",
            pattern=name,
        )

    for name, data in junk.get("file_names", {}).items():
        reason = data if isinstance(data, str) else data.get("reason", "")
        rules.junk_file_names[name.lower()] = FileRule(
            id=f"junk-name:{name}",
            kind="junk",
            title=name,
            reason=str(reason or "Служебный файл исключён из архива."),
            severity="info",
            pattern=name,
        )

    for pattern, data in junk.get("file_globs", {}).items():
        reason = data if isinstance(data, str) else data.get("reason", "")
        rules.junk_file_globs.append(
            FileRule(
                id=f"junk-glob:{pattern}",
                kind="junk",
                title=pattern,
                reason=str(reason or "Служебный файл исключён из архива."),
                severity="info",
                pattern=pattern,
            )
        )

    for name, data in secret.get("file_names", {}).items():
        rules.secret_file_names[name.lower()] = FileRule(
            id=f"secret-name:{name}",
            kind="secret",
            title=str(data.get("title", name)),
            reason=str(data.get("reason", "Файл может содержать секреты.")),
            severity=str(data.get("severity", "high")),
            pattern=name,
        )

    for pattern, data in secret.get("file_globs", {}).items():
        rules.secret_file_globs.append(
            FileRule(
                id=f"secret-glob:{pattern}",
                kind="secret",
                title=str(data.get("title", pattern)),
                reason=str(data.get("reason", "Файл может содержать секреты.")),
                severity=str(data.get("severity", "high")),
                pattern=pattern,
            )
        )

    compiled: list[SecretPattern] = []
    for data in secret.get("content_patterns", []):
        rule_id = str(data.get("id", "unnamed"))
        pattern_text = str(data.get("pattern", ""))
        if not pattern_text:
            raise RuleConfigError(f"Пустой regex в правиле {rule_id}")
        try:
            compiled.append(
                SecretPattern(
                    id=rule_id,
                    title=str(data.get("title", rule_id)),
                    severity=str(data.get("severity", "high")),
                    regex=re.compile(pattern_text, re.MULTILINE),
                    value_group=int(data.get("value_group", 0)),
                    kind=str(data.get("kind", "typed")),
                )
            )
        except re.error as exc:
            raise RuleConfigError(f"Ошибка regex в правиле {rule_id}: {exc}") from exc

    rules.content_patterns = tuple(compiled)
    return rules
