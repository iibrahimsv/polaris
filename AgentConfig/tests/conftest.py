import os
import pytest


@pytest.fixture
def isolated_state_dir(tmp_path, monkeypatch):
    """Point COACH_STATE_DIR at an isolated temp dir for the test."""
    state_dir = tmp_path / "agentstate"
    monkeypatch.setenv("COACH_STATE_DIR", str(state_dir))
    return state_dir
