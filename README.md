# Polaris

An AI engineering coach — an orchestrator plus specialist subagents that watch
your repos, debrief you each morning, and keep your long-term direction
honest. Built on the Anthropic SDK and Composio.

> Polaris is the star sailors steer by. This project is the same idea for an
> engineering career: a fixed point to orient your day-to-day work against.

## Why this exists

I want to land an AI/Prompt Engineer role at a top-tier company. Generic
"productivity bots" don't help with that — they give you reminders, not
judgment. Polaris is the opposite: a small system of agents that read your
actual repos and your stated 18-month direction, then tell you where today's
work is helping and where it's drifting.

Building it is also the portfolio piece. Designing the orchestration, prompt
contracts, and state model *is* the skill I'm hiring myself for.

## What works today

- **`coach` CLI** — `coach init` writes the state directory at `~/agentstate/`
  with three template files (`profile.md`, `config.toml`, `repos.toml`);
  `coach status` reports which state files are present.
- **State module** with atomic writes (write-temp + `os.replace`) so readers
  never see a partial file, and a `COACH_STATE_DIR` override for tests.
- **Anthropic agent runners** (`AgentConfig/`):
  - `simple_agent.py` — stateless Messages API chat (smoke test for keys).
  - `enhanced_agent_runner.py` — full beta agents/sessions/events loop with
    env + agent caches and optional Composio tool injection.
  - `interactive_agent.py` — terminal REPL over the runner.
  - `diagnostic_agent.py` — probes which models the beta agents endpoint
    accepts, so you find out before a real session.
  - `testAgent.py` — integration tests for the runner's success and error
    paths.

See [`AgentConfig/ARCHITECTURE.md`](AgentConfig/ARCHITECTURE.md) for the full
component map and the call sequence diagram.

## Roadmap

| Step | Subagent       | Job                                              | Status   |
|------|----------------|--------------------------------------------------|----------|
| 1    | Coach (core)   | State dir, profile/config templates, CLI         | shipped  |
| 2    | Historian      | Nightly repo crawl → `signals.md` digest         | next     |
| 3    | Critic         | Compare today's work against `profile.md`        | planned  |
| 4    | Planner        | Morning brief: what to ship, what to drop        | planned  |
| 5    | Reactive layer | Composio triggers for CI failures and PR review  | planned  |

## Getting started

```bash
git clone https://github.com/iibrahimsv/polaris.git
cd polaris/AgentConfig
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` next to `AgentConfig/`:

```env
ANTHROPIC_API_KEY=sk-ant-...
COMPOSIO_API_KEY=...        # optional — only needed for tool-using agents
```

Then:

```bash
# verify the SDK + key
python diagnostic_agent.py

# initialize the coach state dir at ~/agentstate/
python -m coach init

# see what's present
python -m coach status

# run the interactive agent REPL
python interactive_agent.py
```

## Layout

```
polaris/
├── AgentConfig/
│   ├── coach/                  # Coach subagent package
│   │   ├── cli.py              # `coach init` / `coach status`
│   │   ├── state.py            # paths + atomic_write
│   │   └── templates/          # profile.md, config.toml, repos.toml
│   ├── config.py               # AgentConfig dataclass (env-loaded)
│   ├── enhanced_agent_runner.py
│   ├── interactive_agent.py
│   ├── simple_agent.py
│   ├── diagnostic_agent.py
│   ├── quick_start.py
│   ├── testAgent.py
│   ├── ARCHITECTURE.md
│   └── requirements.txt
└── README.md
```

The runtime state directory (`~/agentstate/`) is intentionally outside the
repo — it holds personal profile data, derived state, and per-day signals,
none of which belong in git.

## Design notes

- **Subagent boundaries by file, not by function call.** Each specialist
  reads and writes its own markdown file in `~/agentstate/`. The orchestrator
  composes them by reading those files, not by chaining tool calls. This
  keeps each agent independently runnable, testable, and replayable.
- **Atomic writes everywhere.** The state dir is read by multiple processes
  (cron jobs, the morning brief, the REPL). Partial writes would corrupt
  everything downstream.
- **Composio for tools, Anthropic for reasoning.** Composio returns
  Anthropic-formatted tool schemas, so they slot directly into
  `agents.create(tools=...)` with no adapter layer.

## License

[MIT](LICENSE) © 2026 Abdi Ibrahim.
