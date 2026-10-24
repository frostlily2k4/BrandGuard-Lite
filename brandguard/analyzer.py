"""Content analysis: deterministic, explainable rule checks.

Everything here is plain Python + regular expressions. No external AI service
is called, so the same input and rules always give the same findings.

Severity labels:
    High   - a configured banned term was found
    Review - a claim or missing required phrase needs human checking
    Info   - preferred terminology may be missing
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

MAX_CONTENT_CHARS = 10_000
SEVERITY_ORDER = {"High": 0, "Review": 1, "Info": 2}

# Evidence states for claim findings (shown to the reviewer).
EVIDENCE_SOURCE_FOUND = "Possible supporting source configured"
EVIDENCE_NONE_CONFIGURED = "No approved facts configured"
EVIDENCE_NOT_FOUND = "No matching approved fact found"


@dataclass
class Finding:
    category: str
    severity: str
    matched_text: str
    explanation: str
    rule: str
    action: str
    count: int = 1
    evidence_status: str = ""
    evidence: list = field(default_factory=list)
    start: int = -1

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AnalysisResult:
    findings: list
    word_count: int
    char_count: int

    def counts(self) -> dict:
        totals = {"High": 0, "Review": 0, "Info": 0}
        for finding in self.findings:
            totals[finding.severity] = totals.get(finding.severity, 0) + 1
        return totals


def term_pattern(term: str) -> re.Pattern:
    """Case-insensitive pattern that matches a whole word or phrase.

    (?<!\\w) and (?!\\w) stop 'cheap' matching inside 'cheaper', and work for
    terms that start or end with symbols such as '100%' (where \\b fails).
    Any run of spaces in the term matches any run of whitespace in the text.
    """
    words = term.strip().split()
    body = r"\s+".join(re.escape(word) for word in words)
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE)


# Transparent claim heuristics: (label, explanation, regex).
CLAIM_PATTERNS = [
    (
        "Guarantee or absolute promise",
        "Guarantees and absolute promises are high-confidence claims that usually need clear support or conditions.",
        r"(?<!\w)guarantee(?:s|d|ing)?(?!\w)|(?<!\w)risk[- ]free(?!\w)|(?<!\w)(?:zero|no) risk(?!\w)|(?<!\w)never fails?(?!\w)",
    ),
    (
        "100% or total performance claim",
        "Claims of 100% success or total performance are hard to support and may mislead readers.",
        r"(?<!\w)100\s?%|(?<!\w)100\s+percent(?!\w)|(?<!\w)hundred percent(?!\w)",
    ),
    (
        "Ranking or 'best' claim",
        "Ranking and superlative claims (number one, best, leading) usually need a named, current source.",
        r"(?<!\w)(?:number\s+one|no\.\s?1|#\s?1)(?!\w)|(?<!\w)(?:the\s+)?best(?!\w)|(?<!\w)world[- ]class(?!\w)"
        r"|(?<!\w)industry[- ]leading(?!\w)|(?<!\w)unbeatable(?!\w)|(?<!\w)unmatched(?!\w)",
    ),
    (
        "Quantified performance claim",
        "Specific numbers (for example '3x faster' or '50% more') should be backed by a source.",
        r"(?<!\w)\d+(?:\.\d+)?\s?(?:%|x|times|percent)\s+(?:better|faster|more|cheaper|higher|lower|growth|increase|improvement|results)(?!\w)",
    ),
    (
        "Strong certainty claim",
        "Words like 'proven' or 'instant' imply certainty that may need evidence.",
        r"(?<!\w)(?:clinically\s+)?proven(?!\w)|(?<!\w)instant(?:ly)?(?!\w)|(?<!\w)miracle(?!\w)",
    ),
]
_COMPILED_CLAIMS = [(label, why, re.compile(rx, re.IGNORECASE)) for label, why, rx in CLAIM_PATTERNS]

_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "your", "you", "our", "are", "was", "from",
    "have", "has", "will", "can", "all", "any", "more", "than", "into", "about", "they",
    "them", "their", "its", "it's", "not", "but", "get", "now", "who", "what", "when",
}


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9%]+", text.lower())
    return {w for w in words if (len(w) > 3 or w.endswith("%") or w.isdigit()) and w not in _STOPWORDS}


def _sentence_around(text: str, start: int, end: int) -> str:
    """Return the sentence that contains text[start:end]."""
    left = max(text.rfind(ch, 0, start) for ch in ".!?\n")
    right_candidates = [i for i in (text.find(ch, end) for ch in ".!?\n") if i != -1]
    right = min(right_candidates) if right_candidates else len(text)
    return text[left + 1 : right + 1].strip()


def find_supporting_facts(sentence: str, approved_facts: list[dict]) -> list[dict]:
    """Very simple keyword overlap between a claim sentence and approved facts.

    This only suggests *possibly related* facts. A human must still decide
    whether the fact really supports the claim.
    """
    claim_words = _keywords(sentence)
    matches = []
    for fact in approved_facts:
        overlap = claim_words & _keywords(fact.get("fact", ""))
        if len(overlap) >= 2:
            matches.append({**fact, "shared_words": sorted(overlap)})
    return matches


def _check_banned_terms(text: str, rules: dict) -> tuple[list[Finding], list[tuple[int, int]]]:
    findings, spans = [], []
    for item in rules.get("banned_terms", []):
        term = item["term"]
        hits = list(term_pattern(term).finditer(text))
        if not hits:
            continue
        spans.extend((m.start(), m.end()) for m in hits)
        replacement = item.get("replacement", "")
        action = (
            f"Consider replacing it with \u201c{replacement}\u201d (see the suggested version below)."
            if replacement
            else "No replacement is configured. Rewrite this wording manually in the suggested version."
        )
        findings.append(
            Finding(
                category="Banned term",
                severity="High",
                matched_text=hits[0].group(0),
                explanation=f"\u201c{hits[0].group(0)}\u201d appears {len(hits)} time(s). It is on the brand's banned or discouraged list.",
                rule=f"Banned term: {term}",
                action=action,
                count=len(hits),
                start=hits[0].start(),
            )
        )
    return findings, spans


def _check_claims(text: str, rules: dict, skip_spans: list[tuple[int, int]]) -> list[Finding]:
    facts = rules.get("approved_facts", [])
    findings: list[Finding] = []
    seen: set[tuple[str, str]] = set()
    for label, why, pattern in _COMPILED_CLAIMS:
        for match in pattern.finditer(text):
            # Skip claims already reported inside a banned-term match (avoids double warnings).
            if any(s <= match.start() and match.end() <= e for s, e in skip_spans):
                continue
            sentence = _sentence_around(text, match.start(), match.end())
            key = (label, sentence.lower())
            if key in seen:
                continue
            seen.add(key)

            support = find_supporting_facts(sentence, facts)
            if support:
                status = EVIDENCE_SOURCE_FOUND
                explanation = (
                    f"{why} A possibly related approved fact is configured. "
                    "Check that it really supports this exact wording."
                )
            elif not facts:
                status = EVIDENCE_NONE_CONFIGURED
                explanation = (
                    f"{why} Potentially high-confidence claim detected. No supporting approved "
                    "source has been configured. Please verify the claim before publication."
                )
            else:
                status = EVIDENCE_NOT_FOUND
                explanation = (
                    f"{why} None of the configured approved facts appear to relate to this claim. "
                    "This does not mean the claim is false; it means support was not found."
                )
            findings.append(
                Finding(
                    category=f"Claim to verify: {label}",
                    severity="Review",
                    matched_text=match.group(0),
                    explanation=explanation,
                    rule="Promotional claims need approved supporting evidence",
                    action="Human verification required: confirm a source, soften the claim, or remove it.",
                    evidence_status=status,
                    evidence=support,
                    start=match.start(),
                )
            )
    return findings


def _check_required(text: str, rules: dict) -> list[Finding]:
    findings = []
    for phrase in rules.get("required_phrases", []):
        if not term_pattern(phrase).search(text):
            findings.append(
                Finding(
                    category="Required phrase missing",
                    severity="Review",
                    matched_text=phrase,
                    explanation=f"The required phrase \u201c{phrase}\u201d was not found.",
                    rule=f"Required phrase: {phrase}",
                    action="Add the phrase if it applies to this content, or note why it is not needed.",
                )
            )
    return findings


def _check_preferred(text: str, rules: dict) -> list[Finding]:
    findings = []
    for term in rules.get("preferred_terms", []):
        if not term_pattern(term).search(text):
            findings.append(
                Finding(
                    category="Preferred term not used",
                    severity="Info",
                    matched_text=term,
                    explanation=f"The preferred term \u201c{term}\u201d does not appear. This may be fine if it is not relevant here.",
                    rule=f"Preferred term: {term}",
                    action="Use the preferred wording where it fits naturally. No change is required.",
                )
            )
    return findings


def validate_content(text: str | None) -> str:
    """Return cleaned text or raise ValueError with a user-friendly message."""
    if text is None or not text.strip():
        raise ValueError("Paste some content to review. The text box is empty.")
    if len(text) > MAX_CONTENT_CHARS:
        raise ValueError(
            f"This content has {len(text):,} characters. The limit is {MAX_CONTENT_CHARS:,}. "
            "Split it into smaller parts and review each one."
        )
    return text


def analyze_content(text: str, rules: dict) -> AnalysisResult:
    """Run every check and return findings sorted by severity, then position."""
    text = validate_content(text)
    banned, spans = _check_banned_terms(text, rules)
    findings = banned + _check_claims(text, rules, spans) + _check_required(text, rules) + _check_preferred(text, rules)
    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.start if f.start >= 0 else 10**9))
    return AnalysisResult(
        findings=findings,
        word_count=len(re.findall(r"\S+", text)),
        char_count=len(text),
    )
