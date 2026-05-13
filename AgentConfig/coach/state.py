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
