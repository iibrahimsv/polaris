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
