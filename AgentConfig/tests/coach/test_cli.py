import subprocess
import sys
from pathlib import Path

import pytest

from coach import cli, state


def run_cli(args, env_state_dir):
    """Invoke the CLI as a function call (faster than subprocess)."""
    return cli.main(args)


def test_init_creates_state_dir_and_template_files(isolated_state_dir):
    exit_code = run_cli(["init"], isolated_state_dir)
    assert exit_code == 0
    assert isolated_state_dir.is_dir()
    assert state.profile_path().exists()
    assert state.config_path().exists()
    assert state.repos_path().exists()
    assert (isolated_state_dir / "archive" / "signals").is_dir()
    assert (isolated_state_dir / "archive" / "today").is_dir()
    assert (isolated_state_dir / "solutions").is_dir()


def test_init_profile_contains_expected_template_headers(isolated_state_dir):
    run_cli(["init"], isolated_state_dir)
    profile_text = state.profile_path().read_text()
    assert "# Engineering Profile" in profile_text
    assert "## Target role" in profile_text
    assert "## Focus areas this quarter" in profile_text


def test_init_does_not_overwrite_existing_profile(isolated_state_dir):
    run_cli(["init"], isolated_state_dir)
    state.atomic_write(state.profile_path(), "my custom profile\n")
    run_cli(["init"], isolated_state_dir)
    assert state.profile_path().read_text() == "my custom profile\n"


def test_init_force_overwrites_existing_profile(isolated_state_dir):
    run_cli(["init"], isolated_state_dir)
    state.atomic_write(state.profile_path(), "my custom profile\n")
    run_cli(["init", "--force"], isolated_state_dir)
    assert "# Engineering Profile" in state.profile_path().read_text()


def test_status_on_fresh_state_dir_reports_missing(isolated_state_dir, capsys):
    isolated_state_dir.mkdir(parents=True, exist_ok=True)
    exit_code = run_cli(["status"], isolated_state_dir)
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "profile.md" in captured.out
    assert "missing" in captured.out.lower()


def test_status_after_init_reports_present(isolated_state_dir, capsys):
    run_cli(["init"], isolated_state_dir)
    run_cli(["status"], isolated_state_dir)
    captured = capsys.readouterr()
    assert "profile.md" in captured.out
    assert "present" in captured.out.lower()
    assert "config.toml" in captured.out
    assert "repos.toml" in captured.out


def test_module_entrypoint_runs():
    """Invoking the module via `python -m coach.cli --help` exits 0."""
    result = subprocess.run(
        [sys.executable, "-m", "coach.cli", "--help"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    assert result.returncode == 0
    assert "init" in result.stdout
    assert "status" in result.stdout
