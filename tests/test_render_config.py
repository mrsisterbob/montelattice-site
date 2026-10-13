"""Pushes to master never deploy the live site: Render's auto-deploy is off in the blueprint, and the
README says deploys are a manual click. render.yaml is read as text (no YAML dependency).
Run: python -m pytest tests/test_render_config.py -q
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDER = (ROOT / "render.yaml").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")


def _keys(text):
    """Every `autoDeploy:` that is a real key (not inside a comment)."""
    return re.findall(r"^[ \t]*autoDeploy:[ \t]*(\S+)", text, re.M)


def test_auto_deploy_is_set_once_and_is_false():
    assert _keys(RENDER) == ["false"], _keys(RENDER)


def test_auto_deploy_true_appears_nowhere():
    assert not re.search(r"autoDeploy:\s*true", RENDER)


def test_the_comment_says_why_and_the_readme_says_deploys_are_manual():
    assert "2026-10-13" in RENDER and "manual click in Render" in RENDER
    assert "autoDeploy: false" in README and "Manual Deploy" in README
    assert "does not deploy" in README
