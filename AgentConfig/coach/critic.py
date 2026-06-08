"""Critic v0 — single-shot, calibrated code review of the latest commit.

Collects `git diff HEAD~1..HEAD` of repos[0] plus profile.md, asks
claude-opus-4-8 for a senior-engineer critique using the ★ / ✗ / ↗ labels,
and appends a dated entry to ~/agentstate/critique_log.md.

The Anthropic call is isolated in request_critique() and injectable via the
`client` parameter, so the rest of the pipeline is testable offline.

Design: docs/superpowers/specs/2026-06-08-critic-v0-design.md
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from coach import git_stats, state
from coach.repos import RepoEntry, load_repos

MODEL = "claude-opus-4-8"
MAX_TOKENS = 4000
SCHEMA_VERSION = 1
SOURCE_AGENT = "critic"

SYSTEM_PROMPT = """\
You are a senior AI/agent engineer at a FAANG-tier company, reviewing a \
new-grad candidate's commit. Your job is an honest, calibrated code review.

Calibrate strictly to the engineering profile the user provides — their target \
role, current stack, and especially the explicit "what I want the Critic \
calibrating to" section. Don't be gentle. Be specific. Name the blind spot, \
then name the better pattern: "you're doing X; the idiomatic move is Y because Z."

Report every finding — do NOT self-filter to only high-severity issues. It is \
better to surface a finding that gets dismissed than to silently drop a real one.

Push back on resume-driven architecture, scaffolding-forever syndrome, and work \
that is "started" but not shipped or measured. Hold the work to the profile's bar.

Structure the review as markdown using exactly these three labels, each as one \
or more bullets, as many of each as warranted:
- ★ Good — what is genuinely well done
- ✗ Blind spot — a concrete problem plus the better pattern
- ↗ Stretch — a more advanced direction that would level this up

Reference specific files, functions, or lines from the diff. Be concise.
"""


@dataclass(frozen=True)
class ReviewInput:
    repo_nickname: str
    sha: str
    subject: str
    diff: str
    profile_text: str


def collect_review_input(repo: RepoEntry) -> ReviewInput:
    """Assemble a ReviewInput from one repo's latest commit + profile.md."""
    info = git_stats.head_commit_info(repo.path)
    diff = git_stats.commit_diff(repo.path)
    profile_text = state.profile_path().read_text()
    return ReviewInput(
        repo_nickname=repo.nickname,
        sha=info.sha_short,
        subject=info.subject,
        diff=diff,
        profile_text=profile_text,
    )


def build_prompt(r: ReviewInput) -> tuple[str, str]:
    """Return (system, user) prompt strings for the critique request."""
    user = (
        "# Engineering profile (calibrate your review to this)\n\n"
        f"{r.profile_text}\n\n"
        "# Commit under review\n\n"
        f"- repo: {r.repo_nickname}\n"
        f"- commit: {r.sha}\n"
        f"- subject: {r.subject}\n\n"
        "# Diff (git diff HEAD~1..HEAD)\n\n"
        "```diff\n"
        f"{r.diff}\n"
        "```\n"
    )
    return SYSTEM_PROMPT, user


def request_critique(system: str, user: str, *, client=None) -> str:
    """Make the single Anthropic call and return the critique markdown.

    `client` is injectable so tests never hit the network. Newer request
    fields (adaptive thinking, effort) are passed via extra_body to stay
    compatible across anthropic SDK versions.
    """
    if client is None:
        import anthropic

        client = anthropic.Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
        extra_body={
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "high"},
        },
    )
    return "".join(
        block.text
        for block in resp.content
        if getattr(block, "type", None) == "text"
    ).strip()


def _frontmatter(now: datetime) -> str:
    created = now.astimezone(timezone.utc).isoformat()
    return (
        "---\n"
        f"source_agent: {SOURCE_AGENT}\n"
        f"schema_version: {SCHEMA_VERSION}\n"
        f"created_at: {created}\n"
        "---\n"
    )


def render_entry(r: ReviewInput, body: str, now: datetime) -> str:
    """Format one dated critique section for the append-only log."""
    stamp = now.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    label = r.sha or "(unknown)"
    return f"\n## {stamp} — {label} ({r.repo_nickname})\n\n{body}\n"


def append_entry(text: str, now: datetime | None = None) -> Path:
    """Append `text` to critique_log.md, writing frontmatter if the file is new."""
    if now is None:
        now = datetime.now(timezone.utc)
    target = state.critique_log_path()
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_frontmatter(now))
    with target.open("a") as fh:
        fh.write(text)
    return target


def run(
    repo: RepoEntry | None = None,
    now: datetime | None = None,
    client=None,
    dry_run: bool = False,
) -> Path:
    """Entrypoint for `coach critic run`.

    Reviews repos[0]'s latest commit and appends a critique to
    critique_log.md. `dry_run` assembles the prompt without calling the API
    or writing the log — used by the daily smoke suite to stay token-free.
    Returns the critique_log path.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if repo is None:
        entries = load_repos()
        if not entries:
            raise SystemExit(
                "no repos configured — run: python -m coach.cli init"
            )
        repo = entries[0]

    r = collect_review_input(repo)
    system, user = build_prompt(r)

    if dry_run:
        print(
            f"[dry-run] critic ready: {repo.nickname} @ "
            f"{r.sha or '(no commit)'} — diff {len(r.diff)} chars, "
            f"prompt {len(system) + len(user)} chars"
        )
        return state.critique_log_path()

    if not r.diff.strip():
        body = "_No changes in this commit — nothing to review._"
    else:
        body = request_critique(system, user, client=client)

    entry = render_entry(r, body, now)
    return append_entry(entry, now=now)
