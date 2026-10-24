import sqlite3

import pytest

from brandguard.storage import format_time, get_review, list_reviews, save_review

FINDINGS = [{"category": "Banned term", "severity": "High", "matched_text": "cheap"}]


def _save(db, status, comment=""):
    return save_review(db, brand_name="Test Brand", status=status, original_text="Cheap plan",
                       reviewed_text="Affordable plan", findings=FINDINGS, comment=comment)


def test_save_approved_and_retrieve(tmp_path):
    db = tmp_path / "t.db"
    info = _save(db, "Approved", "Looks good")
    record = get_review(db, info["id"])
    assert record["status"] == "Approved"
    assert record["comment"] == "Looks good"
    assert record["original_text"] == "Cheap plan"
    assert record["reviewed_text"] == "Affordable plan"
    assert record["findings"] == FINDINGS
    assert record["created_at"].endswith("+00:00")


def test_save_needs_changes(tmp_path):
    db = tmp_path / "t.db"
    info = _save(db, "Needs Changes", "Remove the claim")
    assert get_review(db, info["id"])["status"] == "Needs Changes"


def test_invalid_status_and_empty_text_rejected(tmp_path):
    db = tmp_path / "t.db"
    with pytest.raises(ValueError):
        _save(db, "Published")
    with pytest.raises(ValueError):
        save_review(db, brand_name="B", status="Approved", original_text=" ", reviewed_text="x", findings=[])


def test_list_newest_first(tmp_path):
    db = tmp_path / "t.db"
    first, second = _save(db, "Approved"), _save(db, "Needs Changes")
    rows = list_reviews(db)
    assert [r["id"] for r in rows] == [second["id"], first["id"]]
    assert rows[0]["findings_count"] == 1


def test_persists_across_new_connections(tmp_path):
    """Simulates an app restart: data is read back through a brand-new connection."""
    db = tmp_path / "t.db"
    info = _save(db, "Approved")
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 1
    assert get_review(db, info["id"]) is not None


def test_missing_review_returns_none(tmp_path):
    assert get_review(tmp_path / "t.db", 999) is None


def test_format_time_ist():
    assert format_time("2026-10-24T04:30:00+00:00") == "24 Oct 2026, 10:00 AM IST"
