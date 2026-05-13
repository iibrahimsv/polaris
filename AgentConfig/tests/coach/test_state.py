from pathlib import Path

import pytest

from coach import state


def test_state_dir_default_is_home_agentstate(monkeypatch):
    monkeypatch.delenv("COACH_STATE_DIR", raising=False)
    assert state.state_dir() == Path.home() / "agentstate"


def test_state_dir_respects_env_override(isolated_state_dir):
    assert state.state_dir() == isolated_state_dir


def test_path_helpers_compose_under_state_dir(isolated_state_dir):
    assert state.profile_path() == isolated_state_dir / "profile.md"
    assert state.config_path() == isolated_state_dir / "config.toml"
    assert state.repos_path() == isolated_state_dir / "repos.toml"
    assert state.signals_path() == isolated_state_dir / "signals.md"
    assert state.today_path() == isolated_state_dir / "today.md"
    assert state.critique_log_path() == isolated_state_dir / "critique_log.md"
    assert state.derived_state_path() == isolated_state_dir / "derived_state.md"
    assert state.drift_path() == isolated_state_dir / "drift.md"
    assert state.lessons_path() == isolated_state_dir / "lessons.md"


def test_ensure_dir_creates_full_layout(isolated_state_dir):
    state.ensure_dir()
    assert isolated_state_dir.is_dir()
    assert (isolated_state_dir / "archive" / "signals").is_dir()
    assert (isolated_state_dir / "archive" / "today").is_dir()
    assert (isolated_state_dir / "solutions").is_dir()


def test_ensure_dir_is_idempotent(isolated_state_dir):
    state.ensure_dir()
    state.ensure_dir()  # must not raise
    assert isolated_state_dir.is_dir()


def test_atomic_write_creates_file_with_content(isolated_state_dir):
    state.ensure_dir()
    target = isolated_state_dir / "hello.md"
    state.atomic_write(target, "hello world\n")
    assert target.read_text() == "hello world\n"


def test_atomic_write_overwrites_existing(isolated_state_dir):
    state.ensure_dir()
    target = isolated_state_dir / "hello.md"
    state.atomic_write(target, "first\n")
    state.atomic_write(target, "second\n")
    assert target.read_text() == "second\n"


def test_atomic_write_does_not_leave_temp_files_on_success(isolated_state_dir):
    state.ensure_dir()
    target = isolated_state_dir / "hello.md"
    state.atomic_write(target, "content\n")
    leftover = list(isolated_state_dir.glob("*.tmp"))
    assert leftover == []
