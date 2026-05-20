"""Historian — nightly activity snapshot writer.

Walks every repo in ~/agentstate/repos.toml, gathers stats via
coach.git_stats, builds a Snapshot dataclass, renders it to markdown
(with a machine-readable YAML frontmatter block), and atomically writes
~/agentstate/derived_state.md.

Pure pipeline. No LLM call in Step 2 — synthesis is deferred.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from coach import git_stats, state
from coach.repos import RepoEntry, load_repos

LINES_PER_HOUR = 60
"""Default conversion factor for diff lines → engineering hours.
60 lines/hour is a defensible industry-average rule of thumb. Override
per-call via collect_snapshot(..., lines_per_hour=X)."""

SCHEMA_VERSION = 1
SOURCE_AGENT = "historian"


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


def _compute_inputs_hash(snap: Snapshot) -> str:
    """SHA256 over the observable snapshot fields, excluding generated_at.

    Lets downstream readers detect "the Historian saw the same world" so
    LLM-driven consumers can short-circuit when inputs haven't changed.
    """
    payload = {
        "repos": [
            {
                "nickname": r.nickname,
                "path": str(r.path),
                "last_commit": r.last_commit.isoformat() if r.last_commit else "",
                "commits_24h": r.commits_24h,
                "commits_7d": r.commits_7d,
                "diff_total_7d": r.diff_total_7d,
                "languages": list(r.languages),
            }
            for r in snap.repos
        ],
        "hours_by_stack": snap.hours_by_stack,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _render_frontmatter(snap: Snapshot) -> str:
    gen = snap.generated_at.astimezone(timezone.utc).isoformat()
    return (
        "---\n"
        f"generated_at: {gen}\n"
        f"source_agent: {SOURCE_AGENT}\n"
        f"schema_version: {SCHEMA_VERSION}\n"
        f"inputs_hash: {_compute_inputs_hash(snap)}\n"
        "---\n"
    )


def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "(no commits yet)"
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def render_derived_state(snap: Snapshot) -> str:
    """Render a Snapshot to the markdown that lands in derived_state.md.

    Output begins with a YAML frontmatter block (machine-readable) and
    continues with a human-readable body.
    """
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
        return _render_frontmatter(snap) + "\n" + "\n".join(lines)

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

    lines.append("## Language share (last 7 days)")
    lines.append("")
    total_hours = sum(snap.hours_by_stack.values())
    if total_hours <= 0:
        lines.append("- (no activity)")
    else:
        for lang in sorted(snap.hours_by_stack):
            pct = round(100 * snap.hours_by_stack[lang] / total_hours, 1)
            lines.append(f"- **{lang}**: {pct}%")
    lines.append("")

    return _render_frontmatter(snap) + "\n" + "\n".join(lines)


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
