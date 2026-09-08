from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
IMPORT_PREFIX = """
import sys

import dotenv

dotenv.load_dotenv = lambda *args, **kwargs: False
"""


def _run_clean_import(
    script: str, **environment_overrides: str
) -> subprocess.CompletedProcess[str]:
    environment = {
        "PYTHONPATH": str(REPOSITORY_ROOT),
        "PYTHON_DOTENV_DISABLED": "1",
        **environment_overrides,
    }
    return subprocess.run(
        [sys.executable, "-c", IMPORT_PREFIX + script],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_app_import_does_not_initialize_ai_clients() -> None:
    script = """
from app.main import app
from fastapi.testclient import TestClient

assert app is not None
assert "app.ai.service" not in sys.modules
assert "app.ai.chatbot" not in sys.modules
assert "app.ai.models.gemini" not in sys.modules
response = TestClient(app).get("/chat")
assert response.status_code == 503
"""

    result = _run_clean_import(script)

    assert result.returncode == 0, result.stderr


def test_configured_chainlit_mounts_without_initializing_ai_clients() -> None:
    script = """
from chainlit.config import config

from app.main import _chainlit_unavailable, app

chat_route = next(route for route in app.routes if getattr(route, "path", None) == "/chat")
assert chat_route.app is not _chainlit_unavailable
assert config.code.password_auth_callback is not None
assert config.code.oauth_callback is None
assert "app.ai.service" not in sys.modules
assert "app.ai.chatbot" not in sys.modules
assert "app.ai.models.gemini" not in sys.modules
"""

    result = _run_clean_import(script, CHAINLIT_AUTH_SECRET="test-secret")

    assert result.returncode == 0, result.stderr


def test_chainlit_registers_oauth_only_when_a_provider_is_configured() -> None:
    script = """
from chainlit.config import config

from app.main import app

assert app is not None
assert config.code.password_auth_callback is not None
assert config.code.oauth_callback is not None
assert "app.ai.service" not in sys.modules
assert "app.ai.chatbot" not in sys.modules
assert "app.ai.models.gemini" not in sys.modules
"""

    result = _run_clean_import(
        script,
        CHAINLIT_AUTH_SECRET="test-secret",
        OAUTH_GOOGLE_CLIENT_ID="test-client",
        OAUTH_GOOGLE_CLIENT_SECRET="test-secret",
    )

    assert result.returncode == 0, result.stderr
