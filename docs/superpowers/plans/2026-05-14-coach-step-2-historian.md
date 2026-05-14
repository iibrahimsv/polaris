# Historian Nightly (Step 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Historian nightly job — a deterministic, LLM-free Python script that walks every repo in `~/agentstate/repos.toml`, computes activity stats over the last 24 hours and 7 days, and atomically writes a human-readable summary to `~/agentstate/derived_state.md`. Exposed as `coach historian nightly`, schedulable via cron at 23:00. This file is the load-bearing input that Step 3 (Coach v0) reads to ground today's debrief in real activity.

**Architecture:** Three pure, testable modules — `repos.py` parses `repos.toml` into validated `RepoEntry` objects; `git_stats.py` wraps `git log` / `git log --numstat` as pure functions over a repo path; `historian.py` orchestrates (snapshot dataclass → markdown render → atomic write). One new CLI subparser (`historian nightly`) wires the orchestrator to argparse. No Anthropic API calls in Step 2 — LLM synthesis is explicitly deferred (spec §3.4: "Tools: Bash (git log, git diff --stat), file r/w"). Synthesis can be layered on later without changing the data pipeline.

**Tech Stack:** Python 3.11 (stdlib `tomllib`, `subprocess`, `dataclasses`, `datetime`), pytest 8 (test-only), existing `coach.state` module for `atomic_write` and `derived_state_path()`.

**Spec reference:** `docs/superpowers/specs/2026-05-13-engineering-coach-system-design.md` — §3.4 (Historian agent), §4.3 (`repos.toml` schema), §5 (code structure), §6 build order step 2.

**Out of scope for Step 2 (deferred):**

- Weekly synthesis (`drift.md`, `lessons.md`) — Step 6.
- LLM synthesis call over the raw stats — can be added in any later step without changing this plan's interfaces.
- Per-file language detection from extensions — Step 2 uses repos.toml's declared `languages` array as the language proxy.

---

## File Structure

Files created or modified in this plan:

```
AgentConfig/
├── coach/
│   ├── repos.py                            # NEW: load + validate repos.toml
│   ├── git_stats.py                        # NEW: pure git command wrappers
│   ├── historian.py                        # NEW: snapshot, render, run_nightly()
│   └── cli.py                              # MODIFY: add `historian nightly` subparser
└── tests/
    └── coach/
        ├── conftest.py                     # MODIFY: add make_repo fixture
        ├── test_repos.py                   # NEW
        ├── test_git_stats.py               # NEW
        ├── test_historian.py               # NEW
        └── test_cli.py                     # MODIFY: add historian nightly E2E test
```

**Responsibilities:**

- `repos.py` — single source of truth for "what repos exist." Pure I/O + validation. Zero git knowledge.
- `git_stats.py` — pure functions over a repo Path. Each function shells out to one `git` command, parses output, returns a typed value. Zero file writes outside the repo.
- `historian.py` — orchestrator. Combines repos + git_stats into a `Snapshot` dataclass, renders markdown, atomic_writes to `derived_state.md`. Zero subprocess calls of its own.
- `cli.py` — argparse glue only. The `historian` subparser routes to `historian.run_nightly()`.

**Why this split:** each module is independently testable. `git_stats.py` tests build temp repos with `subprocess`. `repos.py` tests use temp toml files. `historian.py` tests stub `git_stats` and `repos` to assert renderer + writer behavior. `cli.py` tests run the full stack end-to-end against a temp repo.

---

## Task 1: Repos loader + validation (TDD)

**Files:**
- Create: `AgentConfig/coach/repos.py`
- Create: `AgentConfig/tests/coach/test_repos.py`

The loader reads `~/agentstate/repos.toml` (path via `state.repos_path()`), parses it with stdlib `tomllib`, and returns a list of validated `RepoEntry` objects. Validation: every declared `path` must exist on disk and contain a `.git` directory (or be a git worktree). Missing files surface as a typed exception so the CLI can print something actionable.

- [ ] **Step 1: Write the failing test for the happy path**

Create `AgentConfig/tests/coach/test_repos.py`:

```python
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


def test_load_repos_returns_entries_in_declared_order(tmp_path, monkeypatch):
    monkeypatch.setenv("COACH_STATE_DIR", str(tmp_path))
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m pytest tests/coach/test_repos.py -v
```

Expected: `ModuleNotFoundError: No module named 'coach.repos'` or `ImportError`.

- [ ] **Step 3: Implement coach/repos.py**

Create `AgentConfig/coach/repos.py`:

```python
"""Load and validate ~/agentstate/repos.toml into RepoEntry objects.

Pure I/O + validation. No git knowledge — see coach.git_stats for that.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from coach import state


class ReposConfigError(Exception):
    """Raised when repos.toml is missing, malformed, or points at bad paths."""


@dataclass(frozen=True)
class RepoEntry:
    path: Path
    nickname: str
    languages: list[str]


def load_repos() -> list[RepoEntry]:
    """Parse repos.toml and return RepoEntry objects in declared order.

    Raises ReposConfigError with a remediation hint if the file is
    missing, unparseable, or references a non-existent / non-git path.
    """
    toml_path = state.repos_path()
    if not toml_path.exists():
        raise ReposConfigError(
            f"{toml_path} not found. Run: python -m coach.cli init"
        )

    try:
        data = tomllib.loads(toml_path.read_text())
    except tomllib.TOMLDecodeError as e:
        raise ReposConfigError(f"{toml_path}: {e}") from e

    raw_entries = data.get("repo", [])
    if not isinstance(raw_entries, list):
        raise ReposConfigError(
            f"{toml_path}: expected [[repo]] array, got {type(raw_entries).__name__}"
        )

    entries: list[RepoEntry] = []
    for i, raw in enumerate(raw_entries):
        for required in ("path", "nickname", "languages"):
            if required not in raw:
                raise ReposConfigError(
                    f"{toml_path}: entry #{i + 1} is missing '{required}'"
                )
        path = Path(raw["path"])
        if not path.exists():
            raise ReposConfigError(
                f"{toml_path}: '{raw['nickname']}' path does not exist: {path}"
            )
        if not (path / ".git").exists():
            raise ReposConfigError(
                f"{toml_path}: '{raw['nickname']}' is not a git repo: {path}"
            )
        entries.append(
            RepoEntry(
                path=path,
                nickname=str(raw["nickname"]),
                languages=list(raw["languages"]),
            )
        )

    return entries
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m pytest tests/coach/test_repos.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Add error-path tests**

Append to `AgentConfig/tests/coach/test_repos.py`:

```python
def test_load_repos_missing_file_raises_with_init_hint(tmp_path, monkeypatch):
    monkeypatch.setenv("COACH_STATE_DIR", str(tmp_path))
    # state dir exists but no repos.toml
    state.ensure_dir()

    with pytest.raises(repos.ReposConfigError, match="coach.cli init"):
        repos.load_repos()


def test_load_repos_missing_path_raises_with_nickname(tmp_path, monkeypatch):
    monkeypatch.setenv("COACH_STATE_DIR", str(tmp_path))
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


def test_load_repos_non_git_dir_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("COACH_STATE_DIR", str(tmp_path))
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


def test_load_repos_missing_required_field_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("COACH_STATE_DIR", str(tmp_path))
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


def test_load_repos_empty_returns_empty_list(tmp_path, monkeypatch):
    monkeypatch.setenv("COACH_STATE_DIR", str(tmp_path))
    state.ensure_dir()
    state.repos_path().write_text("# no entries yet\n")

    assert repos.load_repos() == []
```

- [ ] **Step 6: Run all repos tests**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m pytest tests/coach/test_repos.py -v
```

Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent
git add AgentConfig/coach/repos.py AgentConfig/tests/coach/test_repos.py
git commit -m "$(cat <<'EOF'
feat(coach): add repos.toml loader with validation

Parses ~/agentstate/repos.toml into typed RepoEntry objects and
surfaces actionable errors when paths are missing, dirs aren't
git repos, or required fields are absent. This is the input
contract for the Historian nightly walker.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Shared test fixture — `make_repo` helper

**Files:**
- Modify: `AgentConfig/tests/coach/conftest.py`

The next two tasks (`git_stats.py` tests, integration tests) need to build small git repos with controlled commit timestamps. Put the helper in `conftest.py` so both can import it as a fixture.

- [ ] **Step 1: Read the current conftest.py**

```bash
cat /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig/tests/coach/conftest.py
```

Expected: a small fixture (likely a `state_dir` override). Note its current content — you will append, not overwrite.

- [ ] **Step 2: Append the make_repo fixture**

Append to `AgentConfig/tests/coach/conftest.py`:

```python
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest


@pytest.fixture
def make_repo(tmp_path):
    """Factory that builds a git repo at `tmp_path / name` with N commits.

    Each commit gets a controlled commit-timestamp and modifies one file
    named after the language hint (so file extensions match declared
    languages — useful for future per-extension language inference).

    Usage:
        repo = make_repo(
            name="alpha",
            commits=[
                ("2026-05-14T20:00:00+00:00", "main.py", "print('a')\n"),
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
        for iso_ts, filename, content in commits:
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
```

- [ ] **Step 3: Verify nothing broke**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m pytest tests/ -v
```

Expected: all previously passing tests still pass (16 from Step 1 + 5 from Task 1 = 21 passed). No new tests yet — Task 3 consumes the fixture.

- [ ] **Step 4: Commit**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent
git add AgentConfig/tests/coach/conftest.py
git commit -m "$(cat <<'EOF'
test(coach): add make_repo fixture for git-backed tests

Lets git_stats and historian tests build small repos with
controlled commit timestamps without polluting the real
filesystem outside tmp_path.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `git_stats.py` — timestamps and commit counts (TDD)

**Files:**
- Create: `AgentConfig/coach/git_stats.py`
- Create: `AgentConfig/tests/coach/test_git_stats.py`

Two pure functions:

- `last_commit_timestamp(path)` → `datetime | None`. Returns the most recent commit's committer-date as an aware UTC datetime, or `None` if the repo has zero commits.
- `commits_in_window(path, days)` → `int`. Counts commits where committer-date is within the last `days * 24` hours.

- [ ] **Step 1: Write failing tests**

Create `AgentConfig/tests/coach/test_git_stats.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m pytest tests/coach/test_git_stats.py -v
```

Expected: `ModuleNotFoundError: No module named 'coach.git_stats'`.

- [ ] **Step 3: Implement coach/git_stats.py**

Create `AgentConfig/coach/git_stats.py`:

```python
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
    # %cI is strict ISO-8601 with timezone. fromisoformat handles it
    # natively on Python 3.11.
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
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m pytest tests/coach/test_git_stats.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent
git add AgentConfig/coach/git_stats.py AgentConfig/tests/coach/test_git_stats.py
git commit -m "$(cat <<'EOF'
feat(coach): add git_stats — last commit + commits-in-window

Pure functions that wrap `git log` for the Historian. last_commit_timestamp
returns an aware UTC datetime (or None for empty repos); commits_in_window
counts commits inside the last N days using an injectable `now` so tests
stay deterministic.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `git_stats.py` — diff line counts (TDD)

**Files:**
- Modify: `AgentConfig/coach/git_stats.py`
- Modify: `AgentConfig/tests/coach/test_git_stats.py`

Add `diff_lines_in_window(repo, days, now=None)` → `dict[str, int]` with keys `insertions`, `deletions`, `total`. Uses `git log --since=... --numstat` and sums the numeric columns across all listed files in the window. Binary files (which numstat shows as `- -`) are skipped.

- [ ] **Step 1: Write failing tests**

Append to `AgentConfig/tests/coach/test_git_stats.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m pytest tests/coach/test_git_stats.py -v
```

Expected: 4 passed, 3 failed (new tests fail with `AttributeError: module 'coach.git_stats' has no attribute 'diff_lines_in_window'`).

- [ ] **Step 3: Implement diff_lines_in_window**

Append to `AgentConfig/coach/git_stats.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m pytest tests/coach/test_git_stats.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent
git add AgentConfig/coach/git_stats.py AgentConfig/tests/coach/test_git_stats.py
git commit -m "$(cat <<'EOF'
feat(coach): add git_stats.diff_lines_in_window

Sums insertions and deletions across commits in the last N days using
`git log --numstat`. Skips binary files. Used by the Historian to
estimate hours-by-stack.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Historian snapshot + markdown renderer (TDD)

**Files:**
- Create: `AgentConfig/coach/historian.py`
- Create: `AgentConfig/tests/coach/test_historian.py`

Three pieces in one module:

- `@dataclass RepoSnapshot` — per-repo derived data (nickname, path, last_commit, commits_24h, commits_7d, diff_total_7d, languages).
- `@dataclass Snapshot` — top-level (generated_at, repos: list[RepoSnapshot], hours_by_stack: dict[str, float]).
- `collect_snapshot(repos: list[RepoEntry], now=None, lines_per_hour=60)` — fans out to `git_stats`, builds the snapshot.
- `render_derived_state(snap: Snapshot) -> str` — pure function, snapshot → markdown.

Hours-by-stack uses the simplest defensible model: for each repo, take its 7-day diff total, distribute equally across its declared languages, then sum across repos. `LINES_PER_HOUR = 60` is the user-tunable knob.

- [ ] **Step 1: Write failing tests**

Create `AgentConfig/tests/coach/test_historian.py`:

```python
"""Tests for coach.historian — snapshot dataclasses, collector, renderer."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from coach import historian
from coach.repos import RepoEntry


def test_collect_snapshot_aggregates_per_repo(make_repo):
    repo_a = make_repo(
        name="A",
        commits=[
            ("2026-05-14T20:00:00+00:00", "main.py", "a\nb\nc\n"),
            ("2026-05-13T20:00:00+00:00", "main.py", "a\nb\n"),
            ("2026-05-08T20:00:00+00:00", "main.py", "a\n"),
        ],
    )
    repo_b = make_repo(
        name="B",
        commits=[
            ("2026-05-10T20:00:00+00:00", "App.java", "class App {}\n"),
        ],
    )

    entries = [
        RepoEntry(path=repo_a, nickname="Alpha", languages=["python"]),
        RepoEntry(path=repo_b, nickname="Bravo", languages=["java"]),
    ]
    now = datetime(2026, 5, 14, 23, 0, 0, tzinfo=timezone.utc)

    snap = historian.collect_snapshot(entries, now=now, lines_per_hour=60)

    assert snap.generated_at == now
    assert len(snap.repos) == 2
    assert snap.repos[0].nickname == "Alpha"
    assert snap.repos[0].commits_24h == 1
    assert snap.repos[0].commits_7d == 2
    assert snap.repos[1].nickname == "Bravo"
    assert snap.repos[1].commits_24h == 0
    assert snap.repos[1].commits_7d == 1
    assert "python" in snap.hours_by_stack
    assert "java" in snap.hours_by_stack
    assert snap.hours_by_stack["python"] > 0


def test_collect_snapshot_empty_repo_yields_zero_stats(make_repo, tmp_path):
    import subprocess

    empty = tmp_path / "empty_repo"
    empty.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=empty, check=True)

    entries = [
        RepoEntry(path=empty, nickname="Empty", languages=["python"]),
    ]
    now = datetime(2026, 5, 14, 23, 0, 0, tzinfo=timezone.utc)

    snap = historian.collect_snapshot(entries, now=now)

    assert snap.repos[0].last_commit is None
    assert snap.repos[0].commits_24h == 0
    assert snap.repos[0].commits_7d == 0
    assert snap.repos[0].diff_total_7d == 0
    assert snap.hours_by_stack == {"python": 0.0}


def test_collect_snapshot_multi_language_repo_splits_diff(make_repo):
    repo = make_repo(
        name="multilang",
        commits=[
            ("2026-05-14T20:00:00+00:00", "f.py", "x\ny\nz\n"),
        ],
    )
    entries = [
        RepoEntry(path=repo, nickname="Multi", languages=["python", "java"]),
    ]
    now = datetime(2026, 5, 14, 23, 0, 0, tzinfo=timezone.utc)

    snap = historian.collect_snapshot(entries, now=now, lines_per_hour=60)

    # Total diff = 3 lines. Split across 2 languages = 1.5 lines each.
    # Hours = 1.5 / 60 = 0.025 each.
    assert snap.hours_by_stack["python"] == snap.hours_by_stack["java"]
    assert snap.hours_by_stack["python"] > 0


def test_render_derived_state_includes_all_repos_and_totals():
    snap = historian.Snapshot(
        generated_at=datetime(2026, 5, 14, 23, 0, 0, tzinfo=timezone.utc),
        repos=[
            historian.RepoSnapshot(
                nickname="Alpha",
                path=Path("/tmp/alpha"),
                last_commit=datetime(2026, 5, 14, 20, 0, 0, tzinfo=timezone.utc),
                commits_24h=1,
                commits_7d=3,
                diff_total_7d=120,
                languages=["python"],
            ),
        ],
        hours_by_stack={"python": 2.0},
    )

    text = historian.render_derived_state(snap)

    assert "2026-05-14" in text
    assert "Alpha" in text
    assert "/tmp/alpha" in text
    assert "120" in text  # diff total appears
    assert "python" in text
    assert "2.0" in text  # hours-by-stack value appears


def test_render_derived_state_handles_empty_repos_list():
    snap = historian.Snapshot(
        generated_at=datetime(2026, 5, 14, 23, 0, 0, tzinfo=timezone.utc),
        repos=[],
        hours_by_stack={},
    )

    text = historian.render_derived_state(snap)

    assert "2026-05-14" in text
    assert "no repos" in text.lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m pytest tests/coach/test_historian.py -v
```

Expected: `ModuleNotFoundError: No module named 'coach.historian'`.

- [ ] **Step 3: Implement coach/historian.py**

Create `AgentConfig/coach/historian.py`:

```python
"""Historian — nightly activity snapshot writer.

Walks every repo in ~/agentstate/repos.toml, gathers stats via
coach.git_stats, builds a Snapshot dataclass, renders it to markdown,
and atomically writes ~/agentstate/derived_state.md.

Pure pipeline. No LLM call in Step 2 — synthesis is deferred.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from coach import git_stats, state
from coach.repos import RepoEntry, load_repos

LINES_PER_HOUR = 60
"""Default conversion factor for diff lines → engineering hours.
60 lines/hour is a defensible industry-average rule of thumb. Override
per-call via collect_snapshot(..., lines_per_hour=X)."""


@dataclass(frozen=True)
class RepoSnapshot:
    nickname: str
    path: Path
    last_commit: datetime | None
    commits_24h: int
    commits_7d: int
    diff_total_7d: int
    languages: list[str]


@dataclass(frozen=True)
class Snapshot:
    generated_at: datetime
    repos: list[RepoSnapshot]
    hours_by_stack: dict[str, float]


def collect_snapshot(
    entries: list[RepoEntry],
    now: datetime | None = None,
    lines_per_hour: int = LINES_PER_HOUR,
) -> Snapshot:
    """Walk every entry and assemble a Snapshot. Pure aggregation."""
    if now is None:
        now = datetime.now(timezone.utc)

    repos: list[RepoSnapshot] = []
    lines_by_lang: dict[str, float] = {}

    for entry in entries:
        last = git_stats.last_commit_timestamp(entry.path)
        c24 = git_stats.commits_in_window(entry.path, days=1, now=now)
        c7 = git_stats.commits_in_window(entry.path, days=7, now=now)
        diff = git_stats.diff_lines_in_window(entry.path, days=7, now=now)

        repos.append(
            RepoSnapshot(
                nickname=entry.nickname,
                path=entry.path,
                last_commit=last,
                commits_24h=c24,
                commits_7d=c7,
                diff_total_7d=diff["total"],
                languages=list(entry.languages),
            )
        )

        # distribute this repo's diff equally across its declared languages
        if entry.languages:
            share = diff["total"] / len(entry.languages)
            for lang in entry.languages:
                lines_by_lang[lang] = lines_by_lang.get(lang, 0.0) + share

    hours_by_stack = {
        lang: round(lines / lines_per_hour, 2)
        for lang, lines in lines_by_lang.items()
    }

    return Snapshot(
        generated_at=now,
        repos=repos,
        hours_by_stack=hours_by_stack,
    )


def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "(no commits yet)"
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def render_derived_state(snap: Snapshot) -> str:
    """Render a Snapshot to the markdown that lands in derived_state.md."""
    date = snap.generated_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
    gen_dt = _fmt_dt(snap.generated_at)

    lines: list[str] = []
    lines.append(f"# Derived State — {date}")
    lines.append("")
    lines.append(f"_Generated {gen_dt} by Historian nightly._")
    lines.append("")

    if not snap.repos:
        lines.append(
            "No repos configured. Add entries to "
            "`~/agentstate/repos.toml` and re-run."
        )
        lines.append("")
        return "\n".join(lines)

    total_commits_7d = sum(r.commits_7d for r in snap.repos)
    active_24h = [r.nickname for r in snap.repos if r.commits_24h > 0]
    active_7d = [r.nickname for r in snap.repos if r.commits_7d > 0]

    lines.append("## Activity (last 7 days)")
    lines.append("")
    lines.append(f"- Total commits: **{total_commits_7d}**")
    lines.append(
        f"- Active in last 24h: **{len(active_24h)}**"
        + (f"  — {', '.join(active_24h)}" if active_24h else "")
    )
    lines.append(
        f"- Active in last 7d:  **{len(active_7d)}**"
        + (f"  — {', '.join(active_7d)}" if active_7d else "")
    )
    lines.append("")

    lines.append("## Per repo")
    lines.append("")
    for r in snap.repos:
        lines.append(f"### {r.nickname}  `{r.path}`")
        lines.append(f"- last commit:   {_fmt_dt(r.last_commit)}")
        lines.append(f"- commits (24h): {r.commits_24h}")
        lines.append(f"- commits (7d):  {r.commits_7d}")
        lines.append(f"- diff lines 7d: {r.diff_total_7d}")
        lines.append(f"- languages:     {', '.join(r.languages) or '(none)'}")
        lines.append("")

    lines.append("## Hours by stack (estimated)")
    lines.append("")
    lines.append(f"_Factor: {LINES_PER_HOUR} lines/hour. Tune in historian.py._")
    lines.append("")
    if not snap.hours_by_stack:
        lines.append("- (no language data)")
    else:
        for lang in sorted(snap.hours_by_stack):
            lines.append(f"- **{lang}**: {snap.hours_by_stack[lang]} hrs")
    lines.append("")

    return "\n".join(lines)


def run_nightly(now: datetime | None = None) -> Path:
    """Top-level entrypoint for `coach historian nightly`.

    Loads repos.toml, collects the snapshot, renders markdown, and
    atomically writes ~/agentstate/derived_state.md. Returns the path.
    """
    entries = load_repos()
    snap = collect_snapshot(entries, now=now)
    text = render_derived_state(snap)
    target = state.derived_state_path()
    state.atomic_write(target, text)
    return target
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m pytest tests/coach/test_historian.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent
git add AgentConfig/coach/historian.py AgentConfig/tests/coach/test_historian.py
git commit -m "$(cat <<'EOF'
feat(coach): add Historian snapshot, renderer, and run_nightly

collect_snapshot fans out to git_stats for every RepoEntry and assembles
a typed Snapshot. render_derived_state turns it into markdown. run_nightly
ties load_repos + collect + render + atomic_write into the entrypoint that
the CLI and cron will call.

Hours-by-stack uses a 60 lines/hour rule of thumb, configurable per call.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: CLI wiring — `coach historian nightly` (TDD)

**Files:**
- Modify: `AgentConfig/coach/cli.py`
- Modify: `AgentConfig/tests/coach/test_cli.py`

Add a `historian` subparser with one sub-subcommand `nightly`. Wired so future Step 6 work can add `weekly` next to it without touching this code.

- [ ] **Step 1: Read the current cli.py and test_cli.py**

```bash
cat /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig/coach/cli.py
cat /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig/tests/coach/test_cli.py
```

Note the existing `build_parser()` structure — you will add a new sibling subparser, not modify the existing `init` / `status` ones. Note the test harness style (probably uses the `state_dir` fixture from conftest).

- [ ] **Step 2: Write the failing E2E test**

Append to `AgentConfig/tests/coach/test_cli.py`:

```python
def test_cli_historian_nightly_writes_derived_state(
    make_repo, tmp_path, monkeypatch, capsys
):
    from coach import cli, state

    monkeypatch.setenv("COACH_STATE_DIR", str(tmp_path))
    state.ensure_dir()

    repo = make_repo(
        name="cli_alpha",
        commits=[
            ("2026-05-14T20:00:00+00:00", "main.py", "a\nb\nc\n"),
            ("2026-05-13T20:00:00+00:00", "main.py", "a\nb\n"),
        ],
    )
    state.repos_path().write_text(
        f"""
[[repo]]
path      = "{repo}"
nickname  = "CliAlpha"
languages = ["python"]
"""
    )

    exit_code = cli.main(["historian", "nightly"])

    assert exit_code == 0
    out = state.derived_state_path().read_text()
    assert "Derived State" in out
    assert "CliAlpha" in out
    assert "python" in out

    captured = capsys.readouterr()
    assert "derived_state.md" in captured.out
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m pytest tests/coach/test_cli.py::test_cli_historian_nightly_writes_derived_state -v
```

Expected: failure — argparse rejects `historian` as an unknown subcommand.

- [ ] **Step 4: Wire the subparser in cli.py**

Add to `AgentConfig/coach/cli.py` near the top of the file (after the existing imports):

```python
from coach import historian
```

Add this handler function near the existing `cmd_init` / `cmd_status` handlers:

```python
def cmd_historian_nightly(args: argparse.Namespace) -> int:
    target = historian.run_nightly()
    print(f"wrote {target}")
    return 0
```

In `build_parser()`, **before** the `return parser` line, add:

```python
    p_historian = sub.add_parser(
        "historian", help="long-arc activity history"
    )
    p_historian_sub = p_historian.add_subparsers(
        dest="historian_cmd", required=True
    )
    p_historian_nightly = p_historian_sub.add_parser(
        "nightly", help="walk repos and overwrite derived_state.md"
    )
    p_historian_nightly.set_defaults(func=cmd_historian_nightly)
```

- [ ] **Step 5: Run the new test to verify it passes**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m pytest tests/coach/test_cli.py::test_cli_historian_nightly_writes_derived_state -v
```

Expected: 1 passed.

- [ ] **Step 6: Run the full test suite to confirm no regressions**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m pytest tests/ -v
```

Expected: all previous passes plus the new one. Total ≈ 16 (Step 1) + 5 (repos) + 7 (git_stats) + 5 (historian) + 1 (cli historian) = 34 passed.

- [ ] **Step 7: Commit**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent
git add AgentConfig/coach/cli.py AgentConfig/tests/coach/test_cli.py
git commit -m "$(cat <<'EOF'
feat(coach): add `coach historian nightly` CLI subcommand

Wires historian.run_nightly() to argparse. The nested historian/nightly
shape leaves room for Step 6 to add `historian weekly` without restructuring.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Real-system smoke test + cron line

**Files:**
- No new files. This task is a manual verification + crontab install hint.

The unit tests cover the pipeline against synthetic repos. This task confirms the real path works against the user's actual `~/agentstate/repos.toml` (which already lists the ComposioAgent repo) and writes a real `derived_state.md` on the user's machine.

- [ ] **Step 1: Run the nightly job against the real state dir**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m coach.cli historian nightly
```

Expected stdout: `wrote /Users/iibrahimsv/agentstate/derived_state.md`.

Expected file to exist at `~/agentstate/derived_state.md` with a `# Derived State — YYYY-MM-DD` header, an Activity section with non-zero commits (you've committed today), a Per repo section listing the configured repos, and a Hours by stack section.

- [ ] **Step 2: Print and review the output**

```bash
cat /Users/iibrahimsv/agentstate/derived_state.md
```

Verify visually:
- Date matches today.
- Every repo in `repos.toml` appears under "Per repo".
- Numbers look right (compare against `git log --since="7 days ago" --oneline` in the same repo).
- Languages match what's declared in `repos.toml`.

- [ ] **Step 3: Print the cron line to install**

Print this line (do NOT auto-install it — the user will copy/paste into `crontab -e` so they see what's going into their crontab):

```
0 23 * * * /Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m coach.cli historian nightly --chdir /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig >> /Users/iibrahimsv/agentstate/.runlog 2>&1
```

(Note: `coach.cli` is invoked via `python -m` so it picks up `AgentConfig/` as the package root. The CLI doesn't currently support a `--chdir` flag; either run with `cd ... && ...` in cron OR set `PYTHONPATH` — pick the approach matching `.zshrc`/cron conventions on this machine.)

Recommended cron line (drop the unsupported flag, use `cd`):

```
0 23 * * * cd /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig && /Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m coach.cli historian nightly >> /Users/iibrahimsv/agentstate/.runlog 2>&1
```

This matches spec §5 ("cron entries"). The user installs it with `crontab -e`.

- [ ] **Step 4: No commit needed for this task**

Step 7 is verification + installation; no code changes.

---

## Task 8: Documentation — note Step 2 in the project README

**Files:**
- Modify: `README.md` (repo root)

The polaris README has a roadmap table with Step 2 marked "next." Move it to "shipped."

- [ ] **Step 1: Update the roadmap row**

In `/Users/iibrahimsv/PycharmProjects/ComposioAgent/README.md`, find the row:

```
| 2    | Historian      | Nightly repo crawl → `signals.md` digest         | next     |
```

Two corrections:
1. Status: `next` → `shipped`.
2. The original line said the Historian writes to `signals.md` — that was a typo in the README. Historian nightly writes to `derived_state.md` (Scout writes `signals.md`). Fix while you're here.

Replace with:

```
| 2    | Historian      | Nightly repo crawl → `derived_state.md` digest   | shipped  |
```

- [ ] **Step 2: Commit**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent
git add README.md
git commit -m "$(cat <<'EOF'
docs: mark Step 2 (Historian nightly) shipped in roadmap

Also corrects the original "signals.md" reference in the Historian
roadmap row to "derived_state.md" — signals.md is Scout's output,
derived_state.md is Historian's.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Verification — done definition

All of these must be true to call Step 2 complete:

- `pytest tests/` from `AgentConfig/` shows **all green** (34+ tests).
- `python -m coach.cli historian nightly` succeeds with a real `~/agentstate/repos.toml` and produces a readable `derived_state.md`.
- The cron line is installed in the user's crontab (verify with `crontab -l | grep historian`).
- README roadmap shows Step 2 as `shipped`.
- No new runtime dependencies added to `requirements.txt` (Step 2 is pure stdlib + existing deps).

Once these hold, Step 3 (Coach v0) can read `derived_state.md` as ground truth for the morning artifact.

---

## What is NOT in Step 2 (intentional)

- **LLM synthesis call** — Historian could call Claude to produce a narrative version of derived_state.md. Deferred. The mechanical output is already useful; synthesis adds cost and prompt-tuning surface area. Add in a separate plan if the raw numbers prove unreadable in practice.
- **Per-file extension language detection** — currently languages come from `repos.toml`. A more accurate model would parse file extensions from `git ls-files` output. Deferred.
- **Hours-by-stack tuning** — `LINES_PER_HOUR = 60` is hardcoded. A future plan can move this to `config.toml` and let the user calibrate from real timecards.
- **Weekly synthesis (`drift.md`, `lessons.md`)** — Step 6 in the spec.
- **Cron self-install** — the plan prints the line for the user to install. Auto-mutating `crontab` from a script is too high-risk for a personal coach tool.
