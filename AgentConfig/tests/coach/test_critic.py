"""Tests for coach.critic — Critic v0.

All offline: the Anthropic call is injected via a FakeClient, so no test
touches the network.
"""

from __future__ import annotations

from datetime import datetime, timezone

from coach import critic
from coach.repos import RepoEntry


# --- fake Anthropic client -------------------------------------------------

class _Block:
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class _Resp:
    def __init__(self, text: str):
        self.content = [_Block(text)]


class _Messages:
    def __init__(self, outer: "FakeClient"):
        self._outer = outer

    def create(self, **kwargs):
        self._outer.calls.append(kwargs)
        return _Resp(self._outer.text)


class FakeClient:
    def __init__(self, text: str = "★ Good: solid.\n✗ Blind spot: x.\n↗ Stretch: y."):
        self.text = text
        self.calls: list[dict] = []
        self.messages = _Messages(self)


# --- helpers ---------------------------------------------------------------

def _profile(tmp_path, text="# Engineering Profile\nTarget: AI Engineer.\n"):
    (tmp_path / "profile.md").write_text(text)


def _entry(repo_path) -> RepoEntry:
    return RepoEntry(path=repo_path, nickname="Alpha", languages=["python"])


def _two_commits(make_repo):
    return make_repo(
        name="alpha",
        commits=[
            ("2026-05-14T20:00:00+00:00", "a.py", "new\nline\n"),
            ("2026-05-13T20:00:00+00:00", "a.py", "old\n"),
        ],
    )


# --- tests -----------------------------------------------------------------

def test_collect_review_input(make_repo, tmp_path, monkeypatch):
    monkeypatch.setenv("COACH_STATE_DIR", str(tmp_path))
    _profile(tmp_path)
    r = critic.collect_review_input(_entry(_two_commits(make_repo)))

    assert r.repo_nickname == "Alpha"
    assert r.sha
    assert "a.py" in r.diff
    assert "AI Engineer" in r.profile_text


def test_build_prompt_includes_profile_diff_and_labels():
    r = critic.ReviewInput(
        repo_nickname="Alpha",
        sha="abc1234",
        subject="do thing",
        diff="diff --git a/a.py b/a.py",
        profile_text="MY UNIQUE PROFILE",
    )
    system, user = critic.build_prompt(r)

    assert "MY UNIQUE PROFILE" in user
    assert "a.py" in user
    assert "★" in system and "✗" in system and "↗" in system


def test_render_entry_header_format():
    r = critic.ReviewInput("Alpha", "abc1234", "s", "d", "p")
    now = datetime(2026, 6, 8, 14, 32, tzinfo=timezone.utc)

    out = critic.render_entry(r, "BODY", now)

    assert "## 2026-06-08 14:32 UTC — abc1234 (Alpha)" in out
    assert "BODY" in out


def test_append_entry_writes_frontmatter_once(tmp_path, monkeypatch):
    monkeypatch.setenv("COACH_STATE_DIR", str(tmp_path))
    now = datetime(2026, 6, 8, 14, 32, tzinfo=timezone.utc)

    critic.append_entry("\n## entry 1\n", now=now)
    critic.append_entry("\n## entry 2\n", now=now)

    text = (tmp_path / "critique_log.md").read_text()
    assert text.startswith("---")
    assert text.count("source_agent: critic") == 1
    assert "entry 1" in text and "entry 2" in text


def test_run_end_to_end_with_fake_client(make_repo, tmp_path, monkeypatch):
    monkeypatch.setenv("COACH_STATE_DIR", str(tmp_path))
    _profile(tmp_path)
    fake = FakeClient("★ Good: solid.\n✗ Blind spot: x.\n↗ Stretch: y.")
    now = datetime(2026, 6, 8, 14, 32, tzinfo=timezone.utc)

    target = critic.run(repo=_entry(_two_commits(make_repo)), now=now, client=fake)

    assert len(fake.calls) == 1
    text = target.read_text()
    assert "★ Good: solid." in text
    assert "Alpha" in text


def test_run_dry_run_makes_no_call_or_write(make_repo, tmp_path, monkeypatch):
    monkeypatch.setenv("COACH_STATE_DIR", str(tmp_path))
    _profile(tmp_path)
    fake = FakeClient()

    critic.run(repo=_entry(_two_commits(make_repo)), client=fake, dry_run=True)

    assert len(fake.calls) == 0
    assert not (tmp_path / "critique_log.md").exists()
