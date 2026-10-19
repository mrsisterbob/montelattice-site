"""Suite-wide fixtures."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import buildstats  # noqa: E402
import resume_alert  # noqa: E402


@pytest.fixture(autouse=True)
def _no_remote_build_stats(monkeypatch):
    """Keep the suite offline: an empty URL means "no remote snapshot". A test of the remote
    path sets buildstats.SNAPSHOT_URL itself and patches urllib.request.urlopen."""
    monkeypatch.setattr(buildstats, "SNAPSHOT_URL", "")
    buildstats.reset_cache()
    yield
    buildstats.reset_cache()


@pytest.fixture(autouse=True)
def _no_resume_alert(monkeypatch):
    """No test may POST to the engine, even if a real LEAD_INGEST_TOKEN is in the environment.
    test_resume_alert.py restores the real notify itself."""
    monkeypatch.setattr(resume_alert, "notify", lambda request, session: None)
