# Critic v0 — Design

**Date:** 2026-06-08
**Status:** Approved (design); implementation plan to follow.
**Spec author:** brainstormed with the user, 2026-06-08.

## 1. Purpose

Critic v0 is the first *judging* agent in the Polaris Engineering Coach System. It
reads the latest commit of one repo plus the user's `profile.md`, and writes a
calibrated, senior-engineer code review to `~/agentstate/critique_log.md`.

This is deliberately the **smallest thing that produces a real critique on disk**.
`profile.md` Focus Area 1 is explicit: *"One agent (the Critic) working against one
real repo with a hardcoded profile. Ugly is fine. Orchestration and the other agents
come after something runs."* v0 honors that — it is a single, manually-invoked,
single-API-call agent. The git post-commit hook, weekly trend review, multi-repo
support, and tool-use context are all later steps (see §9 Out of Scope).

Relationship to the full spec: this jumps the design spec's build order (Historian →
Coach v0 → Scout → **Critic**) to ship the Critic next, per the profile's
ship-first directive. It implements a reduced form of the Critic described in
§3.3 of `docs/superpowers/specs/2026-05-13-engineering-coach-system-design.md`.

## 2. Locked decisions

| Decision | Value | Rationale |
|---|---|---|
| Review unit | Latest commit diff (`git diff HEAD~1..HEAD`) | Most concrete unit; the Critic names files/functions in one changeset. Closest to the spec's per-commit Critic. |
| Repo source | `repos[0]` from `repos.toml` | Reuses the existing `repos.load_repos()` loader; no new config. `repos[0]` is Polaris itself. |
| Architecture | Single-shot, diff-in-prompt, **no tools** | Smallest deterministic path. Tool-use (the spec's eventual Critic) is "scaffolding-forever" bait the profile warns against; deferred to a later step. |
| Model | `claude-opus-4-8`, adaptive thinking, `effort: "high"` | Current most-capable model; senior code review is its strength. Upgrades the spec's `claude-opus-4-7`. Same request surface. |
| Prompt caching | **Skipped in v0** | The profile-only prefix (~1.2K tokens) is below Opus 4.8's 4096-token minimum cacheable prefix — it would silently not cache. Revisit when `profile.md` + `lessons.md` + diff clear the floor. |
| Output format | Free-form markdown: `★ Good / ✗ Blind spot / ↗ Stretch` | Matches the spec's literal output format; no JSON-schema plumbing in v0. |
| Output file | `~/agentstate/critique_log.md`, append-only | Per the spec's state-directory contract. `state.critique_log_path()` already exists. |
| Frontmatter | Document-level, written once at file creation | The append-only log gets one frontmatter block at the top, not per-entry. See §5. |
| Idempotency | None in v0 — append every run | Re-running on the same commit appends a duplicate entry. Skip-if-already-reviewed is deferred to when the post-commit hook lands. |
| Invocation | `coach critic run` (+ `--dry-run`) | Mirrors the existing `coach historian nightly` CLI pattern. |

## 3. File-level changes

```
AgentConfig/coach/
  critic.py          NEW   — the agent: collect → prompt → call → render → append
  git_stats.py       EDIT  — add commit_diff() + head_commit_info()
  cli.py             EDIT  — add `coach critic run [--dry-run]` subcommand
  scripts/smoke.sh   EDIT  — add a `critic --dry-run` health check (spends no tokens)
tests/coach/
  test_critic.py     NEW   — TDD the units (all offline; Anthropic call injected)
  test_git_stats.py  EDIT  — cover commit_diff + head_commit_info
```

Reused unchanged: `state.critique_log_path()`, `state.profile_path()`,
`repos.load_repos()` / `RepoEntry`, and the `make_repo` test fixture.

## 4. Data flow

```
repos[0] ──► git_stats.commit_diff()    ──┐
            git_stats.head_commit_info() ──┤─► critic.collect_review_input() ─► ReviewInput
profile.md (state.profile_path) ──────────┘                                        │
                                                                                   ▼
                                          critic.build_prompt(ReviewInput) ─► (system, user)
                                                                                   │
                                          critic.request_critique(system, user) ───┤  (Anthropic call, injectable)
                                                                                   ▼
                                          critic.render_entry(r, body, now) ─► dated ★/✗/↗ section
                                                                                   ▼
                                          critic.append_entry(text) ─► critique_log.md
```

## 5. Module design

### 5.1 `git_stats.py` additions

- `commit_diff(repo: Path, rev_range: str = "HEAD~1..HEAD") -> str`
  Returns the unified diff text for the range. If `HEAD~1` does not exist
  (repo has a single commit), falls back to diffing against the git empty-tree
  hash so a one-commit repo still produces a reviewable diff.
- `head_commit_info(repo: Path) -> CommitInfo`
  A small dataclass (or named tuple) carrying `sha_short` and `subject` for the
  entry header.

These follow the existing `_run_git` helper pattern already in `git_stats.py`.

### 5.2 `critic.py`

- `@dataclass(frozen=True) ReviewInput`
  Fields: `repo_nickname: str`, `sha: str`, `subject: str`, `diff: str`,
  `profile_text: str`.

- `collect_review_input(repo: RepoEntry) -> ReviewInput`
  Assembles a `ReviewInput` from the repo (via `git_stats`) and `profile.md`
  (via `state.profile_path()`). No side effects beyond git reads + file read.

- `build_prompt(r: ReviewInput) -> tuple[str, str]`
  Returns `(system, user)`.
  - **system** — the Critic persona: a senior AI/agent engineer at a FAANG-tier
    company reviewing a new-grad candidate; calibrate strictly to the user's
    `profile.md`; emit exactly the three labels `★ Good`, `✗ Blind spot`,
    `↗ Stretch`; **report everything found, do not self-filter to "high
    severity"** (Opus 4.8 follows conservative-filter instructions literally and
    will silently drop findings otherwise).
  - **user** — `profile_text`, the commit metadata (`sha`, `subject`,
    `repo_nickname`), and the `diff`.

- `request_critique(system: str, user: str, *, client=None) -> str`
  The single Anthropic call. Uses `anthropic.Anthropic()` by default; `client`
  is injectable so tests never hit the network. Call shape:
  `messages.create(model="claude-opus-4-8", max_tokens≈4000,
  thinking={"type": "adaptive"}, output_config={"effort": "high"},
  system=system, messages=[{"role": "user", "content": user}])`. Returns the
  concatenated text-block content. Non-streaming (output is short, well under the
  ~16K streaming threshold).

- `render_entry(r: ReviewInput, body: str, now: datetime) -> str`
  Formats one dated section:
  `## 2026-06-08 14:32 — c1cf608 (Polaris)\n\n<body>\n`.

- `append_entry(text: str) -> Path`
  Appends `text` to `critique_log.md`. If the file does not yet exist, writes the
  document-level frontmatter block (below) first, then the entry. Returns the path.

- `run(repo: RepoEntry | None = None, now: datetime | None = None,
       client=None, dry_run: bool = False) -> Path`
  Orchestrates the flow. `repo` defaults to `load_repos()[0]`; `now` defaults to
  `datetime.now(timezone.utc)`. When `dry_run=True`, performs everything except
  the API call and the append — assembles and returns/prints the prompt — so the
  daily smoke suite can exercise the agent without spending tokens.

### 5.3 Frontmatter contract (document-level)

Written **once**, at file creation:

```yaml
---
source_agent: critic
schema_version: 1
created_at: <ISO8601>
---
```

**Deliberate deviation from the Historian contract:** agent-written *overwrite*
files (`derived_state.md`) carry `generated_at` + `inputs_hash` so downstream
readers can short-circuit "same world observed." `critique_log.md` is
**append-only**, so a whole-file hash is meaningless and per-entry frontmatter was
explicitly rejected during design. The log therefore omits `inputs_hash`. This
divergence is intentional and recorded here so it is not mistaken for an oversight.

## 6. Error handling (v0, pragmatic)

| Condition | Behavior |
|---|---|
| `repos.toml` empty / missing | Clear error: "no repos configured — run `coach init`." Exit non-zero. |
| `HEAD~1` does not exist (first commit) | `commit_diff` falls back to the git empty-tree hash; the single commit still reviews. |
| Empty diff (e.g. merge commit) | Skip the API call; append a "nothing to review" note for that commit. |
| `ANTHROPIC_API_KEY` unset | Clear error before any work begins. |
| API 429 / 5xx | SDK auto-retries with backoff (`max_retries=2`). On hard failure, surface the error. Rendering happens before append, so no half-written entry is left behind. |

## 7. Testing plan (TDD)

All tests run offline; the Anthropic call is injected via the `client` parameter.

1. `git_stats.commit_diff` / `head_commit_info` against a `make_repo` fixture
   (including the single-commit empty-tree fallback).
2. `collect_review_input` assembles all five `ReviewInput` fields, with
   `COACH_STATE_DIR` pointed at a temp profile.
3. `build_prompt` includes the profile text and the diff, and instructs the model
   to emit the three labels and report everything.
4. `render_entry` produces the exact dated header format.
5. `append_entry` writes frontmatter on first call and appends **without** a
   second frontmatter block on the next call.
6. `run(client=FakeClient(...))` end-to-end writes a complete entry with no network
   access; `run(dry_run=True)` writes nothing and makes no call.

## 8. Smoke-suite integration

`AgentConfig/coach/scripts/smoke.sh` gains one line:

```
run_check critic "$PY" -m coach.cli critic run --dry-run
```

`--dry-run` exercises repo loading + prompt assembly in the daily smoke run
**without spending tokens**. Only an explicit `coach critic run` makes a paid API
call. This keeps the daily health check free.

## 9. Out of scope (deliberate v0 cuts)

These are the design spec's later Critic steps; none belong in v0:

- Git **post-commit hook** (per-commit auto-review) and the cron **weekly trend review**.
- **Multi-repo** loop (v0 reviews `repos[0]` only).
- **Tool-use / agentic context** (Approach B — giving the Critic `bash git` + file
  read to pull surrounding code). This is the spec's eventual Critic and the natural
  graduation once per-commit review exposes the missing-context pain.
- **Prompt caching** (proposal #1) — deferred until the prefix clears Opus 4.8's
  4096-token floor.
- **Skip-if-already-reviewed** idempotency — deferred to the post-commit hook.
- **promptfoo eval suite** (proposal #3) — ships *after* Critic v0 hits HEAD;
  `profile.md` Focus Area 2 already promises 20 hand-labeled
  `(repo state, profile) → expected critique` pairs.

## 10. Success criteria

v0 is done when:

- `coach critic run` produces a valid, dated, frontmatter-stamped entry in
  `~/agentstate/critique_log.md` that uses the `★ / ✗ / ↗` labels and references
  the actual diff (names a specific file or function from the changeset).
- The critique visibly reflects `profile.md` calibration (e.g. flags
  resume-driven architecture or scaffolding-forever when warranted).
- `coach critic run --dry-run` runs offline and is wired into `smoke.sh`.
- The full test suite is green, with the Anthropic call mocked.
