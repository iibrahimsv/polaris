"""Pure git command wrappers used by the Historian.

Each function shells out to one `git` invocation, parses its output,
and returns a typed value. No side effects outside the repo, no file
writes anywhere. Designed to be unit-testable with tmp_path repos.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _run_git(repo: Path, args: list[str]) -> str:
    """Run `git <args>` in `repo` and return stdout. Empty string on failure."""
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def last_commit_timestamp(repo: Path) -> datetime | None:
    """Return the committer-date of HEAD as an aware UTC datetime.

    Returns None for an empty repo (no commits).
    """
    out = _run_git(repo, ["log", "-1", "--format=%cI"]).strip()
    if not out:
        return None
    dt = datetime.fromisoformat(out)
    return dt.astimezone(timezone.utc)


def commits_in_window(
    repo: Path, days: int, now: datetime | None = None
) -> int:
    """Count commits with committer-date within the last `days * 24` hours.

    `now` defaults to datetime.now(timezone.utc); pass an explicit value
    in tests for determinism.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).isoformat()
    out = _run_git(
        repo,
        ["log", f"--since={since}", "--format=%H"],
    )
    if not out.strip():
        return 0
    return len([line for line in out.splitlines() if line.strip()])
