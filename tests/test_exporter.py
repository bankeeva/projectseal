from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

import pytest

from projectseal.core.errors import ExportError
from projectseal.core.exporter import ExportOptions, ZipExporter
from projectseal.core.models import Category, FileItem, ScanResult, ScanSummary
from projectseal.core.rules import load_rules
from projectseal.core.scanner import Scanner


@pytest.fixture(scope="module")
def rules():
    return load_rules()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_export_contains_only_safe_files(rules, sample_project: Path, tmp_path: Path) -> None:
    result = Scanner(rules).scan(sample_project)
    destination = tmp_path / "clean.zip"
    export = ZipExporter(ExportOptions(allow_overwrite=False)).export(result, destination)

    assert destination.exists()
    assert export.verified is True
    assert export.included_files == 4
    assert export.excluded_secret_files == 1
    assert export.excluded_junk_files == 6
    assert export.excluded_by_user == 0

    with zipfile.ZipFile(destination) as archive:
        names = archive.namelist()
        assert archive.testzip() is None
    assert set(names) == {"README.md", "binary.dat", ".env.example", "src/main.py"}
    assert ".env" not in names
    assert not any(name.startswith("node_modules/") for name in names)
    assert "server.log" not in names


def test_source_files_unchanged_after_export(rules, sample_project: Path, tmp_path: Path) -> None:
    result = Scanner(rules).scan(sample_project)
    before = {
        str(path.relative_to(sample_project)): file_digest(path)
        for path in sample_project.rglob("*")
        if path.is_file()
    }
    ZipExporter().export(result, tmp_path / "clean.zip")
    after = {
        str(path.relative_to(sample_project)): file_digest(path)
        for path in sample_project.rglob("*")
        if path.is_file()
    }
    assert before == after


def test_user_can_deselect_safe_file(rules, sample_project: Path, tmp_path: Path) -> None:
    result = Scanner(rules).scan(sample_project)
    binary = result.item_by_path("binary.dat")
    assert binary is not None
    binary.selected = False
    destination = tmp_path / "clean.zip"
    export = ZipExporter().export(result, destination)
    assert export.excluded_by_user == 1
    with zipfile.ZipFile(destination) as archive:
        assert "binary.dat" not in archive.namelist()


def test_no_selected_files_raises(rules, sample_project: Path, tmp_path: Path) -> None:
    result = Scanner(rules).scan(sample_project)
    for item in result.safe:
        item.selected = False
    with pytest.raises(ExportError):
        ZipExporter().export(result, tmp_path / "clean.zip")


def test_destination_inside_project_is_rejected(rules, sample_project: Path) -> None:
    result = Scanner(rules).scan(sample_project)
    with pytest.raises(ExportError):
        ZipExporter().export(result, sample_project / "clean.zip")


def test_overwrite_requires_permission(rules, sample_project: Path, tmp_path: Path) -> None:
    result = Scanner(rules).scan(sample_project)
    destination = tmp_path / "clean.zip"
    destination.write_bytes(b"old data")
    with pytest.raises(ExportError):
        ZipExporter(ExportOptions(allow_overwrite=False)).export(result, destination)
    export = ZipExporter(ExportOptions(allow_overwrite=True)).export(result, destination)
    assert export.verified is True
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None


def test_path_traversal_is_skipped(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "ok.txt").write_text("ok", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("password = 'OutsideSecret123!'\n", encoding="utf-8")

    result = ScanResult(
        root=root,
        items=[
            FileItem("ok.txt", Category.SAFE, "ok", file_size=2),
            FileItem("../outside.txt", Category.SAFE, "bad", file_size=30),
        ],
        summary=ScanSummary(total_files=2, safe_to_pack=2, safe_selected=2),
    )
    destination = tmp_path / "clean.zip"
    export = ZipExporter().export(result, destination)
    with zipfile.ZipFile(destination) as archive:
        names = archive.namelist()
    assert names == ["ok.txt"]
    assert all(".." not in name for name in names)
    assert "../outside.txt" in export.skipped_files


@pytest.mark.skipif(sys.platform.startswith("win"), reason="симлинки требуют прав Windows")
def test_symlink_in_safe_item_is_skipped(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "ok.txt").write_text("ok", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    (root / "link.txt").symlink_to(outside)

    result = ScanResult(
        root=root,
        items=[
            FileItem("ok.txt", Category.SAFE, "ok", file_size=2),
            FileItem("link.txt", Category.SAFE, "link", file_size=6),
        ],
        summary=ScanSummary(total_files=2, safe_to_pack=2, safe_selected=2),
    )
    destination = tmp_path / "clean.zip"
    export = ZipExporter().export(result, destination)
    with zipfile.ZipFile(destination) as archive:
        assert archive.namelist() == ["ok.txt"]
    assert "link.txt" in export.skipped_files


def test_unicode_archive_names(rules, tmp_path: Path) -> None:
    root = tmp_path / "проект"
    (root / "исходники").mkdir(parents=True)
    (root / "исходники" / "привет.py").write_text("print('привет')\n", encoding="utf-8")
    result = Scanner(rules).scan(root)
    destination = tmp_path / "архив.zip"
    export = ZipExporter().export(result, destination)
    assert export.included_files == 1
    with zipfile.ZipFile(destination) as archive:
        assert archive.namelist() == ["исходники/привет.py"]
        assert archive.testzip() is None


def test_missing_parent_directory_raises(rules, sample_project: Path, tmp_path: Path) -> None:
    result = Scanner(rules).scan(sample_project)
    with pytest.raises(ExportError):
        ZipExporter().export(result, tmp_path / "missing" / "clean.zip")
