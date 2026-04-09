from pathlib import Path
import subprocess

import pytest

from tests import db_test_utils


def test_should_start_local_test_services_only_for_local_default_port() -> None:
    assert db_test_utils.should_start_local_test_services(
        "postgresql+psycopg://eve_trader:eve_trader@localhost:5432/eve_trader_test"
    )
    assert db_test_utils.should_start_local_test_services(
        "postgresql+psycopg://eve_trader:eve_trader@127.0.0.1:5432/eve_trader_test"
    )
    assert db_test_utils.should_start_local_test_services("postgresql+psycopg://eve_trader:eve_trader@/eve_trader_test")
    assert db_test_utils.should_start_local_test_services(
        "postgresql+psycopg://eve_trader:eve_trader@db.internal:5432/eve_trader_test"
    ) is False
    assert db_test_utils.should_start_local_test_services(
        "postgresql+psycopg://eve_trader:eve_trader@localhost:6432/eve_trader_test"
    ) is False


def test_start_local_test_services_uses_repo_root_and_postgres_service(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(
        cmd: list[str],
        *,
        cwd: Path,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> None:
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["check"] = check
        captured["capture_output"] = capture_output
        captured["text"] = text

    monkeypatch.setattr(subprocess, "run", fake_run)

    db_test_utils.start_local_test_services()

    assert captured == {
        "cmd": ["docker", "compose", "up", "-d", "postgres"],
        "cwd": db_test_utils.REPO_ROOT,
        "check": True,
        "capture_output": True,
        "text": True,
    }


def test_start_local_test_services_surfaces_compose_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: object, **kwargs: object) -> None:
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=["docker", "compose", "up", "-d", "postgres"],
            stderr="compose failure",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="compose failure"):
        db_test_utils.start_local_test_services()
