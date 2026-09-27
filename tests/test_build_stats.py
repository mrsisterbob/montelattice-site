"""Build figures on the profile: measured by build_stats.py, served from a committed snapshot.
Driven through the real Flask app (test client), not helper return values.

Run: python -m pytest tests -q
"""
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import buildstats  # noqa: E402
import build_stats  # noqa: E402
import main  # noqa: E402

BANK = {
    "identity": {"name": "Test Person"},
    "experience": [],
    "site_profile": {"figures": [
        {"value": "4", "label": "Systems built, running in production"},
        {"live": "commit_hours"},
        {"live": "tracked_lines"},
    ]},
}


def _snapshot(path, hours=159, lines=44255, age_days=0):
    generated = datetime.now(timezone.utc) - timedelta(days=age_days)
    path.write_text(json.dumps({
        "generated_at": generated.isoformat(timespec="seconds"), "commit_hours": hours,
        "tracked_lines": lines, "repos": {n: {} for n in build_stats.REPOS}, "unreachable": []}),
        encoding="utf-8")
    return path


@pytest.fixture
def client(tmp_path, monkeypatch):
    bank = tmp_path / "bank.json"
    bank.write_text(json.dumps(BANK), encoding="utf-8")
    monkeypatch.setenv("EVIDENCE_BANK_SOURCE", str(bank))
    snap = _snapshot(tmp_path / "build_stats.json")
    monkeypatch.setattr(buildstats, "SNAPSHOT_PATH", str(snap))
    buildstats.reset_cache()
    yield main.app.test_client()
    buildstats.reset_cache()


def _profile(client):
    r = client.get("/")
    assert r.status_code == 200
    return r.get_data(as_text=True)


def test_profile_shows_measured_figures_with_honest_labels(client):
    html = _profile(client)
    assert "159" in html and "44,255" in html
    assert "Hours with a commit" in html and "A measured floor, not a total." in html
    assert "Lines of tracked code across 5 repos" in html
    assert "150+" not in html and "hours worked" not in html.lower()


def test_neither_build_number_is_hardcoded_anywhere_served():
    committed = json.loads((ROOT / "data" / "build_stats.json").read_text(encoding="utf-8"))
    values = {str(committed["commit_hours"]), f"{committed['tracked_lines']:,}", str(committed["tracked_lines"])}
    sources = list((ROOT / "templates").glob("*.html")) + [ROOT / "homepage.py", ROOT / "main.py", ROOT / "buildstats.py"]
    for p in sources:
        text = p.read_text(encoding="utf-8")
        for v in values | {"150+"}:
            assert not re.search(rf"(?<![\d,]){re.escape(v)}(?![\d,])", text), (p.name, v)


def test_requests_never_shell_out_and_snapshot_is_read_at_most_daily(client, monkeypatch):
    def no_git(*a, **k):
        raise AssertionError("a page load shelled out")
    monkeypatch.setattr(subprocess, "run", no_git)
    monkeypatch.setattr(subprocess, "Popen", no_git)
    reads = []
    real_read = buildstats._read
    monkeypatch.setattr(buildstats, "_read", lambda p: reads.append(p) or real_read(p))
    for _ in range(5):
        assert "44,255" in _profile(client)
    assert len(reads) == 1  # one disk read serves every request inside the window

    t0 = time.time()
    buildstats.load(now=t0 + buildstats.CACHE_SECONDS - 60)
    assert len(reads) == 1
    buildstats.load(now=t0 + buildstats.CACHE_SECONDS + 60)
    assert len(reads) == 2  # and it re-reads once the day is up


@pytest.mark.parametrize("breakage", ["missing", "garbage", "zero", "stale"])
def test_failed_measurement_renders_empty_state_never_a_number(client, tmp_path, monkeypatch, breakage):
    snap = tmp_path / "broken.json"
    if breakage == "garbage":
        snap.write_text("{not json", encoding="utf-8")
    elif breakage == "zero":
        _snapshot(snap, hours=0, lines=0)
    elif breakage == "stale":
        _snapshot(snap, age_days=buildstats.MAX_AGE_DAYS + 1)
    monkeypatch.setattr(buildstats, "SNAPSHOT_PATH", str(snap))
    buildstats.reset_cache()
    html = _profile(client)
    assert "159" not in html and "44,255" not in html
    assert html.count(buildstats_empty()) == 2
    assert "Hours with a commit" in html  # the tile stays, labelled, with no number in it


def buildstats_empty():
    import homepage
    return homepage.LIVE_EMPTY


def test_measure_unions_hours_across_repos_and_names_unreachable_ones(tmp_path):
    def repo(name, stamps):
        path = tmp_path / name
        path.mkdir()
        git = lambda *a, **env: subprocess.run(["git", "-C", str(path), *a], check=True, capture_output=True,
                                               env={**__import__("os").environ, **env})
        git("init", "-q")
        (path / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
        (path / "notes.md").write_text("not code\n" * 50, encoding="utf-8")
        git("add", ".")
        for i, stamp in enumerate(stamps):
            git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", str(i),
                GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp)
    repo("one", ["2026-09-01T10:05:00", "2026-09-01T10:40:00", "2026-09-01T11:00:00"])
    repo("two", ["2026-09-01T10:15:00", "2026-09-02T09:00:00"])
    stats = build_stats.measure(str(tmp_path), ["one", "two", "absent"])
    assert stats["commit_hours"] == 3  # 09-01 10 (shared), 09-01 11, 09-02 09
    assert stats["tracked_lines"] == 4  # two .py lines per repo; the markdown is not code
    assert stats["unreachable"] == ["absent"]


def test_only_the_measured_figures_carry_the_live_marker(client):
    """The warm edge on the figures block is how a reader tells a measured number from a banked
    one. It is driven by f.live, so a figure that stops being measured must stop being marked.
    Drives the real page, not _figures(), because the class is applied in the template."""
    html = client.get("/").get_data(as_text=True)
    cells = re.findall(r'<div class="fig(?: fig--live)?">\s*<div class="fig-n">([^<]+)', html)
    live = re.findall(r'<div class="fig fig--live">\s*<div class="fig-n">([^<]+)', html)
    assert len(cells) > len(live), "every figure marked live means the marker says nothing"
    # The client fixture serves a synthetic snapshot (_snapshot defaults), so assert against
    # those, not data/build_stats.json: the point is that the marker follows the measured
    # values wherever they come from.
    assert set(live) == {"159", "44,255"}
