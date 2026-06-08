#!/usr/bin/env bash
# Polaris agent smoke suite — verifies every runnable agent executes without error.
# Runs daily via com.polaris.smoke.plist and appends a PASS/FAIL line to
# ~/agentstate/.smoke_log.
#
# MUST use venv_py311 (Python 3.11+). The repo .venv is 3.9 and fails on
# `import tomllib` (3.11+ stdlib) and has no pytest — that mismatch is the
# whole reason this suite is pinned to an explicit interpreter.
#
# As agents ship (Critic, Coach, Scout), add a run_check line below.
set -u

REPO="/Users/iibrahimsv/PycharmProjects/ComposioAgent"
PY="$REPO/venv_py311/bin/python"
APP="$REPO/AgentConfig"
LOG="$HOME/agentstate/.smoke_log"
TS="$(date '+%Y-%m-%d %H:%M:%S %z')"

cd "$APP" || { echo "$TS  FAIL  cannot cd $APP" >> "$LOG"; exit 1; }

fails=0
results=""

run_check () {
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then
    results="$results ${name}=ok"
  else
    results="$results ${name}=FAIL"
    fails=$((fails + 1))
  fi
}

run_check pytest    "$PY" -m pytest tests/coach/ -q
run_check status    "$PY" -m coach.cli status
run_check historian "$PY" -m coach.cli historian nightly
run_check critic    "$PY" -m coach.cli critic run --dry-run

if [ "$fails" -eq 0 ]; then
  echo "$TS  PASS  --${results}" >> "$LOG"
else
  echo "$TS  FAIL(${fails})  --${results}" >> "$LOG"
fi

exit "$fails"
