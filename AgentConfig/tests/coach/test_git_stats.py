"""Tests for coach.git_stats — pure git command wrappers."""

from __future__ import annotations

from datetime import datetime, timezone

from coach import git_stats


def test_last_commit_timestamp_returns_most_recent(make_repo):
    repo = make_repo(
        name="alpha",
        commits=[
            ("2026-05-14T20:00:00+00:00", "main.py", "v3\n"),
            ("2026-05-13T20:00:00+00:00", "main.py", "v2\n"),
            ("2026-05-12T20:00:00+00:00", "main.py", "v1\n"),
        ],
    )

    ts = git_stats.last_commit_timestamp(repo)

    assert ts == datetime(2026, 5, 14, 20, 0, 0, tzinfo=timezone.utc)


def test_last_commit_timestamp_returns_none_on_empty_repo(tmp_path):
    import subprocess

    repo = tmp_path / "empty"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    assert git_stats.last_commit_timestamp(repo) is None


def test_commits_in_window_counts_only_within_window(make_repo):
    # "Now" for the test is fixed at 2026-05-14T23:00:00 UTC.
    # The 7-day window covers 2026-05-07T23:00 → 2026-05-14T23:00.
    repo = make_repo(
        name="alpha",
        commits=[
            ("2026-05-14T20:00:00+00:00", "f.py", "a\n"),  # in 24h
            ("2026-05-13T20:00:00+00:00", "f.py", "b\n"),  # in 7d, not 24h
            ("2026-05-09T20:00:00+00:00", "f.py", "c\n"),  # in 7d
            ("2026-05-01T20:00:00+00:00", "f.py", "d\n"),  # out of 7d
        ],
    )

    now = datetime(2026, 5, 14, 23, 0, 0, tzinfo=timezone.utc)

    assert git_stats.commits_in_window(repo, days=1, now=now) == 1
    assert git_stats.commits_in_window(repo, days=7, now=now) == 3


def test_commits_in_window_zero_on_empty_repo(tmp_path):
    import subprocess

    repo = tmp_path / "empty"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    assert git_stats.commits_in_window(repo, days=7) == 0


def test_diff_lines_in_window_sums_insertions_and_deletions(make_repo):
    # Two commits inside the window, one outside.
    repo = make_repo(
        name="diffrepo",
        commits=[
            ("2026-05-14T20:00:00+00:00", "a.py", "line1\nline2\nline3\n"),
            ("2026-05-13T20:00:00+00:00", "a.py", "line1\nline2\n"),
            ("2026-05-01T20:00:00+00:00", "a.py", "line1\n"),
        ],
    )
    now = datetime(2026, 5, 14, 23, 0, 0, tzinfo=timezone.utc)

    # Commit at 05-14 adds 1 line (3 - 2). Commit at 05-13 adds 1 line
    # (2 - 1, from a.py creation perspective at that commit). The 05-01
    # commit creates the file with 1 line, but it's outside the 7d window.
    result = git_stats.diff_lines_in_window(repo, days=7, now=now)

    assert result["insertions"] >= 2  # at minimum the two in-window adds
    assert "deletions" in result
    assert result["total"] == result["insertions"] + result["deletions"]


def test_diff_lines_in_window_zero_on_empty_repo(tmp_path):
    import subprocess

    repo = tmp_path / "empty"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    result = git_stats.diff_lines_in_window(repo, days=7)

    assert result == {"insertions": 0, "deletions": 0, "total": 0}


def test_diff_lines_in_window_skips_commits_outside_window(make_repo):
    repo = make_repo(
        name="oldonly",
        commits=[
            ("2026-05-01T20:00:00+00:00", "a.py", "x\ny\nz\n"),
        ],
    )
    now = datetime(2026, 5, 14, 23, 0, 0, tzinfo=timezone.utc)

    result = git_stats.diff_lines_in_window(repo, days=7, now=now)

    assert result == {"insertions": 0, "deletions": 0, "total": 0}
