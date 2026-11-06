from __future__ import annotations

import pytest

from projectseal.core.rules import RuleConfigError, load_rules

# Все значения ниже синтетические. Они собираются из частей, чтобы
# GitHub secret scanning не принимал тесты за утечку настоящих ключей.
AWS_KEY = "AKIA" + "ZZ7Q2X4M9PLK3RTU"
GITHUB_TOKEN = "ghp_" + "AbCdEfGhIjKlMnOpQrStUvWx123456"
OPENAI_KEY = "sk-proj-" + "AbCdEfGhIjKlMnOpQrStUvWx"
STRIPE_KEY = "sk_live_" + "AbCdEfGhIjKlMnOpQrSt"
SLACK_TOKEN = "xoxb-" + "123456789012-AbCdEfGhIj"
GOOGLE_KEY = "AIza" + "AbCdEfGhIjKlMnOpQrStUvWxYz123456789"
JWT_TOKEN = "eyJhbGciOiJIUzI1NiJ9" + "." + "eyJzdWIiOiJkZW1vIn0" + "." + "signature12345"
PRIVATE_KEY_HEADER = "-----BEGIN " + "RSA PRIVATE KEY-----"
NPM_TOKEN = "npm_" + "AbCdEfGhIjKlMnOpQr"


@pytest.fixture(scope="module")
def rules():
    return load_rules()


def test_secret_filename_rules(rules) -> None:
    assert rules.classify_filename(".env").kind == "secret"
    assert rules.classify_filename(".env.production").kind == "secret"
    assert rules.classify_filename(".ENV").kind == "secret"
    assert rules.classify_filename("id_rsa").kind == "secret"
    assert rules.classify_filename("server.pem").kind == "secret"
    assert rules.classify_filename("credentials.json").kind == "secret"


def test_example_files_are_ignored(rules) -> None:
    assert rules.classify_filename(".env.example") is None
    assert rules.classify_filename(".env.sample") is None
    assert rules.classify_filename("config.example.json") is None
    assert rules.classify_filename("id_rsa.pub") is None


def test_junk_rules(rules) -> None:
    assert rules.junk_dir_rule("node_modules") is not None
    assert rules.junk_dir_rule(".venv") is not None
    assert rules.junk_dir_rule("__pycache__") is not None
    assert rules.classify_filename("server.log").kind == "junk"
    assert rules.classify_filename(".DS_Store").kind == "junk"
    assert rules.classify_filename("main.py") is None


def test_placeholder_values_are_not_secrets(rules) -> None:
    assert rules.find_secret("password = 'your_password_here'") is None
    assert rules.find_secret("api_key = 'changeme123'") is None
    assert rules.find_secret("token = os.getenv('TOKEN')") is None
    assert rules.find_secret("password = '${DB_PASSWORD}'") is None
    assert rules.find_secret("password = 'SuperSecret123!'") is not None


@pytest.mark.parametrize(
    ("text", "rule_id"),
    [
        (f"AWS_ACCESS_KEY_ID={AWS_KEY}", "aws_access_key"),
        (f"token = {GITHUB_TOKEN}", "github_token"),
        (f"key = {OPENAI_KEY}", "openai_api_key"),
        (f"key = {STRIPE_KEY}", "stripe_secret_key"),
        (f"token = {SLACK_TOKEN}", "slack_token"),
        (f"key = {GOOGLE_KEY}", "google_api_key"),
        (f"token = {JWT_TOKEN}", "jwt_token"),
        (
            "DATABASE_URL=postgres://user:SuperSecret123@localhost:5432/db",
            "database_url_password",
        ),
        (PRIVATE_KEY_HEADER, "private_key_block"),
        (f"npm_token={NPM_TOKEN}", "npm_token"),
        ('"password": "SuperSecret123!"', "generic_password"),
        ('"api_key": "AbCdEfGhIjKlMnOp"', "generic_api_key"),
        ('"access_token": "AbCdEfGhIjKlMnOp"', "generic_token"),
    ],
)
def test_content_patterns(rules, text: str, rule_id: str) -> None:
    match = rules.find_secret(text)
    assert match is not None
    assert match.rule_id == rule_id


def test_preview_does_not_contain_raw_value(rules) -> None:
    value = "SuperSecret123!"
    match = rules.find_secret(f"password = '{value}'")
    assert match is not None
    assert value not in match.preview
    assert "••" in match.preview


def test_invalid_rules_file_raises(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(RuleConfigError):
        load_rules(path)


def test_invalid_regex_raises(tmp_path) -> None:
    path = tmp_path / "bad_regex.json"
    path.write_text(
        '{"version":"1","junk":{},"secret":{"content_patterns":'
        '[{"id":"x","pattern":"["}]},"placeholders":[]}',
        encoding="utf-8",
    )
    with pytest.raises(RuleConfigError):
        load_rules(path)
