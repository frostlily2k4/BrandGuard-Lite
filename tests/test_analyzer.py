import pytest

from brandguard.analyzer import (
    EVIDENCE_NONE_CONFIGURED, EVIDENCE_NOT_FOUND, EVIDENCE_SOURCE_FOUND, MAX_CONTENT_CHARS, analyze_content,
)
from brandguard.rules import normalize_rules
from brandguard.suggestions import build_suggestion

RULES = normalize_rules({
    "brand_name": "Test Brand",
    "preferred_terms": ["easy to use"],
    "banned_terms": [
        {"term": "guaranteed results", "replacement": "designed to help"},
        {"term": "cheap", "replacement": "affordable"},
        {"term": "100% success", "replacement": ""},
    ],
    "approved_facts": [],
})


def by_category(result, prefix):
    return [f for f in result.findings if f.category.startswith(prefix)]


def test_clean_text_has_no_findings():
    result = analyze_content("Our planner is easy to use and helps teams plan their week.", RULES)
    assert result.findings == []


def test_banned_term_detected_with_rule_and_severity():
    result = analyze_content("Get guaranteed results today.", RULES)
    banned = by_category(result, "Banned term")
    assert len(banned) == 1
    assert banned[0].severity == "High"
    assert banned[0].rule == "Banned term: guaranteed results"
    assert banned[0].matched_text == "guaranteed results"


def test_case_insensitive_and_flexible_spacing():
    result = analyze_content("GUARANTEED   Results for all.", RULES)
    assert by_category(result, "Banned term")[0].matched_text == "GUARANTEED   Results"


def test_no_match_inside_longer_word():
    result = analyze_content("Cheaper plans are easy to use.", RULES)
    assert by_category(result, "Banned term") == []


def test_repeated_term_reported_once_with_count():
    result = analyze_content("Cheap, cheap, CHEAP. Easy to use.", RULES)
    banned = by_category(result, "Banned term")
    assert len(banned) == 1 and banned[0].count == 3


def test_percent_term_matches_despite_symbol():
    result = analyze_content("We promise 100% success.", RULES)
    assert by_category(result, "Banned term")[0].matched_text == "100% success"


def test_missing_preferred_term_is_info():
    result = analyze_content("A simple tool for teams.", RULES)
    info = by_category(result, "Preferred term")
    assert len(info) == 1 and info[0].severity == "Info"


def test_high_confidence_claim_flagged_without_evidence():
    result = analyze_content("We are the number one app and work 3x faster results.", RULES)
    claims = by_category(result, "Claim to verify")
    assert len(claims) >= 2
    assert all(c.severity == "Review" for c in claims)
    assert all(c.evidence_status == EVIDENCE_NONE_CONFIGURED for c in claims)
    assert "No supporting approved source has been configured" in claims[0].explanation
    assert "Human verification required" in claims[0].action


def test_claim_with_related_and_unrelated_facts():
    rules = normalize_rules({**RULES, "approved_facts": [
        {"fact": "Independent test in 2025 showed reports load 3x faster.", "source": "Lab report"},
    ]})
    related = by_category(analyze_content("Reports load 3x faster now.", rules), "Claim to verify")
    assert related[0].evidence_status == EVIDENCE_SOURCE_FOUND
    assert related[0].evidence[0]["source"] == "Lab report"
    unrelated = by_category(analyze_content("The best coffee in town.", rules), "Claim to verify")
    assert unrelated[0].evidence_status == EVIDENCE_NOT_FOUND
    assert "does not mean the claim is false" in unrelated[0].explanation


def test_claim_inside_banned_term_not_duplicated():
    result = analyze_content("Guaranteed results. Easy to use.", RULES)
    assert by_category(result, "Claim to verify") == []
    assert len(by_category(result, "Banned term")) == 1


def test_required_phrase_missing():
    rules = normalize_rules({**RULES, "required_phrases": ["Terms apply"]})
    result = analyze_content("Easy to use.", rules)
    assert by_category(result, "Required phrase")[0].severity == "Review"
    assert by_category(analyze_content("Easy to use. Terms apply.", rules), "Required phrase") == []


@pytest.mark.parametrize("text", ["", "   \n  ", None])
def test_empty_content_rejected(text):
    with pytest.raises(ValueError, match="empty"):
        analyze_content(text, RULES)


def test_overlong_content_rejected():
    with pytest.raises(ValueError, match="limit"):
        analyze_content("a" * (MAX_CONTENT_CHARS + 1), RULES)


def test_findings_sorted_by_severity():
    result = analyze_content("Cheap and the best.", RULES)
    order = {"High": 0, "Review": 1, "Info": 2}
    sev = [order[f.severity] for f in result.findings]
    assert sev == sorted(sev)


def test_replacement_suggestions_preserve_original_and_case():
    original = "Cheap plans with guaranteed results. 100% success!"
    suggested, changes = build_suggestion(original, RULES)
    assert suggested == "Affordable plans with designed to help. 100% success!"
    assert original == "Cheap plans with guaranteed results. 100% success!"  # untouched
    manual = [c for c in changes if not c["replacement"]]
    assert manual == [{"term": "100% success", "replacement": "", "count": 1}]
