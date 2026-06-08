"""Pure git command wrappers used by the Historian.

Each function shells out to one `git` invocation, parses its output,
and returns a typed value. No side effects outside the repo, no file
writes anywhere. Designed to be unit-testable with tmp_path repos.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Git's well-known SHA for the empty tree — used to diff the very first
# commit (which has no parent) against "nothing".
_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


@dataclass(frozen=True)
class CommitInfo:
    sha_short: str
    subject: str


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


def diff_lines_in_window(
    repo: Path, days: int, now: datetime | None = None
) -> dict[str, int]:
    """Sum inserted and deleted lines across commits in the last `days`.

    Returns {"insertions": N, "deletions": M, "total": N + M}.

    Binary files (which git --numstat reports as `- -`) are skipped.
    Empty repos and repos with zero in-window commits return all zeros.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).isoformat()
    out = _run_git(
        repo,
        ["log", f"--since={since}", "--numstat", "--format="],
    )

    insertions = 0
    deletions = 0
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added, removed, _filename = parts
        if added == "-" or removed == "-":
            # binary file
            continue
        try:
            insertions += int(added)
            deletions += int(removed)
        except ValueError:
            continue

    return {
        "insertions": insertions,
        "deletions": deletions,
        "total": insertions + deletions,
    }


def commit_diff(repo: Path, rev_range: str = "HEAD~1..HEAD") -> str:
    """Return the unified diff text for `rev_range`.

    For the default HEAD~1..HEAD on a repo whose HEAD has no parent (a
    single-commit repo), falls back to diffing HEAD against the git empty
    tree so the first commit is still reviewable. Returns "" on failure.
    """
    if rev_range == "HEAD~1..HEAD":
        has_parent = _run_git(
            repo, ["rev-parse", "--verify", "-q", "HEAD~1"]
        ).strip()
        if not has_parent:
            return _run_git(repo, ["diff", _EMPTY_TREE, "HEAD"])
    return _run_git(repo, ["diff", rev_range])


def head_commit_info(repo: Path) -> CommitInfo:
    """Return the short SHA and subject line of HEAD.

    Returns empty strings for a repo with no commits.
    """
    out = _run_git(repo, ["log", "-1", "--format=%h%x00%s"]).strip()
    if not out:
        return CommitInfo(sha_short="", subject="")
    sha, _, subject = out.partition("\x00")
    return CommitInfo(sha_short=sha, subject=subject)
