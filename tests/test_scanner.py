from __future__ import annotations

import hashlib
import os
import stat
import sys
import threading
import time
from pathlib import Path

import pytest

from projectseal.core.models import Category
from projectseal.core.rules import load_rules
from projectseal.core.scanner import ScanInputError, Scanner, ScanOptions


@pytest.fixture(scope="module")
def rules():
    return load_rules()


def test_classification_and_summary(rules, sample_project: Path) -> None:
    result = Scanner(rules).scan(sample_project)
    assert result.cancelled is False
    assert result.summary.secrets_found == 1
    assert result.summary.junk_found == 6  # 5 файлов node_modules + server.log
    assert result.summary.safe_to_pack == 4  # main.py, README, .env.example, binary.dat
    assert result.summary.total_files == 11
    assert result.summary.binary_files == 1
    assert result.summary.errors_count == 0

    env = result.item_by_path(".env")
    assert env is not None
    assert env.category is Category.SECRET
    assert env.selected is False
    assert "SuperSecret123!" not in env.preview
    assert "••" in env.preview

    example = result.item_by_path(".env.example")
    assert example is not None
    assert example.category is Category.SAFE

    node_modules = result.item_by_path("node_modules")
    assert node_modules is not None
    assert node_modules.category is Category.JUNK
    assert node_modules.is_dir is True
    assert node_modules.child_count == 5


def test_source_files_are_not_modified(rules, sample_project: Path) -> None:
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    before = {
        str(path.relative_to(sample_project)): (digest(path), path.stat().st_mtime_ns)
        for path in sample_project.rglob("*")
        if path.is_file()
    }
    Scanner(rules).scan(sample_project)
    after = {
        str(path.relative_to(sample_project)): (digest(path), path.stat().st_mtime_ns)
        for path in sample_project.rglob("*")
        if path.is_file()
    }
    assert before == after


@pytest.mark.skipif(sys.platform.startswith("win"), reason="симлинки требуют прав Windows")
def test_symlinks_are_not_followed(rules, tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("password = 'OutsideSecret123!'\n", encoding="utf-8")
    (root / "inside.txt").write_text("safe\n", encoding="utf-8")
    (root / "external_link").symlink_to(outside, target_is_directory=True)
    (root / "file_link.txt").symlink_to(outside / "secret.txt")

    result = Scanner(rules).scan(root)
    assert result.item_by_path("external_link") is not None
    assert result.item_by_path("external_link").category is Category.JUNK
    assert result.item_by_path("file_link.txt") is not None
    assert result.item_by_path("file_link.txt").category is Category.JUNK
    assert result.summary.secrets_found == 0
    assert all(not item.relative_path.startswith("external_link/") for item in result.items)


@pytest.mark.skipif(sys.platform.startswith("win"), reason="chmod на Windows не работает")
@pytest.mark.skipif(getattr(os, "geteuid", lambda: 1)() == 0, reason="root игнорирует права доступа")
def test_permission_denied_is_reported_as_unverified(rules, tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    secret = root / "locked.txt"
    secret.write_text("password = 'SuperSecret123!'\n", encoding="utf-8")
    secret.chmod(0o000)
    try:
        result = Scanner(rules).scan(root)
        item = result.item_by_path("locked.txt")
        assert item is not None
        assert item.category is Category.SECRET
        assert item.severity == "unknown"
        assert result.summary.unverified_count == 1
        assert result.summary.errors_count == 1
        assert result.errors[0].kind == "permission"
    finally:
        secret.chmod(0o600)


def test_cyrillic_paths_and_content(rules, tmp_path: Path) -> None:
    root = tmp_path / "проект"
    (root / "исходники").mkdir(parents=True)
    (root / "исходники" / "настройки.py").write_text(
        "# комментарий\npassword = 'ОченьСекретныйПароль123'\n", encoding="utf-8"
    )
    (root / "README.md").write_text("# Привет\n", encoding="utf-8")
    result = Scanner(rules).scan(root)
    secret = result.item_by_path("исходники/настройки.py")
    assert secret is not None
    assert secret.category is Category.SECRET
    assert "ОченьСекретныйПароль123" not in secret.preview
    assert result.summary.secrets_found == 1


def test_binary_and_large_files_are_marked(rules, tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "image.bin").write_bytes(b"\x00\x01\x02" * 100)
    (root / "large.txt").write_text("a" * (6 * 1024 * 1024), encoding="utf-8")
    result = Scanner(rules).scan(root)
    binary = result.item_by_path("image.bin")
    large = result.item_by_path("large.txt")
    assert binary is not None and binary.category is Category.SAFE
    assert large is not None and large.category is Category.SAFE
    assert result.summary.binary_files == 1
    assert result.summary.large_files == 1
    assert any(error.kind == "skipped" for error in result.errors)


def test_max_files_limit(rules, tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    for index in range(10):
        (root / f"file_{index}.py").write_text("x = 1\n", encoding="utf-8")
    result = Scanner(rules, ScanOptions(max_files=5)).scan(root)
    assert result.summary.total_files == 5
    assert result.summary.limits_hit
    assert "лимит" in result.summary.limits_hit[0].lower()


def test_cancel_returns_partial_result(rules, tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    for index in range(20):
        (root / f"file_{index}.txt").write_text("data\n", encoding="utf-8")
    cancel = threading.Event()
    cancel.set()
    result = Scanner(rules).scan(root, cancel=cancel)
    assert result.cancelled is True


def test_missing_and_non_directory_input(rules, tmp_path: Path) -> None:
    with pytest.raises(ScanInputError):
        Scanner(rules).scan(tmp_path / "missing")
    file_path = tmp_path / "file.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(ScanInputError):
        Scanner(rules).scan(file_path)


def test_empty_directory(rules, tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    result = Scanner(rules).scan(root)
    assert result.summary.total_files == 0
    assert result.summary.safe_to_pack == 0
    assert result.items == []


def test_progress_callback_is_called(rules, sample_project: Path) -> None:
    phases: list[str] = []
    Scanner(rules).scan(sample_project, progress=lambda p: phases.append(p.phase))
    assert "walk" in phases
    assert "analyze" in phases
    assert "done" in phases


def test_scan_1000_files_under_60_seconds(rules, tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    for index in range(1000):
        (root / f"module_{index}.py").write_text(
            f"def function_{index}():\n    return {index}\n", encoding="utf-8"
        )
    started = time.perf_counter()
    result = Scanner(rules).scan(root)
    elapsed = time.perf_counter() - started
    assert result.summary.safe_to_pack == 1000
    assert elapsed < 60, f"scan took {elapsed:.2f}s"
