"""SQLite storage for human review decisions."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

VALID_STATUSES = ("Approved", "Needs Changes")
IST = timezone(timedelta(hours=5, minutes=30), name="IST")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    brand_name TEXT NOT NULL,
    status TEXT NOT NULL,
    original_text TEXT NOT NULL,
    reviewed_text TEXT NOT NULL,
    findings_json TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT ''
)
"""


def _connect(db_path: str | Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path) -> None:
    with closing(_connect(db_path)) as conn, conn:
        conn.execute(_SCHEMA)


def format_time(iso_utc: str) -> str:
    """'2026-10-24T10:00:00+00:00' -> '24 Oct 2026, 03:30 PM IST'."""
    try:
        return datetime.fromisoformat(iso_utc).astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")
    except (TypeError, ValueError):
        return str(iso_utc)


def save_review(
    db_path: str | Path,
    *,
    brand_name: str,
    status: str,
    original_text: str,
    reviewed_text: str,
    findings: list[dict],
    comment: str = "",
) -> dict:
    """Save one human decision. Returns {'id', 'created_at'}."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Status must be one of {VALID_STATUSES}.")
    if not original_text or not original_text.strip():
        raise ValueError("Original content is empty.")
    if not reviewed_text or not reviewed_text.strip():
        raise ValueError("Reviewed version is empty.")
    init_db(db_path)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(_connect(db_path)) as conn, conn:
        cursor = conn.execute(
            "INSERT INTO reviews (created_at, brand_name, status, original_text, reviewed_text, findings_json, comment)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                created_at,
                brand_name.strip() or "My Brand",
                status,
                original_text,
                reviewed_text,
                json.dumps(findings, ensure_ascii=False),
                (comment or "").strip()[:2000],
            ),
        )
        return {"id": cursor.lastrowid, "created_at": created_at}


def list_reviews(db_path: str | Path, limit: int = 200) -> list[dict]:
    """Newest first, without the long text fields."""
    init_db(db_path)
    with closing(_connect(db_path)) as conn:
        rows = conn.execute(
            "SELECT id, created_at, brand_name, status, original_text, findings_json FROM reviews"
            " ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    result = []
    for row in rows:
        preview = " ".join(row["original_text"].split())
        result.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "brand_name": row["brand_name"],
                "status": row["status"],
                "findings_count": len(json.loads(row["findings_json"] or "[]")),
                "preview": preview[:80] + ("\u2026" if len(preview) > 80 else ""),
            }
        )
    return result


def get_review(db_path: str | Path, review_id: int) -> dict | None:
    init_db(db_path)
    with closing(_connect(db_path)) as conn:
        row = conn.execute("SELECT * FROM reviews WHERE id = ?", (int(review_id),)).fetchone()
    if row is None:
        return None
    record = dict(row)
    record["findings"] = json.loads(record.pop("findings_json") or "[]")
    return record
