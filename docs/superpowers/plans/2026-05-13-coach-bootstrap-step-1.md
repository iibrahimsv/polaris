# Coach Bootstrap (Step 1) Implementation Plan

> **For agentic workers:** 
> REQUIRED SUB-SKILL: 
> Use superpowers:subagent-driven-development (recommended) or 
> superpowers:executing-plans to implement this plan task-by-task. 
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the `coach` CLI skeleton, the `~/agentstate/` state directory,
and the configuration templates (`profile.md`, `config.toml`, `repos.toml`) 
so the user has a working foundation to layer the 
Scout/Coach/Critic/Historian agents onto in subsequent plans.

**Architecture:** A new `AgentConfig/coach/` 
Python package with a thin argparse-based 
CLI (`coach init`, `coach status`), 
a `state.py` module that owns all path resolution and 
atomic file writes, and a `templates/` 
directory of starter files copied into `~/agentstate/` on init. 
State directory location is overridable via the `COACH_STATE_DIR` 
env var so tests can run in isolated temp directories. No external services, 
no API calls — this is pure scaffolding.

**Tech Stack:** Python 3.11 (uses stdlib `tomllib`), argparse (stdlib, no new runtime deps), 
pytest (test-only dep), `pathlib`, `os.replace` for atomic writes.

**Spec reference:** 
`docs/superpowers/specs/2026-05-13-engineering-coach-system-design.md` 
— §3 (agent designs), 
§4 (state directory contract), 
§5 (code structure), §6 build order step 1.

---

## File Structure

Files created in this plan:

```
AgentConfig/
├── requirements.txt                       # MODIFY: add pytest
├── coach/
│   ├── __init__.py                        # NEW: empty package marker + __version__
│   ├── state.py                           # NEW: STATE_DIR, paths, atomic_write, ensure_dir
│   ├── cli.py                             # NEW: argparse entrypoint, `init` and `status` subcommands
│   └── templates/
│       ├── profile.md                     # NEW: user-edited goals/stack template
│       ├── config.toml                    # NEW: cron times, model choices, delivery flags
│       └── repos.toml                     # NEW: list of repos for Historian to scan
└── tests/
    ├── __init__.py                        # NEW: empty
    ├── conftest.py                        # NEW: pytest fixture isolating COACH_STATE_DIR
    └── coach/
        ├── __init__.py                    # NEW: empty
        ├── test_state.py                  # NEW: tests state.py
        └── test_cli.py                    # NEW: tests cli.py end-to-end
```

**Responsibilities:**
- `state.py` — single source of truth for "where is each file." No business logic.
- `cli.py` — argparse dispatch only. Subcommand handlers call into `state.py`.
- `templates/*` — static text files copied verbatim on init. Editable without touching code.
- `tests/conftest.py` — overrides `COACH_STATE_DIR` to a `tmp_path` so tests never touch real `~/agentstate/`.

---

## Task 1: Add pytest, create package skeleton

**Files:**
- Modify: `AgentConfig/requirements.txt`
- Create: `AgentConfig/coach/__init__.py`
- Create: `AgentConfig/coach/templates/` (directory, will hold files in Task 3)
- Create: `AgentConfig/tests/__init__.py`
- Create: `AgentConfig/tests/coach/__init__.py`

- [ ] **Step 1: Append pytest to requirements.txt**

Edit `AgentConfig/requirements.txt`, append:

```
pytest>=8.0.0
```

- [ ] **Step 2: Install pytest into the venv**

Run:

```bash
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/pip install pytest
```

Expected: `Successfully installed pytest-X.Y.Z` (plus iniconfig, packaging, pluggy).

- [ ] **Step 3: Create the package skeleton**

Create `AgentConfig/coach/__init__.py` with:

```python
"""Engineering Coach System — see docs/superpowers/specs/2026-05-13-engineering-coach-system-design.md"""

__version__ = "0.1.0"
```

Create `AgentConfig/tests/__init__.py` and `AgentConfig/tests/coach/__init__.py` as empty files.

Create the directory `AgentConfig/coach/templates/` (no file inside yet — Task 3 fills it).

- [ ] **Step 4: Verify pytest discovers an empty test suite**

Run from `AgentConfig/`:

```bash
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m pytest tests/ -v
```

Expected: `no tests ran in X.XXs` (zero collected, zero errors).

- [ ] **Step 5: Commit**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent
git add AgentConfig/requirements.txt AgentConfig/coach/__init__.py AgentConfig/tests/__init__.py AgentConfig/tests/coach/__init__.py
git commit -m "$(cat <<'EOF'
feat(coach): add coach package skeleton + pytest

First slice of the Engineering Coach System spec — empty package
plus test scaffolding so subsequent tasks can be added TDD-style.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: state.py — paths and atomic writes (TDD)

**Files:**
- Create: `AgentConfig/coach/state.py`
- Create: `AgentConfig/tests/conftest.py`
- Create: `AgentConfig/tests/coach/test_state.py`

The state module owns *every* filesystem path in the system. Centralizing paths here means later agents (Scout, Coach, Critic, Historian) all import from one place — no path strings duplicated across files.

- [ ] **Step 1: Write the conftest fixture**

Create `AgentConfig/tests/conftest.py`:

```python
import os
import pytest

@pytest.fixture
def isolated_state_dir(tmp_path, monkeypatch):
    """Point COACH_STATE_DIR at an isolated temp dir for the test."""
    state_dir = tmp_path / "agentstate"
    monkeypatch.setenv("COACH_STATE_DIR", str(state_dir))
    return state_dir
```

- [ ] **Step 2: Write the failing tests**

Create `AgentConfig/tests/coach/test_state.py`:

```python
import os
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
```

- [ ] **Step 3: Run tests, confirm failure**

Run from `AgentConfig/`:

```bash
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m pytest tests/coach/test_state.py -v
```

Expected: `ImportError` or `ModuleNotFoundError: No module named 'coach.state'` — every test errors out at collection.

- [ ] **Step 4: Write the minimal implementation**

Create `AgentConfig/coach/state.py`:

```python
"""Filesystem paths and atomic writes for the Coach system state directory.

All other coach modules import from here — no path strings should
be duplicated across the codebase.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path


def state_dir() -> Path:
    """Return the active state directory.

    Honors COACH_STATE_DIR if set (used by tests); otherwise
    ~/agentstate.
    """
    override = os.environ.get("COACH_STATE_DIR")
    if override:
        return Path(override)
    return Path.home() / "agentstate"


def profile_path() -> Path:
    return state_dir() / "profile.md"


def config_path() -> Path:
    return state_dir() / "config.toml"


def repos_path() -> Path:
    return state_dir() / "repos.toml"


def signals_path() -> Path:
    return state_dir() / "signals.md"


def today_path() -> Path:
    return state_dir() / "today.md"


def critique_log_path() -> Path:
    return state_dir() / "critique_log.md"


def derived_state_path() -> Path:
    return state_dir() / "derived_state.md"


def drift_path() -> Path:
    return state_dir() / "drift.md"


def lessons_path() -> Path:
    return state_dir() / "lessons.md"


def ensure_dir() -> None:
    """Create the full state directory layout. Idempotent."""
    root = state_dir()
    (root / "archive" / "signals").mkdir(parents=True, exist_ok=True)
    (root / "archive" / "today").mkdir(parents=True, exist_ok=True)
    (root / "solutions").mkdir(parents=True, exist_ok=True)


def atomic_write(target: Path, content: str) -> None:
    """Write content to target atomically (write-temp + os.replace).

    Ensures that readers never see a partially-written file.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(content)
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()
```

- [ ] **Step 5: Run tests, confirm pass**

Run from `AgentConfig/`:

```bash
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m pytest tests/coach/test_state.py -v
```

Expected: `8 passed in X.XXs`.

- [ ] **Step 6: Commit**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent
git add AgentConfig/coach/state.py AgentConfig/tests/conftest.py AgentConfig/tests/coach/test_state.py
git commit -m "$(cat <<'EOF'
feat(coach): add state module with paths and atomic writes

state.py owns every filesystem path used by the coach system.
ensure_dir() creates the full ~/agentstate layout; atomic_write()
guarantees readers never see partial files. COACH_STATE_DIR
override lets tests run in tmp dirs without polluting $HOME.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Template files for `coach init`

**Files:**
- Create: `AgentConfig/coach/templates/profile.md`
- Create: `AgentConfig/coach/templates/config.toml`
- Create: `AgentConfig/coach/templates/repos.toml`

Templates are plain text files copied verbatim during `coach init`. Putting them on disk (not in a Python string) means you can iterate on the wording without touching code.

- [ ] **Step 1: Write `profile.md` template**

Create `AgentConfig/coach/templates/profile.md`:

```markdown
# Engineering Profile

> Edit this file to set the direction for the coach system.
> The Coach, Scout, and Critic all read this as gospel for what
> "better engineer" means for you. Update it whenever your goals shift.

## Who I am
<!-- e.g., "CS student, security + agents track" -->

## Target role (18 months out)
<!-- e.g., "Security engineer at a top-tier company" -->

## Current stack
<!-- languages, frameworks, currently learning -->

## Active projects
- <!-- name + one-line description -->

## Focus areas this quarter
1. <!-- area + why -->
2.
3.

## Things I want the Critic calibrating to
<!-- e.g., "Senior engineer at a top-tier company. Don't be gentle.
     Name blind spots specifically. Reference the better pattern." -->
```

- [ ] **Step 2: Write `config.toml` template**

Create `AgentConfig/coach/templates/config.toml`:

```toml
# Coach system configuration.
# Edit values, but keep the schema — agents read these by key name.

[models]
scout     = "claude-sonnet-4-6"
coach     = "claude-opus-4-7"
critic    = "claude-opus-4-7"
historian = "claude-sonnet-4-6"

[schedule]
scout             = "0 6 * * *"
coach             = "0 7 * * *"
historian_nightly = "0 23 * * *"
historian_weekly  = "30 22 * * 0"
critic_weekly     = "0 22 * * 0"

[delivery]
shell_greeting = true   # cat today.md on new terminal session
slack          = false  # v2 — Composio Slack DM
email          = false  # v2 — Composio Gmail

[critic]
calibration_target  = "senior engineer at a top-tier company"
post_commit_enabled = true
```

- [ ] **Step 3: Write `repos.toml` template**

Create `AgentConfig/coach/templates/repos.toml`:

```toml
# Repos for the Historian to scan nightly.
# Add one [[repo]] block per repo you want tracked.

[[repo]]
path      = "/Users/iibrahimsv/PycharmProjects/ComposioAgent"
nickname  = "ComposioAgent"
languages = ["python"]

# Example second entry — uncomment and edit:
# [[repo]]
# path      = "/Users/iibrahimsv/code/cs-coursework"
# nickname  = "Coursework"
# languages = ["java"]
```

- [ ] **Step 4: Commit (no tests yet — these are static assets)**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent
git add AgentConfig/coach/templates/profile.md AgentConfig/coach/templates/config.toml AgentConfig/coach/templates/repos.toml
git commit -m "$(cat <<'EOF'
feat(coach): add init templates for profile, config, repos

Static templates copied into ~/agentstate by `coach init`.
Kept as plain files (not Python strings) so prompt/config
wording can be tuned without code changes.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `coach init` and `coach status` CLI (TDD)

**Files:**
- Create: `AgentConfig/coach/cli.py`
- Create: `AgentConfig/tests/coach/test_cli.py`

The CLI is the only entry point — every cron job and the git hook will eventually call `python -m coach.cli ...`. For now, just two subcommands: `init` (write templates) and `status` (show what's in state dir).

- [ ] **Step 1: Write the failing CLI tests**

Create `AgentConfig/tests/coach/test_cli.py`:

```python
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
```

- [ ] **Step 2: Run tests, confirm failure**

Run from `AgentConfig/`:

```bash
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m pytest tests/coach/test_cli.py -v
```

Expected: `ModuleNotFoundError: No module named 'coach.cli'` — every test errors at collection.

- [ ] **Step 3: Write the CLI implementation**

Create `AgentConfig/coach/cli.py`:

```python
"""Command-line interface for the coach system.

Subcommands:
  init    — create ~/agentstate and write template files
  status  — show which state files are present
"""

from __future__ import annotations

import argparse
import sys
from importlib import resources
from pathlib import Path

from coach import state

TEMPLATES = ("profile.md", "config.toml", "repos.toml")


def _template_text(name: str) -> str:
    """Read a template file shipped with the package."""
    return resources.files("coach.templates").joinpath(name).read_text()


def _target_for_template(name: str) -> Path:
    mapping = {
        "profile.md": state.profile_path(),
        "config.toml": state.config_path(),
        "repos.toml": state.repos_path(),
    }
    return mapping[name]


def cmd_init(args: argparse.Namespace) -> int:
    state.ensure_dir()
    for name in TEMPLATES:
        target = _target_for_template(name)
        if target.exists() and not args.force:
            print(f"skip  {target}  (already exists; use --force to overwrite)")
            continue
        state.atomic_write(target, _template_text(name))
        print(f"write {target}")
    print(f"\nstate dir ready at {state.state_dir()}")
    print("next: edit profile.md to set your direction.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = state.state_dir()
    if not root.exists():
        print(f"state dir not initialized at {root}")
        print("run: coach init")
        return 0
    print(f"state dir: {root}")
    checks = [
        ("profile.md",        state.profile_path()),
        ("config.toml",       state.config_path()),
        ("repos.toml",        state.repos_path()),
        ("signals.md",        state.signals_path()),
        ("today.md",          state.today_path()),
        ("derived_state.md",  state.derived_state_path()),
        ("drift.md",          state.drift_path()),
        ("lessons.md",        state.lessons_path()),
        ("critique_log.md",   state.critique_log_path()),
    ]
    for label, path in checks:
        status = "present" if path.exists() else "missing"
        print(f"  {label:<18} {status}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coach",
        description="Engineering Coach System CLI.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="initialize ~/agentstate with templates")
    p_init.add_argument("--force", action="store_true",
                        help="overwrite existing template files")
    p_init.set_defaults(func=cmd_init)

    p_status = sub.add_parser("status", help="show which state files are present")
    p_status.set_defaults(func=cmd_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Make templates importable via `importlib.resources`**

The CLI uses `resources.files("coach.templates")` to find template content. For that to work, `coach/templates/` needs an `__init__.py`.

Create `AgentConfig/coach/templates/__init__.py` as an empty file.

- [ ] **Step 5: Run tests, confirm pass**

Run from `AgentConfig/`:

```bash
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m pytest tests/coach/test_cli.py -v
```

Expected: `7 passed in X.XXs`.

- [ ] **Step 6: Manual smoke test against a tmp dir**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig
COACH_STATE_DIR=/tmp/coach-smoke /Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m coach.cli init
COACH_STATE_DIR=/tmp/coach-smoke /Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m coach.cli status
ls -la /tmp/coach-smoke
rm -rf /tmp/coach-smoke
```

Expected output: `init` writes three files + reports paths; `status` shows three `present`, six `missing`; `ls` confirms `profile.md`, `config.toml`, `repos.toml`, plus the `archive/` and `solutions/` subdirectories.

- [ ] **Step 7: Commit**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent
git add AgentConfig/coach/cli.py AgentConfig/coach/templates/__init__.py AgentConfig/tests/coach/test_cli.py
git commit -m "$(cat <<'EOF'
feat(coach): add init and status CLI subcommands

`coach init` writes profile.md, config.toml, repos.toml templates
into ~/agentstate (or COACH_STATE_DIR). `coach status` reports
which state files are present. Both are TDD-covered; --force flag
on init enables intentional overwrite. argparse, stdlib only.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Run full suite + user-side init

**Files:** none modified — verification and user-facing handoff.

- [ ] **Step 1: Run the full test suite**

Run from `AgentConfig/`:

```bash
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m pytest tests/ -v
```

Expected: `15 passed in X.XXs` (8 from test_state + 7 from test_cli).

- [ ] **Step 2: Verify no stray temp files in repo**

Run from repo root:

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent
find AgentConfig -name "*.tmp" -o -name "__pycache__"
```

Expected: only `__pycache__` directories (those are gitignored). No `.tmp` files.

- [ ] **Step 3: Run `coach init` against the real `~/agentstate/`**

```bash
cd /Users/iibrahimsv/PycharmProjects/ComposioAgent/AgentConfig
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m coach.cli init
/Users/iibrahimsv/PycharmProjects/ComposioAgent/venv_py311/bin/python -m coach.cli status
```

Expected: `~/agentstate/` exists with `profile.md`, `config.toml`, `repos.toml`. `status` reports those three present and the rest (signals, today, etc.) missing — which is correct, no agents have run yet.

- [ ] **Step 4: Open `~/agentstate/profile.md` and fill it out**

This is a manual step. Replace the `<!-- … -->` placeholders with real content. The Coach quality is bounded by what's in this file — be specific. Examples:

- Target role: "Security engineer at FAANG within 18 months."
- Focus areas this quarter: "Agent architectures", "OWASP top 10", "Systems literacy (1 read/week)"
- Calibration: "Senior eng at top-tier. Don't be gentle."

(Do NOT commit this file — it's outside the repo and personal.)

- [ ] **Step 5: Final commit — none required**

Step 1 ships. The plan ends here. The next plan ("Step 2: Historian nightly") will be written separately and depend only on what this plan produced.

---

## What's NOT in this plan

These are deliberately deferred to subsequent plans (matching spec §6 build order):

- **Step 2** — Historian nightly: git walker + `derived_state.md` writer
- **Step 3** — Coach v0: reads `profile.md` + `derived_state.md`, writes `today.md` (no Scout yet)
- **Step 4** — Scout: web search + HN + ArXiv → `signals.md`
- **Step 5** — Critic post-commit: git hook + per-commit review
- **Step 6** — Historian weekly + Critic weekly trend
- **Step 7** — Delivery polish (Slack via Composio)

Each becomes its own plan. The compounding property holds: after this plan, `coach init`/`status` is a working tool that lets the user write their profile. After plan 2, the Historian gives nightly `derived_state.md`. After plan 3, daily `today.md` exists. And so on.
