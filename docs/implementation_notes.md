# Implementation notes (for the Round 2 PDF)

## How rules are stored
`brand_rules.json` (demo, in the repo) seeds the app. When a user saves settings, a cleaned copy is written to
`data/brand_rules.json` (atomic write). Cleaning trims text, drops blank rows and removes case-insensitive duplicates.

## How content is analysed (`brandguard/analyzer.py`)
1. Validate: reject empty text and text over 10,000 characters.
2. Banned terms: each term becomes a regex `(?<!\w)term(?!\w)`, case-insensitive, with flexible whitespace.
   The regex never matches inside longer words ("cheap" does not match "cheaper") and works with symbols like "100%".
   One finding per term, with a count. Severity: High.
3. Claim patterns: five transparent regex groups (guarantees, 100% claims, ranking/best, quantified claims,
   certainty words). A claim inside an already-flagged banned term is skipped to avoid a double warning.
   Severity: Review.
4. Evidence lookup: the claim's sentence is compared to each approved fact by keyword overlap (2+ shared words).
   The result is one of three states: possible supporting fact configured / no approved facts configured /
   no matching fact found. Every claim is marked "Human verification required".
5. Required phrases missing: Review. Preferred terms missing: Info.
6. Findings are sorted by severity, then by position in the text.

## How suggestions are created (`brandguard/suggestions.py`)
Only replacements the user configured are applied, to a copy, with basic capitalisation matching.
Terms with no replacement are listed for a manual rewrite. Claims are never rewritten automatically.

## How decisions are stored (`brandguard/storage.py`)
SQLite table `reviews` stores: id, created_at (UTC ISO), brand_name, status (Approved | Needs Changes),
original_text, reviewed_text, findings_json and comment. Times are displayed in IST.

## Deployment
Streamlit Community Cloud from a public GitHub repo, Python 3.12. The file system is temporary, so the data
can reset on restart or redeploy.

## Test results (run 24 Oct 2026, in the build sandbox: Python 3.12.3, Streamlit 1.66.1)
31 passed, 0 failed (`python -m pytest -v`). This covers all 12 required test cases, plus:
- the automated UI workflow: sample, review, edit, approve-blocked-without-tick, approve, history;
- Needs Changes, plus persistence in a fresh app session;
- settings save and restore.

Re-run these on your laptop and on the deployed app before quoting results in the PDF.
