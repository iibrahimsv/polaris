"""Command-line interface for the coach system.

Subcommands:
  init    — create ~/agentstate and write template files
  status  — show which state files are present
"""

from __future__ import annotations

import argparse
import sys
from importlib import resources
from typing import Callable
from pathlib import Path

from coach import state

# Single source of truth: template filename → callable returning its destination path.
# Adding a new template means adding one entry here (and a matching file in templates/).
_TEMPLATE_TARGETS: dict[str, Callable[[], Path]] = {
    "profile.md": state.profile_path,
    "config.toml": state.config_path,
    "repos.toml": state.repos_path,
}
TEMPLATES: tuple[str, ...] = tuple(_TEMPLATE_TARGETS.keys())


def _template_text(name: str) -> str:
    """Read a template file shipped with the package."""
    return resources.files("coach.templates").joinpath(name).read_text()


def _target_for_template(name: str) -> Path:
    return _TEMPLATE_TARGETS[name]()


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
    print(f"next: edit {state.profile_path()} to set your direction.")
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
