"""Tests for coach.historian — snapshot dataclasses, collector, renderer."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from coach import historian
from coach.repos import RepoEntry


def test_collect_snapshot_aggregates_per_repo(make_repo):
    repo_a = make_repo(
        name="A",
        commits=[
            ("2026-05-14T20:00:00+00:00", "main.py", "a\nb\nc\n"),
            ("2026-05-13T20:00:00+00:00", "main.py", "a\nb\n"),
            # 7d window from 2026-05-14T23:00 cuts at 2026-05-07T23:00,
            # so this commit must be earlier than that to land out-of-window.
            ("2026-05-06T20:00:00+00:00", "main.py", "a\n"),
        ],
    )
    repo_b = make_repo(
        name="B",
        commits=[
            ("2026-05-10T20:00:00+00:00", "App.java", "class App {}\n"),
        ],
    )

    entries = [
        RepoEntry(path=repo_a, nickname="Alpha", languages=["python"]),
        RepoEntry(path=repo_b, nickname="Bravo", languages=["java"]),
    ]
    now = datetime(2026, 5, 14, 23, 0, 0, tzinfo=timezone.utc)

    snap = historian.collect_snapshot(entries, now=now, lines_per_hour=60)

    assert snap.generated_at == now
    assert len(snap.repos) == 2
    assert snap.repos[0].nickname == "Alpha"
    assert snap.repos[0].commits_24h == 1
    assert snap.repos[0].commits_7d == 2
    assert snap.repos[1].nickname == "Bravo"
    assert snap.repos[1].commits_24h == 0
    assert snap.repos[1].commits_7d == 1
    assert "python" in snap.hours_by_stack
    assert "java" in snap.hours_by_stack
    assert snap.hours_by_stack["python"] > 0


def test_collect_snapshot_empty_repo_yields_zero_stats(make_repo, tmp_path):
    import subprocess

    empty = tmp_path / "empty_repo"
    empty.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=empty, check=True)

    entries = [
        RepoEntry(path=empty, nickname="Empty", languages=["python"]),
    ]
    now = datetime(2026, 5, 14, 23, 0, 0, tzinfo=timezone.utc)

    snap = historian.collect_snapshot(entries, now=now)

    assert snap.repos[0].last_commit is None
    assert snap.repos[0].commits_24h == 0
    assert snap.repos[0].commits_7d == 0
    assert snap.repos[0].diff_total_7d == 0
    assert snap.hours_by_stack == {"python": 0.0}


def test_collect_snapshot_multi_language_repo_splits_diff(make_repo):
    repo = make_repo(
        name="multilang",
        commits=[
            ("2026-05-14T20:00:00+00:00", "f.py", "x\ny\nz\n"),
        ],
    )
    entries = [
        RepoEntry(path=repo, nickname="Multi", languages=["python", "java"]),
    ]
    now = datetime(2026, 5, 14, 23, 0, 0, tzinfo=timezone.utc)

    snap = historian.collect_snapshot(entries, now=now, lines_per_hour=60)

    # Total diff = 3 lines. Split across 2 languages = 1.5 lines each.
    # Hours = 1.5 / 60 = 0.025 each.
    assert snap.hours_by_stack["python"] == snap.hours_by_stack["java"]
    assert snap.hours_by_stack["python"] > 0


def test_render_derived_state_includes_all_repos_and_totals():
    snap = historian.Snapshot(
        generated_at=datetime(2026, 5, 14, 23, 0, 0, tzinfo=timezone.utc),
        repos=[
            historian.RepoSnapshot(
                nickname="Alpha",
                path=Path("/tmp/alpha"),
                last_commit=datetime(2026, 5, 14, 20, 0, 0, tzinfo=timezone.utc),
                commits_24h=1,
                commits_7d=3,
                diff_total_7d=120,
                languages=["python"],
            ),
        ],
        hours_by_stack={"python": 2.0},
    )

    text = historian.render_derived_state(snap)

    assert "2026-05-14" in text
    assert "Alpha" in text
    assert "/tmp/alpha" in text
    assert "120" in text  # diff total appears
    assert "python" in text
    assert "2.0" in text  # hours-by-stack value appears
    assert "100" in text and "%" in text  # language share section appears


def test_render_derived_state_handles_empty_repos_list():
    snap = historian.Snapshot(
        generated_at=datetime(2026, 5, 14, 23, 0, 0, tzinfo=timezone.utc),
        repos=[],
        hours_by_stack={},
    )

    text = historian.render_derived_state(snap)

    assert "2026-05-14" in text
    assert "no repos" in text.lower()


def test_render_derived_state_emits_yaml_frontmatter_with_required_keys():
    snap = historian.Snapshot(
        generated_at=datetime(2026, 5, 14, 23, 0, 0, tzinfo=timezone.utc),
        repos=[
            historian.RepoSnapshot(
                nickname="Alpha",
                path=Path("/tmp/alpha"),
                last_commit=datetime(2026, 5, 14, 20, 0, 0, tzinfo=timezone.utc),
                commits_24h=1,
                commits_7d=3,
                diff_total_7d=120,
                languages=["python"],
            ),
        ],
        hours_by_stack={"python": 2.0},
    )

    text = historian.render_derived_state(snap)

    # frontmatter is the first thing in the output, fenced by ---
    assert text.startswith("---\n"), "expected --- on line 1"
    end = text.find("\n---\n", 4)
    assert end > 0, "expected closing --- fence"
    fm = text[4:end]

    # required keys present
    assert "generated_at: 2026-05-14T23:00:00+00:00" in fm
    assert "source_agent: historian" in fm
    assert "schema_version: 1" in fm
    # inputs_hash is a 64-char hex sha256
    assert "inputs_hash: " in fm
    hash_line = [ln for ln in fm.splitlines() if ln.startswith("inputs_hash:")][0]
    hash_value = hash_line.split(":", 1)[1].strip()
    assert len(hash_value) == 64 and all(c in "0123456789abcdef" for c in hash_value)


def test_render_derived_state_inputs_hash_stable_across_renders():
    """Same observable snapshot → same inputs_hash, regardless of generated_at."""
    repos = [
        historian.RepoSnapshot(
            nickname="Alpha",
            path=Path("/tmp/alpha"),
            last_commit=datetime(2026, 5, 14, 20, 0, 0, tzinfo=timezone.utc),
            commits_24h=1,
            commits_7d=3,
            diff_total_7d=120,
            languages=["python"],
        ),
    ]
    snap_a = historian.Snapshot(
        generated_at=datetime(2026, 5, 14, 23, 0, 0, tzinfo=timezone.utc),
        repos=repos,
        hours_by_stack={"python": 2.0},
    )
    snap_b = historian.Snapshot(
        # different generated_at — should NOT affect inputs_hash
        generated_at=datetime(2026, 5, 14, 23, 5, 0, tzinfo=timezone.utc),
        repos=repos,
        hours_by_stack={"python": 2.0},
    )

    text_a = historian.render_derived_state(snap_a)
    text_b = historian.render_derived_state(snap_b)

    hash_a = [ln for ln in text_a.splitlines() if ln.startswith("inputs_hash:")][0]
    hash_b = [ln for ln in text_b.splitlines() if ln.startswith("inputs_hash:")][0]

    assert hash_a == hash_b
