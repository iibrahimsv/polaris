# Engineering Coach System — Design

**Status:** Approved, ready for implementation planning
**Date:** 2026-05-13
**Owner:** Abdi Ibrahim (`dcabdi@gmail.com`)
**Project:** ComposioAgent (`/Users/iibrahimsv/PycharmProjects/ComposioAgent`)

---

## 1. Why this exists

The original ask was "agents that come up with new ideas each day from the tech market + AI updates." After reframing, the deeper goal is: **use agents to measurably make me a better engineer.** Idea generation alone is a passive content stream — it doesn't compound. The mechanisms that actually move engineering skill are deliberate practice, critique loops, ambition calibration, and compounding lessons.

This system replaces "daily idea engine" with a **personal engineering coach**: a small team of agents that produce a daily artifact tilted toward action (challenge to solve, connection to current work, ambition pointer), plus per-commit critique, plus a weekly review of drift between stated goals and observed work.

## 2. Scope

In scope:

- Four agents running on cron / git-hook schedules: **Scout, Coach, Critic, Historian**
- A shared state directory at `~/agentstate/` that is the contract between agents
- Daily delivery via shell greeting (`.zshrc`) and a `coach` CLI
- Initial sources for Scout: web search, Hacker News API, ArXiv RSS, GitHub trending
- Per-commit code review via git `post-commit` hook
- Weekly drift report (stated goals vs. git activity) and compounding lessons file

Out of scope (deliberately, for compounding rollout):

- Slack/email/SMS delivery (deferred to v2; v1 ships shell + CLI only)
- Web dashboard
- Conversational weekly check-ins (the user model already declined the "interview" option)
- Cross-machine state sync (single-machine for v1)
- Auto-implementation of suggested challenges (the human still does the work)

## 3. Agent designs

All four agents run via the standard **Anthropic Messages API** (not the beta agents endpoint). Each agent is one high-quality completion over state files. Composio tools attach via `tools=` on `messages.create` where needed (Scout only, for now). System prompts live in `.md` files under `coach/prompts/` so prompt tuning needs no code changes.

### 3.1 Scout — daily signal scanner

| Attribute | Value |
|---|---|
| Model | `claude-sonnet-4-6` |
| Schedule | Cron, 06:00 daily |
| Inputs | `profile.md`, `derived_state.md`, last 3 days of archived `signals.md` |
| Outputs | `~/agentstate/signals.md` (today, overwrites prior) + `~/agentstate/archive/signals/YYYY-MM-DD.md` (rotated copy of prior day) |
| Tools | Web search (Anthropic native), HN Algolia API, ArXiv RSS, GitHub trending (scraped), optional Composio Twitter/X |
| Job | Scan world state. Filter to what matches user's stack + goals. Score relevance 0–10. Group by category (AI/Agents, Security, Your stack). |

**Output format:**

```markdown
# Signals — 2026-05-13

## AI / Agents
- [9.2] Anthropic shipped MCP 1.2 with stdio transport
        link: https://...
        why-relevant: you're building agent infra; MCP is core
- [7.5] LangGraph 0.3 added persistent state checkpoints

## Security
- [8.1] CVE-2026-12345 in popular Python supply-chain tool

## Your stack
- [8.7] Composio shipped Webhooks v2 — maps to step 5 of your arch plan
```

### 3.2 Coach — the daily artifact maker

| Attribute | Value |
|---|---|
| Model | `claude-opus-4-7` |
| Schedule | Cron, 07:00 daily (runs after Scout) |
| Inputs | `profile.md`, `derived_state.md`, `drift.md`, `signals.md`, `lessons.md`, last 7 days of archived `today.md` |
| Outputs | `~/agentstate/today.md` + `~/agentstate/solutions/YYYY-MM-DD.md` (reference solution for today's challenge) |
| Tools | None — pure reasoning over state files |
| Job | Synthesize a daily artifact tilted toward action. Three required sections: (1) Challenge — a 45-min deliberate-practice problem with a hidden reference solution, (2) Connection — today's news tied to user's current project, (3) Ambition pointer — read/build/pattern from one tier above the user's level. Optionally append a Drift watch section when `drift.md` shows a meaningful gap. |

**Output format:**

```markdown
# 2026-05-13 — Daily

## Challenge (45 min, deliberate practice)
Implement a stdio-transport MCP server that exposes ONE tool that
returns current time. No SDK — just JSON-RPC over stdin/stdout.
Why this: you've been API-side. You need the server side of the
protocol to ship Composio-style integrations.
Reference solution: ~/agentstate/solutions/2026-05-13.md
(do NOT read until you finish or get stuck > 25 min)

## Connection (today's news × your stack)
Composio webhooks v2 maps directly to step 5 of your arch plan
(reactive triggers). ComposioAgent could get on_pr_assigned in
~80 lines today.

## Ambition pointer
"Building a $0.001 LLM gateway" — Cloudflare eng blog, 12 min.
Stretches you on tail-latency budgeting + request hedging
(neither of which your code touches yet).

## Drift watch
You said security matters. Last 7 days: 0 hrs security-adjacent.
Today's challenge counts. Tomorrow leans security.
```

### 3.3 Critic — review what shipped

| Attribute | Value |
|---|---|
| Model | `claude-opus-4-7` |
| Triggers | Git `post-commit` hook (per-commit review) + cron Sunday 22:00 (weekly trend review) |
| Inputs | `git diff HEAD~1..HEAD` (per-commit) or `git log + diffs` for last 7 days (weekly), `profile.md` (calibrate critique to user's target level) |
| Outputs | `~/agentstate/critique_log.md` (append-only, dated entries) |
| Tools | Bash (`git`), file reading |
| Job | Senior-engineer code review against the user's stated target level (e.g., "senior eng at top company"). Name blind spots concretely. Three labels: `★ Good`, `✗ Blind spot`, `↗ Stretch`. |

**Output format (per entry):**

```markdown
## 2026-05-13 14:32 — commit a1b2c3d (ComposioAgent)
file: enhanced_agent_runner.py

★ Good: caching env_id + agent_id avoids redundant API calls.
✗ Blind spot: `_environment_cache` is instance state but runner
  is instantiated fresh per test → cache is dead. Persist to
  ~/agentstate or hoist module-level.
✗ Blind spot: bare `except Exception` swallows typed Anthropic
  errors. Distinguish RateLimitError (retry) from AuthError
  (fail fast).
↗ Stretch: no timing breakdown. perf_counter around API calls,
  log to derived_state for Historian.
```

### 3.4 Historian — long-arc keeper

| Attribute | Value |
|---|---|
| Model | `claude-sonnet-4-6` |
| Schedule | Cron, 23:00 nightly (derived state) + Sunday 22:30 weekly synthesis |
| Inputs (nightly) | All git repos listed in `repos.toml`, `profile.md` |
| Inputs (weekly) | Nightly derived state for last 7 days, `today.md` archive, `critique_log.md`, `profile.md` |
| Outputs | `derived_state.md` (nightly overwrite), `drift.md` (weekly append), `lessons.md` (weekly append) |
| Tools | Bash (git log, git diff --stat, ls), file r/w |
| Job — nightly | Walk every repo in `repos.toml`. Compute: language %, active repos last 24h/7d, last commit timestamp per repo, total commits last 7d, estimated hours-by-stack from diff sizes. Write to `derived_state.md`. |
| Job — weekly | Read `profile.md` goals. Read last 7 days of activity. Append to `drift.md` one paragraph naming the biggest gap. Then synthesize lessons from `critique_log.md` + week's commits and append to `lessons.md`. |

## 4. State directory contract

The state directory is the **contract** between agents. Agents do not call each other — they leave notes for each other. This means each agent can be tested in isolation, swapped, or even hand-edited if it gets something wrong.

```
~/agentstate/
├── profile.md              # YOU edit. Goals, target role, stack, focus areas.
├── derived_state.md        # Historian nightly (overwrite).
├── drift.md                # Historian weekly (append).
├── signals.md              # Scout daily (overwrite).
├── today.md                # Coach daily (overwrite). The artifact you read.
├── solutions/
│   └── 2026-05-13.md       # Coach challenge's reference solution.
├── critique_log.md         # Critic append-only.
├── lessons.md              # Historian weekly (append).
├── archive/
│   ├── signals/2026-05-12.md
│   └── today/2026-05-12.md
├── repos.toml              # config: list of git repos for Historian.
└── config.toml             # cron times, models, delivery channels, critique level.
```

### 4.1 `profile.md` template

Sets direction. The user maintains this by hand.

```markdown
# Engineering Profile

## Who I am
CS student. Currently building toward software engineering with a
security specialization.

## Target role (18 months out)
Security engineer at a top-tier company (FAANG or peer).

## Current stack
Python, Java, SQLite, JDBC. Learning: Anthropic SDK, Composio,
agent architectures, MCP.

## Active projects
- ComposioAgent (personal-assistant agent, mid-build)

## Focus areas this quarter
1. Agent architectures (orchestrator + specialist pattern)
2. Security fundamentals (CTF practice, OWASP top 10)
3. Systems literacy (one read per week from a senior eng blog)

## Things I want the Critic calibrating to
Senior engineer at top-tier company. Don't be gentle. Name
blind spots specifically. Reference the better pattern.
```

### 4.2 `config.toml` schema

```toml
[models]
scout = "claude-sonnet-4-6"
coach = "claude-opus-4-7"
critic = "claude-opus-4-7"
historian = "claude-sonnet-4-6"

[schedule]
scout = "0 6 * * *"
coach = "0 7 * * *"
historian_nightly = "0 23 * * *"
historian_weekly = "30 22 * * 0"
critic_weekly = "0 22 * * 0"

[delivery]
shell_greeting = true     # cat today.md on new terminal
slack = false             # v2
email = false             # v2

[critic]
calibration_target = "senior engineer at top-tier company"
post_commit_enabled = true
```

### 4.3 `repos.toml` schema

```toml
[[repo]]
path = "/Users/iibrahimsv/PycharmProjects/ComposioAgent"
nickname = "ComposioAgent"
languages = ["python"]

[[repo]]
path = "/Users/iibrahimsv/code/cs-coursework"
nickname = "Coursework"
languages = ["java"]
```

## 5. Code structure

Lives inside the existing `AgentConfig/` directory under a new `coach/` subpackage.

```
AgentConfig/coach/
├── __init__.py
├── runner.py           # shared: load state, call Anthropic, write state, error handling
├── scout.py            # scout main + source adapters (HN, ArXiv, web)
├── coach.py            # coach main + synthesis prompt loader
├── critic.py           # critic main + git diff handler
├── historian.py        # historian main + repo walker + drift calc
├── cli.py              # `coach scout`, `coach today`, `coach critic --commit HEAD`, `coach weekly`
├── state.py            # file paths, archive rotation, atomic writes
├── prompts/
│   ├── scout.md
│   ├── coach.md
│   ├── critic.md
│   └── historian.md
└── sources/
    ├── __init__.py
    ├── hn.py           # Hacker News Algolia API
    ├── arxiv.py        # ArXiv RSS
    └── github.py       # GitHub trending
```

The `coach` CLI is the single entry point for cron and the git hook. All scheduling lives in user crontab (not in Python) so it's debuggable and visible to the OS.

**Cron entries:**

```
0  6  * * *  cd ~/PycharmProjects/ComposioAgent && AgentConfig/coach/cli.py scout
0  7  * * *  cd ~/PycharmProjects/ComposioAgent && AgentConfig/coach/cli.py coach
0  23 * * *  cd ~/PycharmProjects/ComposioAgent && AgentConfig/coach/cli.py historian nightly
30 22 * * 0  cd ~/PycharmProjects/ComposioAgent && AgentConfig/coach/cli.py historian weekly
0  22 * * 0  cd ~/PycharmProjects/ComposioAgent && AgentConfig/coach/cli.py critic weekly
```

**Git hook (`.git/hooks/post-commit` in each watched repo):**

```bash
#!/bin/sh
~/PycharmProjects/ComposioAgent/AgentConfig/coach/cli.py critic --commit HEAD &
```

(Backgrounded so commits stay fast; failures are silent and logged.)

**Shell greeting (one line appended to `.zshrc`):**

```bash
[ -f ~/agentstate/today.md ] && cat ~/agentstate/today.md
```

## 6. Build order

Compounding, not big-bang. Every step ships something usable on its own.

| Step | What ships | Time | Standalone value |
|---|---|---|---|
| 1 | Bootstrap: state dir + `profile.md` template + `config.toml` + `repos.toml` + `coach` CLI skeleton | ~30 min | Forces user to write down goals |
| 2 | Historian nightly only — `derived_state.md` from git walks | ~3 hrs | "You committed 0 security code in 14 days" — already useful |
| 3 | Coach v0 — reads `profile` + `derived_state`, writes `today.md` (no Scout dependency yet) | ~3 hrs | Daily artifact exists |
| 4 | Scout — HN + ArXiv + web search → `signals.md` | ~4 hrs | Coach now connects to world-state |
| 5 | Critic post-commit — git hook + per-commit review | ~3 hrs | Every commit gets reviewed |
| 6 | Historian weekly — `drift.md` + `lessons.md` + Critic weekly trend | ~3 hrs | Sunday-night meta-insight |
| 7 | Delivery polish — Slack DM via Composio | ~2 hrs | Phone notifications |

Total ≈ 18 hours of focused work. Spread over 2–3 weeks at one specialist per session, matching the user's existing "compounding cadence" preference (see architecture plan memory).

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Cost: Opus-4-7 daily Coach + per-commit Critic could rack up bills | Per-commit Critic runs only on commits > N lines (skip tiny commits). Coach prompt caching on `profile.md` + `lessons.md` (rarely change). Estimate first month's cost after step 5. |
| Slop: agent outputs become generic / repetitive | Coach reads last 7 days of `today.md` from archive — explicitly told "do not repeat suggestions." Weekly user rating optional (append `★`/`✗` to a line; Historian factors into lessons). |
| Stale state: `profile.md` rots | Historian's weekly drift report names "your profile says X, your code says Y" — surfacing rot organically. |
| Git hook fragility | Hook is async (backgrounded); failures don't block commit. Logs to `~/agentstate/critique_log.md` regardless. |
| Cron silent failures | All cron entries pipe stderr to `~/agentstate/.runlog`. A `coach status` command shows last run timestamps + exit codes. |
| Scope creep into v2 features mid-build | Build order is strict; v2 items (Slack, web dashboard, conversational check-ins) are explicitly out of scope for this spec. |

## 8. Open decisions deferred to implementation

These are deliberately left open for the implementation plan to resolve:

- Exact prompt content for each agent's `prompts/*.md` (will iterate empirically)
- Whether to use prompt caching from day 1 or add in step 5 (likely add early)
- Whether the `coach` CLI uses Click, Typer, or argparse (preference, not architectural)
- Atomic write strategy for state files (write-temp + rename vs. simple write)
- Whether `signals.md` keeps a max length cap (probably yes, ~50 signals/day cap)

## 9. Success criteria

- After step 3 (Coach v0), user reads `today.md` daily for 5 consecutive days without manual prompting
- After step 5 (Critic post-commit), user references a critic finding in at least one fix per week
- After step 6 (Historian weekly), `drift.md` correctly identifies at least one real gap the user agrees with
- After step 7 (Slack delivery), user opens Slack DM within 30 min of 7am at least 4 of 7 days

If these criteria aren't met, the system isn't working and the prompts/triggers need rework before adding scope.
