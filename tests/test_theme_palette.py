"""The blues are a little warmer than before and every documented contrast pair still clears its
floor. Parses the served tokens.css; sRGB -> OKLCH and WCAG 2.x contrast are computed here in pure
Python (no dependency). Run: python -m pytest tests -q
"""
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import main  # noqa: E402

# The values before this change (tokens.css at 2026-09-27): the baseline the hue shift is measured from.
OLD = {
    ("light", "--teal"): "#1D264A", ("light", "--teal-deep"): "#141B36",
    ("dark", "--teal"): "#11162B", ("dark", "--teal-deep"): "#0B101E",
}
HUE_MIN, HUE_MAX = 3.0, 10.0
TEXT_FLOOR, LARGE_FLOOR = 4.5, 3.0


def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def luminance(h):
    r, g, b = (_lin(v) for v in rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def oklch_hue(h):
    r, g, b = (_lin(v) for v in rgb(h))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    bb = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return math.degrees(math.atan2(bb, a)) % 360


def hue_shift(old, new):
    return (oklch_hue(new) - oklch_hue(old) + 180) % 360 - 180


@pytest.fixture(scope="module")
def palettes():
    css = main.app.test_client().get("/static/css/tokens.css").get_data(as_text=True)
    light = re.search(r':root,\s*:root\[data-theme="light"\] \{(.*?)^\}', css, re.S | re.M).group(1)
    dark = re.search(r':root\[data-theme="dark"\] \{(.*?)\}', css, re.S).group(1)
    grab = lambda block: dict(re.findall(r"(--[\w-]+):\s*(#[0-9A-Fa-f]{6})\b", block))
    return {"light": grab(light), "dark": grab(dark)}


@pytest.mark.parametrize("mode,name", sorted(OLD))
def test_palette_teal_is_warmer_by_3_to_10_degrees_of_oklch_hue(palettes, mode, name):
    shift = hue_shift(OLD[(mode, name)], palettes[mode][name])
    assert HUE_MIN <= shift <= HUE_MAX, (mode, name, round(shift, 2))


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_palette_the_gold_accents_are_unchanged(palettes, mode):
    expected = {"light": {"--brass": "#E0B978", "--brass-warm": "#BE9A64"},
                "dark": {"--brass": "#EDCB8C", "--brass-warm": "#CEA872"}}[mode]
    for name, value in expected.items():
        assert palettes[mode][name].upper() == value, (mode, name)


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_palette_text_pairs_clear_4_5_and_large_marks_clear_3(palettes, mode):
    p = palettes[mode]
    text_pairs = [("--ink", "--paper"), ("--ink", "--surface"), ("--muted", "--paper"),
                  ("--muted", "--surface"), ("--brass-text", "--paper"), ("--brass-text", "--surface"),
                  ("--ok", "--surface"), ("--down", "--surface"), ("--on-teal", "--teal"), ("--brass", "--teal")]
    large_pairs = [("--brass-warm", "--teal"), ("--brass-warm", "--teal-deep")]
    for fg, bg in text_pairs:
        assert contrast(p[fg], p[bg]) >= TEXT_FLOOR, (mode, fg, bg, round(contrast(p[fg], p[bg]), 2))
    for fg, bg in large_pairs:
        assert contrast(p[fg], p[bg]) >= LARGE_FLOOR, (mode, fg, bg, round(contrast(p[fg], p[bg]), 2))


def test_palette_documented_figures_match_the_measured_ones(palettes):
    """The header lists each pair to one decimal; it must equal what the hex values compute to."""
    css = (ROOT / "static" / "css" / "tokens.css").read_text(encoding="utf-8")
    header = css[:css.index(":root,")]
    names = {"ink/paper": ("--ink", "--paper"), "ink/surface": ("--ink", "--surface"),
             "muted/paper": ("--muted", "--paper"), "muted/surface": ("--muted", "--surface"),
             "brass-text/paper": ("--brass-text", "--paper"), "brass-text/surface": ("--brass-text", "--surface"),
             "ok/surface": ("--ok", "--surface"), "down/surface": ("--down", "--surface"),
             "on-teal/teal": ("--on-teal", "--teal"), "brass/teal": ("--brass", "--teal"),
             "brass-warm/teal": ("--brass-warm", "--teal"), "brass-warm/teal-deep": ("--brass-warm", "--teal-deep")}
    for mode in ("light", "dark"):
        line = re.search(rf"{mode}:\s+(.*?)(?=\n\s+(?:dark:|\(The))", header, re.S).group(1)
        listed = dict(re.findall(r"([\w-]+/[\w-]+) ([\d.]+)", line))
        assert set(listed) == set(names), (mode, set(names) ^ set(listed))
        for label, (fg, bg) in names.items():
            measured = contrast(palettes[mode][fg], palettes[mode][bg])
            # One decimal as printed; a value on a .x5 boundary may round either way.
            assert abs(float(listed[label]) - measured) <= 0.051, (mode, label, listed[label], round(measured, 3))


def test_palette_light_cards_are_blue_and_separate_from_the_page(palettes):
    """White-on-white was the defect: the surface was lighter than paper and nearly neutral."""
    import math
    lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    def oklch(h):
        r, g, b = (lin(int(h[i:i + 2], 16) / 255) for i in (1, 3, 5))
        l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
        m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
        s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
        a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
        bb = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
        return math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360
    p = palettes["light"]
    chroma, hue = oklch(p["--surface"])
    assert chroma >= 0.015 and 240 <= hue <= 290, (p["--surface"], round(chroma, 4), round(hue, 1))
    assert contrast(p["--surface"], p["--paper"]) >= 1.08, round(contrast(p["--surface"], p["--paper"]), 3)
    # Chart marks drawn inside cards (non-text, 3:1), and the heatmap ramp's first step must still
    # read as a step off the card (it was 1.42 on the old surface).
    for name in ("--chart-1", "--chart-2", "--chart-3", "--chart-4", "--chart-5", "--chart-6"):
        assert contrast(p[name], p["--surface"]) >= LARGE_FLOOR, name
    assert contrast(p["--cal1"], p["--surface"]) >= 1.4
    # --warn is a fill or border on cards, never text: the 3:1 non-text floor applies.
    assert contrast(p["--warn"], p["--surface"]) >= LARGE_FLOOR
