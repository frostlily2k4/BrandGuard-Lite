"""End-to-end UI test using Streamlit's built-in AppTest (no browser needed)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("BRANDGUARD_DATA_DIR", str(tmp_path))
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception
    return at


def button(at, label):
    return next(b for b in at.button if b.label == label)


def test_empty_content_shows_error(app):
    button(app, "Run review").click().run()
    assert any("empty" in e.value for e in app.error)


def test_full_workflow_approve_then_history(app):
    button(app, "Load sample text").click().run()
    button(app, "Run review").click().run()
    assert not app.exception
    page = " ".join(m.value for m in app.markdown)
    assert "Banned term" in page and "Claim to verify" in page

    edited = next(t for t in app.text_area if t.label == "Reviewed version")
    assert "designed to help" in edited.value and "affordable" in edited.value
    edited.set_value(edited.value.replace("100% success on every launch", "steady progress")).run()

    # Approving without the confirmation tick is blocked.
    app.radio(key="decision").set_value("Approved").run()
    button(app, "Save decision").click().run()
    assert any("tick the box" in e.value for e in app.error)

    app.checkbox(key="confirm_review").check().run()
    app.text_area(key="comment").set_value("Checked with marketing lead.").run()
    button(app, "Save decision").click().run()
    assert not app.exception
    assert any("Saved review **#1**" in m.value for m in app.markdown)

    # History shows the saved record with both versions and the comment.
    assert "steady progress" in next(t for t in app.text_area if t.label == "Reviewed version" and t.disabled).value
    page = " ".join(m.value for m in app.markdown)
    assert "Review #1" in page and "Checked with marketing lead." in page


def test_needs_changes_and_restart_persistence(tmp_path, monkeypatch):
    monkeypatch.setenv("BRANDGUARD_DATA_DIR", str(tmp_path))
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    button(at, "Load sample text").click().run()
    button(at, "Run review").click().run()
    at.radio(key="decision").set_value("Needs Changes").run()
    button(at, "Save decision").click().run()
    assert any("Saved review **#1**" in m.value for m in at.markdown)

    # A brand-new app session (like a restart) still sees the saved review.
    fresh = AppTest.from_file(APP, default_timeout=30)
    fresh.run()
    assert any("Needs Changes" in m.value for m in fresh.markdown if "Review #1" in m.value)


def test_settings_save_and_restore(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("BRANDGUARD_DATA_DIR", str(tmp_path))
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    at.text_input[0].set_value("Acme Test")
    next(t for t in at.text_area if t.label.startswith("Required phrases")).set_value("Terms apply")
    button(at, "Save brand settings").click().run()
    saved = json.loads((tmp_path / "brand_rules.json").read_text(encoding="utf-8"))
    assert saved["brand_name"] == "Acme Test" and saved["required_phrases"] == ["Terms apply"]
    button(at, "Restore demo rules").click().run()
    restored = json.loads((tmp_path / "brand_rules.json").read_text(encoding="utf-8"))
    assert restored["brand_name"] == "Dreamer Demo Brand"
