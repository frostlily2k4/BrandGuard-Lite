"""Brand rules: default demo rules, cleaning, and JSON load/save.

Rule format (a plain dictionary so it is easy to store as JSON):

{
    "brand_name": "Dreamer Demo Brand",
    "tone": "Clear, helpful, honest and friendly.",
    "preferred_terms": ["easy to use", "customer support"],
    "banned_terms": [{"term": "guaranteed results", "replacement": "designed to help"}],
    "approved_facts": [{"fact": "...", "source": "..."}],
    "required_phrases": ["..."]
}
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path

# Demonstration data only. These are not claims about any real organisation.
DEFAULT_RULES: dict = {
    "brand_name": "Dreamer Demo Brand",
    "tone": "Clear, helpful, honest and friendly. Avoid hype and pressure tactics.",
    "preferred_terms": ["easy to use", "customer support"],
    "banned_terms": [
        {"term": "guaranteed results", "replacement": "designed to help"},
        {"term": "100% success", "replacement": ""},
        {"term": "cheap", "replacement": "affordable"},
    ],
    "approved_facts": [
        {
            "fact": "Customer support is available Monday to Friday, 9 AM to 6 PM IST.",
            "source": "Demo support policy (sample data)",
        }
    ],
    "required_phrases": [],
}

MAX_TERM_LENGTH = 200
MAX_LIST_ITEMS = 100


def _clean_text(value, max_len: int = 2000) -> str:
    """Turn any value into a trimmed string ('' for None/NaN)."""
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none"}:
        return ""
    return text[:max_len]


def _clean_list(values) -> list[str]:
    """Trim, drop blanks and remove case-insensitive duplicates, keeping order."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values or []:
        text = _clean_text(value, MAX_TERM_LENGTH)
        if text and text.lower() not in seen:
            seen.add(text.lower())
            result.append(text)
    return result[:MAX_LIST_ITEMS]


def normalize_rules(raw: dict | None) -> dict:
    """Return a complete, clean rules dictionary from possibly messy input."""
    raw = raw or {}
    rules = {
        "brand_name": _clean_text(raw.get("brand_name"), 100) or "My Brand",
        "tone": _clean_text(raw.get("tone"), 1000),
        "preferred_terms": _clean_list(raw.get("preferred_terms")),
        "required_phrases": _clean_list(raw.get("required_phrases")),
        "banned_terms": [],
        "approved_facts": [],
    }

    seen_terms: set[str] = set()
    for item in raw.get("banned_terms") or []:
        if isinstance(item, str):
            item = {"term": item, "replacement": ""}
        if not isinstance(item, dict):
            continue
        term = _clean_text(item.get("term"), MAX_TERM_LENGTH)
        if term and term.lower() not in seen_terms:
            seen_terms.add(term.lower())
            rules["banned_terms"].append(
                {"term": term, "replacement": _clean_text(item.get("replacement"), MAX_TERM_LENGTH)}
            )
    rules["banned_terms"] = rules["banned_terms"][:MAX_LIST_ITEMS]

    for item in raw.get("approved_facts") or []:
        if isinstance(item, str):
            item = {"fact": item, "source": ""}
        if not isinstance(item, dict):
            continue
        fact = _clean_text(item.get("fact"), 1000)
        if fact:
            rules["approved_facts"].append(
                {"fact": fact, "source": _clean_text(item.get("source"), 500)}
            )
    rules["approved_facts"] = rules["approved_facts"][:MAX_LIST_ITEMS]
    return rules


def default_rules() -> dict:
    """A fresh copy of the demo rules (safe to modify)."""
    return normalize_rules(copy.deepcopy(DEFAULT_RULES))


def load_rules(path: str | Path) -> dict:
    """Load rules from JSON. Falls back to demo rules if the file is missing or broken."""
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8") as handle:
            return normalize_rules(json.load(handle))
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
        return default_rules()


def save_rules(rules: dict, path: str | Path) -> dict:
    """Clean and save rules to JSON safely (write to a temp file, then replace)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = normalize_rules(rules)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(clean, handle, indent=2, ensure_ascii=False)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
    return clean
