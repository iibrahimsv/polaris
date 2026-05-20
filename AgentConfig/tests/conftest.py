import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def isolated_state_dir(tmp_path, monkeypatch):
    """Point COACH_STATE_DIR at an isolated temp dir for the test."""
    state_dir = tmp_path / "agentstate"
    monkeypatch.setenv("COACH_STATE_DIR", str(state_dir))
    return state_dir


@pytest.fixture
def make_repo(tmp_path):
    """Factory that builds a git repo at `tmp_path / name` with N commits.

    Each commit gets a controlled commit-timestamp and modifies one file
    named after the language hint (so file extensions match declared
    languages — useful for future per-extension language inference).

    Commits are listed newest-first (index 0 is HEAD); the fixture
    iterates in reverse so the FIRST entry becomes the most recent
    commit and `git log` walks history chronologically.

    Usage:
        repo = make_repo(
            name="alpha",
            commits=[
                ("2026-05-14T20:00:00+00:00", "main.py", "print('a')\n"),  # HEAD
                ("2026-05-13T20:00:00+00:00", "main.py", "print('b')\n"),
            ],
        )
    """

    def _build(name: str, commits: list[tuple[str, str, str]]) -> Path:
        repo = tmp_path / name
        repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=repo, check=True
        )
        for iso_ts, filename, content in reversed(commits):
            (repo / filename).write_text(content)
            subprocess.run(["git", "add", filename], cwd=repo, check=True)
            env = {
                **os.environ,
                "GIT_AUTHOR_DATE": iso_ts,
                "GIT_COMMITTER_DATE": iso_ts,
            }
            subprocess.run(
                ["git", "commit", "-q", "-m", f"commit at {iso_ts}"],
                cwd=repo,
                env=env,
                check=True,
            )
        return repo

    return _build
