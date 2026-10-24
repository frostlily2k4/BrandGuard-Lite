"""Build an editable suggested version using configured replacements only.

The original text is never modified. Terms without a configured replacement
are left untouched for the user to rewrite manually. Nothing is invented.
"""

from __future__ import annotations

from .analyzer import term_pattern


def _match_case(original: str, replacement: str) -> str:
    """Keep simple capitalisation: 'Cheap' -> 'Affordable', 'CHEAP' -> 'AFFORDABLE'."""
    if original.isupper() and len(original) > 1:
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def build_suggestion(text: str, rules: dict) -> tuple[str, list[dict]]:
    """Return (suggested_text, changes).

    changes: list of {"term", "replacement", "count"} for replacements applied.
    unresolved terms (banned, found, but no replacement) are listed with
    replacement "" and count, so the UI can ask for a manual rewrite.
    """
    suggested = text
    changes: list[dict] = []
    for item in rules.get("banned_terms", []):
        term, replacement = item["term"], item.get("replacement", "").strip()
        pattern = term_pattern(term)
        count = len(pattern.findall(suggested))
        if not count:
            continue
        if replacement:
            suggested = pattern.sub(lambda m: _match_case(m.group(0), replacement), suggested)
        changes.append({"term": term, "replacement": replacement, "count": count})
    return suggested, changes
