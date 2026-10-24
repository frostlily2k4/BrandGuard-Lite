# BrandGuard Lite

**Team DREAMER · FutureStack Round 2**

BrandGuard Lite checks marketing content against your brand rules before publication. It explains each issue, suggests configured wording fixes in an editable copy, and records a human approval decision.

**Live app:** `<PUBLIC_APP_URL — add after deployment is tested>`
**Repository:** `<GITHUB_REPO_URL — add after the repo is created>`

---

## Problem

Organisations publish content written by employees, agencies, freelancers and AI tools. Brand rules and approved facts are often scattered, so content can drift in tone and terminology, use banned wording, or make promotional claims nobody has checked. BrandGuard Lite is our scoped first implementation of that brand-governance problem. It focuses on text checks, claim warnings, editable suggestions and human approval.

## Features (implemented in this version)

| Feature | What it does |
|---|---|
| Brand settings | Edit the brand name, tone guidance, preferred terms, banned terms and replacements, approved facts with sources, and required phrases. Saved as JSON. |
| Content review | Paste text (up to 10,000 characters). A sample text button is provided. |
| Banned-term check | Case-insensitive, whole-word regex matching. Flexible spacing is allowed. Each term is reported once with a count. |
| Claim warnings | Transparent patterns detect guarantees, 100% claims, "best/number one", quantified claims and certainty words. Each warning shows its evidence state. |
| Evidence state | Shows one of: possible supporting fact configured, no approved facts configured, or no matching fact found. Human verification is always required. |
| Required / preferred terms | Missing required phrases are marked **Review**. Missing preferred terms are marked **Info**. |
| Explained findings | Each finding shows a severity, the matched text, the reason, the related rule and a suggested next step. |
| Editable suggestion | Configured replacements are applied to a copy. The original is preserved, and terms with no replacement are flagged for a manual rewrite. |
| Re-check | Re-runs the checks on the edited version. |
| Human decision | Mark content Approved or Needs Changes, with an optional comment. Approving requires an explicit confirmation tick. |
| Review history | A SQLite record of each review: ID, time (IST), brand, status, original, reviewed version, findings and comment. Records can be filtered, opened and downloaded as JSON. |

Not included in this version: AI/LLM analysis, automated tone scoring, file upload, image/logo checks, accessibility checks and publishing integrations.

## Technology stack

Python 3.11+, Streamlit, SQLite (built into Python), JSON, regular expressions, pandas (installed with Streamlit) and pytest. No external AI API is used.

## Architecture

```
app.py                     Streamlit interface (4 tabs)
brandguard/rules.py        Load, clean and save brand rules (JSON)
brandguard/analyzer.py     Rule checks, claim patterns, evidence lookup -> Findings
brandguard/suggestions.py  Applies configured replacements to a copy
brandguard/storage.py      SQLite: save/list/get review decisions
brand_rules.json           Demo rules shipped with the app
data/                      Created at runtime: saved rules + brandguard.db (not in Git)
tests/                     Unit tests + automated UI workflow tests
```

Data flow: brand rules (JSON) and the pasted text go to `analyze_content()`, which produces findings. In parallel, `build_suggestion()` produces the editable copy. The human decision then goes to `save_review()` (SQLite), and the record appears in Review History.

## Run locally (Windows PowerShell)

```powershell
cd path\to\BrandGuard-Lite
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
streamlit run app.py
```

The app opens at http://localhost:8501.

- If `Activate.ps1` is blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again.
- `py -3.11` also works. Python 3.11 or newer is required.

## Run tests

```powershell
python -m pytest -v
```

The tests cover rules, analysis, suggestions, storage, and an automated end-to-end run of the app using Streamlit's `AppTest`.

## Deploy (Streamlit Community Cloud)

1. Push this folder to a **public** GitHub repository. `data/`, `.venv/` and secrets are excluded by `.gitignore`.
2. Sign in at share.streamlit.io with GitHub and choose **Create app**, then deploy from a GitHub repo.
3. Select the repository, the branch `main`, and the main file `app.py`.
4. Open **Advanced settings** and choose Python **3.12**, which is the version the tests were run on.
5. Click **Deploy**. Watch the build log for errors.
6. Open the public URL in a private/incognito window and run the full workflow.

No secrets are needed. Judges do not need any account.

**Storage note:** the cloud app's file system is temporary. Saved settings and review history can reset when the app restarts, sleeps or is redeployed.

## Limitations

- Checks are rule-based. They catch configured terms and common claim patterns, not every problem.
- A claim warning means "check this", not "this is false". Missing evidence means the claim is *not supported by configured sources*.
- Evidence matching uses simple keyword overlap. A reviewer must confirm that the fact really supports the claim.
- Words like "best" are flagged even in harmless phrases. A reviewer can ignore these.
- English only. Single shared workspace, with no user accounts.

## Responsible use and privacy

- A human makes every approval decision. The app never auto-approves or publishes.
- Original text is preserved, and suggestions are editable.
- No content is sent to any external AI service.
- Use sample or non-confidential content. Do not paste personal or client-confidential data.
- This is decision support, not a guarantee of factual accuracy or legal compliance.

## Attribution and AI-assistance disclosure

- Libraries: Streamlit, pandas, pytest (open source) and the Python standard library (`re`, `sqlite3`, `json`).
- Code was developed with the help of an AI coding assistant (Anthropic's Claude). The team reviewed, ran and tested it.
- Demo brand rules and sample text are fictional.
- `<Add any other disclosure the competition requires.>`
