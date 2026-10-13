"""/job-engine shows a server-rendered flow chart whose band widths are the engine's own counts.
Run: python -m pytest tests -q
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import jobstats  # noqa: E402
import main  # noqa: E402
from test_job_dashboard import FULL  # noqa: E402

NO_FUNNEL = dict(FULL, funnel=None)
WITH_FUNNEL = dict(FULL, funnel={"replies": 2, "interviews": 1, "offers": 0, "reply_rate_pct": 2.4,
                                 "interview_rate_pct": 1.2, "offer_rate_pct": 0.0})


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("PUBLIC_FUNNEL_STATS", raising=False)
    monkeypatch.setenv("ANALYTICS_ENABLED", "false")
    return main.app.test_client()


def _page(client, monkeypatch, payload):
    monkeypatch.setattr(jobstats, "fetch", lambda: payload)
    r = client.get("/job-engine")
    assert r.status_code == 200
    return r.get_data(as_text=True)


def _flow(html):
    m = re.search(r'<svg class="pipeline-flow".*?</svg>', html, re.S)
    return m.group(0) if m else ""


def _bands(svg):
    """[(label, count text, band width)] in document order."""
    out = []
    for g in re.findall(r"<g transform.*?</g>", svg, re.S):
        texts = re.findall(r"<text[^>]*>(.*?)</text>", g, re.S)
        label = re.sub(r"<[^>]+>", "", texts[0]).strip()
        width = float(re.search(r'<rect[^>]*width="([\d.]+)"', g).group(1))
        out.append((label, texts[1].strip(), width))
    return out


def test_flow_without_a_funnel_has_exactly_the_four_pipeline_stages_in_order(client, monkeypatch):
    svg = _flow(_page(client, monkeypatch, NO_FUNNEL))
    assert 'viewBox="0 0 ' in svg and 'role="img"' in svg
    bands = _bands(svg)
    assert [b[0].split(" since")[0] for b in bands] == [
        "Listings discovered", "Roles screened", "Documents compiled", "Applications sent"]
    assert [b[1] for b in bands] == ["5,678", "1,234", "14", "82"]


def test_flow_with_a_funnel_adds_replies_interviews_offers_after_applications(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_FUNNEL_STATS", "true")
    svg = _flow(_page(client, monkeypatch, WITH_FUNNEL))
    labels = [b[0] for b in _bands(svg)]
    assert labels[-3:] == ["Replies", "Interviews", "Offers"]
    assert labels.index("Applications sent") == len(labels) - 4


def test_flow_the_funnel_stays_hidden_when_the_site_switch_is_off(client, monkeypatch):
    labels = [b[0] for b in _bands(_flow(_page(client, monkeypatch, WITH_FUNNEL)))]
    assert "Replies" not in labels


def test_flow_a_missing_count_drops_that_band_and_the_page_still_renders(client, monkeypatch):
    html = _page(client, monkeypatch, dict(NO_FUNNEL, documents_compiled=None))
    labels = [b[0] for b in _bands(_flow(html))]
    assert not any(label.startswith("Documents compiled") for label in labels)
    assert len(labels) == 3


def test_flow_the_largest_stage_has_the_widest_band_and_small_ones_keep_a_sliver(client, monkeypatch):
    bands = _bands(_flow(_page(client, monkeypatch, NO_FUNNEL)))
    widths = {label.split(" since")[0]: w for label, _, w in bands}
    assert widths["Listings discovered"] == max(widths.values())
    assert widths["Documents compiled"] >= 0.04 * 560 - 0.1


def test_flow_widths_are_proportional_to_the_counts(client, monkeypatch):
    widths = {label.split(" since")[0]: w for label, _, w in _bands(_flow(_page(client, monkeypatch, NO_FUNNEL)))}
    assert widths["Roles screened"] / widths["Listings discovered"] == pytest.approx(1234 / 5678, rel=0.01)


def test_flow_implies_no_conversion_and_prints_no_percentage(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_FUNNEL_STATS", "true")
    svg = _flow(_page(client, monkeypatch, WITH_FUNNEL))
    assert "%" not in svg
    assert "since Sep 26, 2026" in svg  # the documents counter's own start date


def test_flow_is_absent_with_fewer_than_two_stages_and_with_no_feed(client, monkeypatch):
    only_one = {"status": "ok", "roles_screened": 5, "timeline": []}
    assert 'class="pipeline-flow"' not in _page(client, monkeypatch, only_one)
    monkeypatch.setattr(jobstats, "fetch", lambda: None)
    assert client.get("/job-engine").status_code == 200


def test_flow_adds_no_script_and_uses_chart_tokens(client, monkeypatch):
    svg = _flow(_page(client, monkeypatch, NO_FUNNEL))
    assert "<script" not in svg
    assert set(re.findall(r"var\((--[\w-]+)\)", svg)) <= {"--ink", "--muted", "--chart-1", "--chart-2",
                                                          "--chart-3", "--chart-4", "--chart-5", "--chart-6", "--ok"}
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", svg)


def test_flow_stages_is_pure_and_ignores_non_numbers():
    assert jobstats.flow_stages(None) == []
    stages = jobstats.flow_stages({"listings_discovered": "many", "roles_screened": 10, "applications_sent": True})
    assert [s["key"] for s in stages] == ["screened"]


def test_flow_a_real_zero_is_drawn_as_nothing_and_a_missing_funnel_value_reads_as_the_tiles_do(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_FUNNEL_STATS", "true")
    payload = dict(FULL, funnel={"replies": 2, "interviews": None, "offers": 0, "reply_rate_pct": 2.4,
                                 "interview_rate_pct": None, "offer_rate_pct": 0.0})
    bands = {label: (count, width) for label, count, width in _bands(_flow(_page(client, monkeypatch, payload)))}
    assert bands["Offers"] == ("0", 0.0)
    assert bands["Interviews"] == ("0", 0.0)  # the Conversion tile reads 0 for the same missing value
    assert bands["Replies"][1] > 0


def test_flow_colour_follows_the_stage_not_its_position(client, monkeypatch):
    with_docs = _flow(_page(client, monkeypatch, NO_FUNNEL))
    without = _flow(_page(client, monkeypatch, dict(NO_FUNNEL, documents_compiled=None)))
    def colour(svg, label):
        g = [g for g in re.findall(r"<g transform.*?</g>", svg, re.S) if label in g][0]
        return re.search(r"fill: var\((--[\w-]+)\)\"/>", g).group(1)
    assert colour(with_docs, "Applications sent") == colour(without, "Applications sent")


def test_flow_counts_must_be_whole_numbers():
    assert jobstats.flow_stages({"listings_discovered": 1234.5, "roles_screened": 10, "applications_sent": 4})         and [s["key"] for s in jobstats.flow_stages({"listings_discovered": 1234.5, "roles_screened": 10,
                                                     "applications_sent": 4})] == ["screened", "applications"]
