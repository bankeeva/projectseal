"""Создать синтетические демонстрационные проекты.

Все «секреты» здесь вымышлены и нужны только для проверки правил.
Ни один файл не содержит реальных доступов.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"

# Синтетические значения собираются из частей: так GitHub secret scanning
# не принимает демо-файлы за настоящие утечки. Сгенерированные файлы
# (demo/leaky_project) в git не попадают.
OPENAI_KEY = "sk-proj-" + "DemoKeyAbCdEfGhIjKlMnOpQrStUvWx"
AWS_KEY = "AKIA" + "ZZ7Q2X4M9PLK3RTU"
AWS_SECRET = "Demo" + "SecretKey1234567890AbCdEf"
GITHUB_TOKEN = "ghp_" + "DemoTokenAbCdEfGhIjKlMnOpQrStUvWx12"
GOOGLE_KEY = "AIza" + "DemoKeyAbCdEfGhIjKlMnOpQrStUvWx12YZ"
STRIPE_KEY = "sk_live_" + "DemoStripeKey1234567890"
SLACK_TOKEN = "xoxb-" + "123456789012-DemoTokenAbCdEfGh"
NPM_TOKEN = "npm_" + "DemoToken1234567890"
JWT_TOKEN = "eyJhbGciOiJIUzI1NiJ9" + "." + "eyJzdWIiOiJkZW1vIn0" + "." + "demo_signature_1234567890"
DB_PASSWORD = "Demo" + "DbPass123"
NOTES_PASSWORD = "Demo" + "Passw0rd!2026"
CREDENTIAL_PASSWORD = "Demo" + "Credential123!"
RSA_HEADER = "-----BEGIN " + "RSA PRIVATE KEY-----"
RSA_FOOTER = "-----END " + "RSA PRIVATE KEY-----"
PRIVATE_HEADER = "-----BEGIN " + "PRIVATE KEY-----"
PRIVATE_FOOTER = "-----END " + "PRIVATE KEY-----"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def make_leaky_project() -> None:
    project = DEMO / "leaky_project"
    if project.exists():
        import shutil

        shutil.rmtree(project)
    project.mkdir(parents=True)

    write(
        project / "README.md",
        "# Учебный проект «Северный ветер»\n\n"
        "Демонстрационный проект для проверки ProjectSeal. Все ключи ниже — "
        "синтетические и не дают доступа ни к каким сервисам.\n\n"
        "## Запуск\n\n```bash\npython -m src.main\n```\n",
    )
    write(project / "requirements.txt", "fastapi==0.115.0\nuvicorn==0.30.0\npydantic==2.9.0\n")
    write(project / ".gitignore", ".env\nvenv/\n__pycache__/\n*.log\n")
    write(
        project / ".env",
        "APP_NAME=NorthWind Demo\n"
        "DB_HOST=localhost\n"
        "DB_USER=demo_user\n"
        "DB_PASSWORD=SuperSecretDemo123!\n"
        f"OPENAI_API_KEY={OPENAI_KEY}\n",
    )
    write(
        project / ".env.example",
        "APP_NAME=NorthWind Demo\n"
        "DB_HOST=localhost\n"
        "DB_USER=your_user_here\n"
        "DB_PASSWORD=your_password_here\n"
        "OPENAI_API_KEY=sk-proj-your_key_here\n",
    )

    write(
        project / "keys" / "id_rsa",
        f"{RSA_HEADER}\n"
        "MIIEowIBAAKCAQEA0DemoOnlyKeyMaterial000000000000000000000000\n"
        "000000000000000000000000000000000000000000000000000000000000\n"
        f"{RSA_FOOTER}\n",
    )
    write(project / "keys" / "id_rsa.pub", "ssh-rsa AAAAB3DemoPublicKeyOnly user@demo\n")

    write(
        project / "config" / "settings.py",
        '"""Настройки демо-проекта."""\n\n'
        f'AWS_ACCESS_KEY_ID = "{AWS_KEY}"\n'
        f'AWS_SECRET_ACCESS_KEY = "{AWS_SECRET}"\n'
        f'GITHUB_TOKEN = "{GITHUB_TOKEN}"\n'
        f'GOOGLE_API_KEY = "{GOOGLE_KEY}"\n',
    )
    write(
        project / "config" / "google.json",
        f'{{\n  "api_key": "{GOOGLE_KEY}",\n'
        '  "project": "northwind-demo"\n}\n',
    )
    write(
        project / "config" / "service-account.json",
        '{\n  "type": "service_account",\n  "private_key": "'
        + PRIVATE_HEADER
        + '\\nDemoOnly\\n'
        + PRIVATE_FOOTER
        + '\\n",\n  "client_email": "demo@example.invalid"\n}\n',
    )
    write(
        project / ".npmrc",
        "registry=https://registry.npmjs.org/\n"
        f"//registry.npmjs.org/:_authToken={NPM_TOKEN}\n",
    )

    write(
        project / "src" / "__init__.py",
        '"""Пакет приложения."""\n',
    )
    write(
        project / "src" / "main.py",
        "from fastapi import FastAPI\n\n"
        "from .api_client import fetch_weather\n\n"
        "app = FastAPI(title=\"NorthWind Demo\")\n\n\n"
        "@app.get(\"/health\")\n"
        "def health() -> dict[str, str]:\n"
        "    return {\"status\": \"ok\"}\n\n\n"
        "@app.get(\"/weather\")\n"
        "def weather(city: str = \"demo\") -> dict:\n"
        "    return fetch_weather(city)\n",
    )
    write(
        project / "src" / "api_client.py",
        '"""Клиент внешнего API (демонстрационные ключи)."""\n\n'
        f'STRIPE_SECRET_KEY = "{STRIPE_KEY}"\n'
        f'SLACK_TOKEN = "{SLACK_TOKEN}"\n\n\n'
        "def fetch_weather(city: str) -> dict:\n"
        "    return {\"city\": city, \"temperature\": 21, \"source\": \"demo\"}\n",
    )
    write(
        project / "src" / "auth.py",
        '"""Демонстрационная авторизация."""\n\n'
        f'DEMO_JWT = "{JWT_TOKEN}"\n\n\n'
        "def current_user(token: str) -> str:\n"
        "    return \"demo\" if token else \"anonymous\"\n",
    )
    write(
        project / "src" / "database.py",
        '"""Работа с локальной базой."""\n\n'
        f'DATABASE_URL = "postgres://demo_user:{DB_PASSWORD}@db.example.local:5432/demo"\n\n\n'
        "def connect() -> str:\n"
        "    return DATABASE_URL\n",
    )
    for index in range(2, 9):
        write(
            project / "src" / f"module_{index}.py",
            f'"""Учебный модуль {index}."""\n\n'
            f"def calculate_{index}(value: int) -> int:\n"
            f"    return value * {index} + {index}\n",
        )

    for index in range(1, 5):
        write(
            project / "tests" / f"test_module_{index}.py",
            f"from src.module_{index + 1} import calculate_{index + 1}\n\n\n"
            f"def test_calculate_{index}() -> None:\n"
            f"    assert calculate_{index + 1}(2) == 2 * {index + 1} + {index + 1}\n",
        )

    write(
        project / "docs" / "notes.md",
        "# Заметки разработчика\n\n"
        "Проверить подключение к демо-базе.\n\n"
        f"    password = \"{NOTES_PASSWORD}\"\n\n"
        f"Старая строка подключения: postgres://demo_user:{DB_PASSWORD}@db.example.local:5432/demo\n",
    )
    write(
        project / "docs" / "architecture.md",
        "# Архитектура\n\n"
        "```\nUI -> API -> Service -> Repository -> Database\n```\n\n"
        "Слои общаются через DTO. Секретов в этом документе нет.\n",
    )
    write(
        project / "credentials.json",
        '{\n  "username": "demo",\n  "password": "'
        + CREDENTIAL_PASSWORD
        + '",\n  "note": "synthetic demo only"\n}\n',
    )

    write_bytes(
        project / "assets" / "logo.png",
        bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
            "890000000d49444154789c6360000000020001e221bc330000000049454e44ae"
            "426082"
        ),
    )
    write_bytes(
        project / "data" / "users.db",
        b"SQLite format 3\x00" + b"\x00" * 128 + b"demo database, not real\x00",
    )
    write(project / "data" / "sample.json", '{"items": [1, 2, 3], "source": "demo"}\n')

    # Мусор: зависимости, окружения, кэши, логи, служебные файлы.
    packages = {
        "react": 40,
        "react-dom": 40,
        "lodash": 40,
    }
    for package, count in packages.items():
        for index in range(count):
            write(
                project / "node_modules" / package / f"file_{index}.js",
                f"module.exports = {{ id: {index}, package: \"{package}\" }};\n",
            )
    for index in range(30):
        write(
            project / "venv" / "lib" / "python3.12" / "site-packages" / f"pkg_{index}.py",
            f"VERSION = \"{index}.0\"\n",
        )
    for index in range(4):
        write_bytes(
            project / "__pycache__" / f"module_{index}.cpython-312.pyc",
            b"\x00\x01demo compiled cache\x00",
        )
    write(project / ".git" / "HEAD", "ref: refs/heads/main\n")
    write(project / ".git" / "config", "[core]\n\trepositoryformatversion = 0\n")
    write(project / ".git" / "refs" / "heads" / "main", "0000000000000000000000000000000000000000\n")
    write(project / ".pytest_cache" / "README.md", "pytest cache\n")
    write(project / ".pytest_cache" / "v" / "cache" / "nodeids", "[]\n")
    write(project / "logs" / "app.log", "2026-11-01 INFO demo started\n2026-11-01 INFO health ok\n")
    write(project / "logs" / "error.log", "2026-11-01 WARNING demo warning\n")
    write_bytes(project / ".DS_Store", b"\x00\x00\x00\x01Bud1\x00\x00\x00\x00demo")
    write(project / ".idea" / "workspace.xml", "<project version=\"4\"><component name=\"demo\"/></project>\n")
    for index in range(3):
        write(project / "build" / f"artifact_{index}.tmp", "temporary build artifact\n")

    write(
        project / "README_DEMO.md",
        "# Демо-папка ProjectSeal\n\n"
        "Эта папка специально содержит синтетические секреты и мусор. "
        "Она нужна для демонстрации работы приложения.\n",
    )


def make_clean_project() -> None:
    project = DEMO / "clean_project"
    if project.exists():
        import shutil

        shutil.rmtree(project)
    project.mkdir(parents=True)

    write(
        project / "README.md",
        "# Чистый учебный проект\n\n"
        "Небольшой проект без секретов и мусора. Подходит для быстрой проверки "
        "сценария упаковки.\n",
    )
    write(project / "requirements.txt", "requests==2.32.0\n")
    write(project / ".env.example", "API_URL=https://example.invalid/api\nAPI_KEY=your_key_here\n")
    write(project / ".gitignore", ".env\nvenv/\n__pycache__/\n")
    write(project / "src" / "__init__.py", "")
    write(
        project / "src" / "main.py",
        "from .calculator import add\n\n\n"
        "def main() -> None:\n"
        "    print(add(2, 2))\n\n\n"
        "if __name__ == \"__main__\":\n"
        "    main()\n",
    )
    write(
        project / "src" / "calculator.py",
        "def add(left: int, right: int) -> int:\n"
        "    return left + right\n\n\n"
        "def multiply(left: int, right: int) -> int:\n"
        "    return left * right\n",
    )
    write(
        project / "tests" / "test_calculator.py",
        "from src.calculator import add, multiply\n\n\n"
        "def test_add() -> None:\n"
        "    assert add(2, 2) == 4\n\n\n"
        "def test_multiply() -> None:\n"
        "    assert multiply(3, 4) == 12\n",
    )
    write(project / "docs" / "usage.md", "# Использование\n\n```bash\npython -m src.main\n```\n")
    write(project / "LICENSE", "MIT License\n\nCopyright (c) 2026 Demo\n")
    for index in range(1, 6):
        write(
            project / "src" / f"helper_{index}.py",
            f"def helper_{index}(value: int) -> int:\n    return value + {index}\n",
        )


def main() -> None:
    DEMO.mkdir(parents=True, exist_ok=True)
    make_leaky_project()
    make_clean_project()
    write(
        DEMO / "README.md",
        "# Демонстрационные проекты\n\n"
        "* `leaky_project` — синтетические секреты и мусор для проверки всех трёх функций.\n"
        "* `clean_project` — чистый проект без рисков.\n\n"
        "Все ключи и пароли вымышлены. Не используйте эти значения как настоящие.\n",
    )
    print("demo projects created in", DEMO)


if __name__ == "__main__":
    main()
