"""Suite-wide fixtures."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import buildstats  # noqa: E402


@pytest.fixture(autouse=True)
def _no_remote_build_stats(monkeypatch):
    """Keep the suite offline: an empty URL means "no remote snapshot". A test of the remote
    path sets buildstats.SNAPSHOT_URL itself and patches urllib.request.urlopen."""
    monkeypatch.setattr(buildstats, "SNAPSHOT_URL", "")
    buildstats.reset_cache()
    yield
    buildstats.reset_cache()
