"""Tests for coach.repos — repos.toml loader and validation."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from coach import repos, state


def _init_git(path: Path) -> None:
    """Make `path` look like a git repo without committing anything."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)


def test_load_repos_returns_entries_in_declared_order(
    isolated_state_dir, tmp_path
):
    state.ensure_dir()

    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    _init_git(repo_a)
    _init_git(repo_b)

    state.repos_path().write_text(
        f"""
[[repo]]
path      = "{repo_a}"
nickname  = "A"
languages = ["python"]

[[repo]]
path      = "{repo_b}"
nickname  = "B"
languages = ["java", "kotlin"]
"""
    )

    entries = repos.load_repos()

    assert [e.nickname for e in entries] == ["A", "B"]
    assert entries[0].path == repo_a
    assert entries[0].languages == ["python"]
    assert entries[1].languages == ["java", "kotlin"]


def test_load_repos_missing_file_raises_with_init_hint(isolated_state_dir):
    # state dir exists but no repos.toml
    state.ensure_dir()

    with pytest.raises(repos.ReposConfigError, match="coach.cli init"):
        repos.load_repos()


def test_load_repos_missing_path_raises_with_nickname(isolated_state_dir):
    state.ensure_dir()
    state.repos_path().write_text(
        """
[[repo]]
path      = "/nonexistent/ghost-repo"
nickname  = "Ghost"
languages = ["python"]
"""
    )

    with pytest.raises(repos.ReposConfigError, match="Ghost"):
        repos.load_repos()


def test_load_repos_non_git_dir_raises(isolated_state_dir, tmp_path):
    state.ensure_dir()
    not_a_repo = tmp_path / "plain_dir"
    not_a_repo.mkdir()
    state.repos_path().write_text(
        f"""
[[repo]]
path      = "{not_a_repo}"
nickname  = "Plain"
languages = ["python"]
"""
    )

    with pytest.raises(repos.ReposConfigError, match="not a git repo"):
        repos.load_repos()


def test_load_repos_missing_required_field_raises(isolated_state_dir):
    state.ensure_dir()
    state.repos_path().write_text(
        """
[[repo]]
path     = "/tmp"
nickname = "NoLangs"
"""
    )

    with pytest.raises(repos.ReposConfigError, match="languages"):
        repos.load_repos()


def test_load_repos_empty_returns_empty_list(isolated_state_dir):
    state.ensure_dir()
    state.repos_path().write_text("# no entries yet\n")

    assert repos.load_repos() == []
