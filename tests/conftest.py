"""Общие фикстуры pytest."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

# Qt-тесты должны работать без дисплея.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]

# Синтетический ключ собирается в рантайме, чтобы статический сканер
# GitHub не принимал демо-значение за настоящий секрет.
DEMO_OPENAI_KEY = "sk-proj-" + "DemoKeyAbCdEfGhIjKlMnOpQrStUvWx"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def qapp():
    from projectseal.app import create_application

    app = create_application([])
    yield app
    app.quit()


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    (root / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    (root / ".env").write_text(
        f"DB_PASSWORD=SuperSecret123!\n"
        f"OPENAI_API_KEY={DEMO_OPENAI_KEY}\n",
        encoding="utf-8",
    )
    (root / ".env.example").write_text(
        "DB_PASSWORD=your_password_here\n", encoding="utf-8"
    )
    (root / "node_modules").mkdir()
    for index in range(5):
        (root / "node_modules" / f"pkg_{index}.js").write_text("x", encoding="utf-8")
    (root / "server.log").write_text("log line\n", encoding="utf-8")
    (root / "binary.dat").write_bytes(b"\x00\x01\x02" * 20)
    return root


def wait_for(app, predicate, timeout: float = 15.0, interval: float = 0.01) -> bool:
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        app.processEvents()
        if predicate():
            return True
        time.sleep(interval)
    app.processEvents()
    return bool(predicate())


@pytest.fixture
def wait_until(qapp):
    def _wait(predicate, timeout: float = 15.0) -> bool:
        return wait_for(qapp, predicate, timeout)

    return _wait
