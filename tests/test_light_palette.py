"""The light theme sits on a soft warm off-white ground, with warm cards one step lighter and a warm
grey for secondary text (2026-10-13, after "the white mode is a bit too bright ... more cream, less
pink"). Dark mode and the teal bands are unchanged. Parses the served tokens.css; OKLCH and WCAG 2.x
contrast are computed here in plain Python. Run: python -m pytest tests -q
"""
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import main  # noqa: E402

OLD_LIGHT = {"--paper": "#F2F5FA", "--surface": "#E4EBF8", "--muted": "#5E5760"}
# The dark block as it was on master before this change. It must not move.
DARK = {
    "--teal": "#14152B", "--brass": "#EDCB8C", "--brass-warm": "#CEA872", "--paper": "#121C31",
    "--ink": "#EEEAF0", "--surface": "#19253D", "--muted": "#ABA4B2", "--brass-text": "#EDCB8C",
    "--on-teal": "#EFF3FA", "--teal-deep": "#0D0F1E", "--ok": "#5CC79F", "--warn": "#E0A548",
    "--down": "#EE8670", "--cal1": "#2A3D62", "--cal2": "#3E5E95", "--cal3": "#6F95D1",
    "--cal4": "#A9C4EE", "--chart-1": "#7FA4DC", "--chart-2": "#EBC98A", "--chart-3": "#5FBDB8",
    "--chart-4": "#B3C3DD", "--chart-5": "#D9A273", "--chart-6": "#A7B77E",
}
# Light tokens this task must not touch.
UNCHANGED_LIGHT = {"--teal": "#22254A", "--teal-deep": "#181A36", "--brass": "#E0B978",
                   "--brass-warm": "#BE9A64", "--on-teal": "#EEF2F9", "--ink": "#1D1A1F"}


def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def luminance(h):
    r, g, b = (_lin(v) for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def oklch(h):
    r, g, b = (_lin(v) for v in _rgb(h))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    bb = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360


@pytest.fixture(scope="module")
def palettes():
    css = main.app.test_client().get("/static/css/tokens.css").get_data(as_text=True)
    light = re.search(r':root,\s*:root\[data-theme="light"\] \{(.*?)^\}', css, re.S | re.M).group(1)
    dark = re.search(r':root\[data-theme="dark"\] \{(.*?)\}', css, re.S).group(1)
    grab = lambda block: {k: v.upper() for k, v in re.findall(r"(--[\w-]+):\s*(#[0-9A-Fa-f]{6})\b", block)}
    return {"light": grab(light), "dark": grab(dark)}


def test_light_ground_is_a_warm_off_white_dimmer_than_before(palettes):
    p = palettes["light"]
    assert p["--paper"] != OLD_LIGHT["--paper"]
    assert luminance(p["--paper"]) < luminance(OLD_LIGHT["--paper"]), luminance(p["--paper"])
    for name in ("--paper", "--surface"):
        chroma, hue = oklch(p[name])
        assert 60 <= hue <= 100 and 0.004 <= chroma <= 0.02, (name, p[name], round(chroma, 4), round(hue, 1))


def test_light_cards_are_warm_not_blue_and_never_brighter_than_the_old_ground(palettes):
    p = palettes["light"]
    assert p["--surface"] != OLD_LIGHT["--surface"]
    assert luminance(p["--surface"]) <= luminance(OLD_LIGHT["--paper"]) + 1e-9
    r, _g, b = _rgb(p["--surface"])
    assert b - r <= 2, p["--surface"]  # not blue
    assert contrast(p["--surface"], p["--paper"]) >= 1.08, round(contrast(p["--surface"], p["--paper"]), 3)


def test_light_secondary_text_is_a_warm_grey_that_still_reads(palettes):
    p = palettes["light"]
    assert p["--muted"] != OLD_LIGHT["--muted"]
    _chroma, hue = oklch(p["--muted"])
    assert 40 <= hue <= 100, round(hue, 1)  # the old mauve was 319
    for ground in ("--paper", "--surface"):
        assert contrast(p["--muted"], p[ground]) >= 4.5, (ground, round(contrast(p["--muted"], p[ground]), 2))


def test_light_text_pairs_clear_4_5_and_marks_clear_their_floors_on_the_new_card(palettes):
    p = palettes["light"]
    for fg, bg in [("--ink", "--paper"), ("--ink", "--surface"), ("--brass-text", "--paper"),
                   ("--brass-text", "--surface"), ("--ok", "--surface"), ("--down", "--surface")]:
        assert contrast(p[fg], p[bg]) >= 4.5, (fg, bg, round(contrast(p[fg], p[bg]), 2))
    # Chart marks drawn inside cards (non-text, 3:1); the heatmap's first step must read as a step off
    # the card; --warn is only a fill or border.
    for name in ("--chart-1", "--chart-2", "--chart-3", "--chart-4", "--chart-5", "--chart-6"):
        assert contrast(p[name], p["--surface"]) >= 3.0, name
    assert contrast(p["--cal1"], p["--surface"]) >= 1.4
    assert contrast(p["--warn"], p["--surface"]) >= 3.0


def test_the_dark_block_and_the_teal_bands_did_not_move(palettes):
    for name, value in DARK.items():
        assert palettes["dark"][name] == value, ("dark", name)
    for name, value in UNCHANGED_LIGHT.items():
        assert palettes["light"][name] == value, ("light", name)
