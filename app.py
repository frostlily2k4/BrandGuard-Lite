"""BrandGuard Lite - Team DREAMER (FutureStack Round 2).

Run locally:  streamlit run app.py
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from brandguard.analyzer import MAX_CONTENT_CHARS, analyze_content
from brandguard.rules import load_rules, normalize_rules, save_rules
from brandguard.storage import format_time, get_review, list_reviews, save_review
from brandguard.suggestions import build_suggestion

# ---------------------------------------------------------------- paths
APP_DIR = Path(__file__).parent
DATA_DIR = Path(os.environ.get("BRANDGUARD_DATA_DIR", APP_DIR / "data"))
RULES_PATH = DATA_DIR / "brand_rules.json"   # user-saved rules (not committed to Git)
SEED_RULES_PATH = APP_DIR / "brand_rules.json"  # demo rules shipped with the repo
DB_PATH = DATA_DIR / "brandguard.db"

SAMPLE_TEXT = (
    "Meet FlowDesk, the best project tool for small teams! Our app gives you guaranteed results "
    "and 100% success on every launch. Teams finish work 3x faster than before. "
    "It's cheap, simple, and our support team replies instantly."
)

st.set_page_config(page_title="BrandGuard Lite", page_icon="\U0001F6E1\uFE0F", layout="wide")

st.markdown(
    """
<style>
:root { --forest:#1B4332; --teal:#0F766E; --line:#DDE5E0; --muted:#52615A; }
.block-container { padding-top: 2rem; max-width: 1150px; }
.bg-hero h1 { color: var(--forest); font-size: 2.1rem; margin: 0 0 .2rem 0; letter-spacing: -.01em; }
.bg-hero p { color: var(--muted); margin: 0; font-size: 1.02rem; max-width: 70ch; }
.bg-hero .team { color: var(--teal); font-weight: 600; font-size: .9rem; margin-top: .35rem; }
.bg-finding { border: 1px solid var(--line); border-left-width: 5px; border-radius: 8px;
              padding: .8rem 1rem; margin-bottom: .7rem; background: #fff; }
.bg-finding.High { border-left-color: #B42318; }
.bg-finding.Review { border-left-color: #B54708; }
.bg-finding.Info { border-left-color: #0F766E; }
.bg-badge { display:inline-block; font-size:.78rem; font-weight:700; padding:.1rem .5rem;
            border-radius: 999px; margin-right:.45rem; }
.bg-badge.High { background:#FEF3F2; color:#B42318; }
.bg-badge.Review { background:#FFFAEB; color:#B54708; }
.bg-badge.Info { background:#F0FDFA; color:#0F766E; }
.bg-finding .cat { font-weight: 650; color: #1F2937; }
.bg-finding .row { margin-top:.3rem; font-size:.93rem; color:#374151; }
.bg-finding .row b { color: var(--forest); }
.bg-finding mark { background:#FDF6B2; padding:0 .15rem; border-radius:3px; }
.bg-status { display:inline-block; padding:.2rem .7rem; border-radius:999px; font-weight:700; }
.bg-status.Approved { background:#E7F6EC; color:#1B4332; }
.bg-status.Needs { background:#FFFAEB; color:#B54708; }
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- helpers
def esc(value) -> str:
    return html.escape(str(value or ""))


def current_rules() -> dict:
    if RULES_PATH.exists():
        return load_rules(RULES_PATH)
    return load_rules(SEED_RULES_PATH)  # falls back to built-in demo rules if missing


def init_state() -> None:
    defaults = {
        "draft": "",
        "result": None,
        "edited": "",
        "review_error": "",
        "save_error": "",
        "saved": None,
        "recheck": None,
        "rules_version": 0,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset_review() -> None:
    for key in ("result", "saved", "recheck"):
        st.session_state[key] = None
    st.session_state.edited = ""
    st.session_state.review_error = ""
    st.session_state.save_error = ""
    for key in ("decision", "confirm_review", "comment"):
        st.session_state.pop(key, None)


def cb_load_sample() -> None:
    reset_review()
    st.session_state.draft = SAMPLE_TEXT


def cb_clear() -> None:
    reset_review()
    st.session_state.draft = ""


def cb_run_review() -> None:
    reset_review()
    text = st.session_state.draft
    rules = current_rules()
    try:
        analysis = analyze_content(text, rules)
    except ValueError as err:
        st.session_state.review_error = str(err)
        return
    suggested, changes = build_suggestion(text, rules)
    st.session_state.result = {
        "original": text,
        "brand_name": rules["brand_name"],
        "tone": rules["tone"],
        "findings": [f.to_dict() for f in analysis.findings],
        "counts": analysis.counts(),
        "words": analysis.word_count,
        "changes": changes,
    }
    st.session_state.edited = suggested


def cb_reset_edit() -> None:
    result = st.session_state.result
    if result:
        st.session_state.edited, _ = build_suggestion(result["original"], current_rules())
        st.session_state.recheck = None


def cb_save_decision() -> None:
    st.session_state.save_error = ""
    result = st.session_state.result
    decision = st.session_state.get("decision")
    reviewed = st.session_state.get("edited", "")
    if not result:
        st.session_state.save_error = "Run a review first."
        return
    if decision not in ("Approved", "Needs Changes"):
        st.session_state.save_error = "Choose Approved or Needs Changes before saving."
        return
    if decision == "Approved" and not st.session_state.get("confirm_review"):
        st.session_state.save_error = "To approve, tick the box confirming you have checked the findings and the reviewed version."
        return
    if not reviewed.strip():
        st.session_state.save_error = "The reviewed version is empty. Add text or reset the suggestion."
        return
    try:
        info = save_review(
            DB_PATH,
            brand_name=result["brand_name"],
            status=decision,
            original_text=result["original"],
            reviewed_text=reviewed,
            findings=result["findings"],
            comment=st.session_state.get("comment", ""),
        )
    except Exception as err:  # show storage problems instead of crashing
        st.session_state.save_error = f"Could not save the decision: {err}"
        return
    st.session_state.saved = {**info, "status": decision}


def render_finding(f: dict) -> None:
    sev = f["severity"]
    rows = [
        f'<div class="row"><b>Found:</b> <mark>{esc(f["matched_text"])}</mark>'
        + (f' &nbsp;({f["count"]} times)' if f.get("count", 1) > 1 else "")
        + "</div>"
        if f["severity"] != "Info" and f["category"] != "Required phrase missing"
        else f'<div class="row"><b>Term:</b> {esc(f["matched_text"])}</div>',
        f'<div class="row"><b>Why:</b> {esc(f["explanation"])}</div>',
        f'<div class="row"><b>Rule:</b> {esc(f["rule"])}</div>',
    ]
    if f.get("evidence_status"):
        rows.append(f'<div class="row"><b>Evidence:</b> {esc(f["evidence_status"])}</div>')
        for ev in f.get("evidence", []):
            source = f' (source: {esc(ev.get("source"))})' if ev.get("source") else ""
            rows.append(f'<div class="row">&nbsp;&nbsp;\u2022 {esc(ev.get("fact"))}{source}</div>')
    rows.append(f'<div class="row"><b>Next step:</b> {esc(f["action"])}</div>')
    st.markdown(
        f'<div class="bg-finding {sev}"><span class="bg-badge {sev}">{sev}</span>'
        f'<span class="cat">{esc(f["category"])}</span>{"".join(rows)}</div>',
        unsafe_allow_html=True,
    )


def status_badge(status: str) -> str:
    css = "Approved" if status == "Approved" else "Needs"
    return f'<span class="bg-status {css}">{esc(status)}</span>'


# ---------------------------------------------------------------- page
init_state()

st.markdown(
    """
<div class="bg-hero">
  <h1>BrandGuard Lite</h1>
  <p>Paste your marketing content, review brand-rule findings, edit suggestions and record a human approval decision.</p>
  <div class="team">Team DREAMER &middot; FutureStack Round 2</div>
</div>
""",
    unsafe_allow_html=True,
)
st.write("")

tab_review, tab_settings, tab_history, tab_about = st.tabs(
    ["\U0001F4DD Review Content", "\u2699\uFE0F Brand Settings", "\U0001F4DA Review History", "\u2139\uFE0F About / Limitations"]
)

# ================================================================ REVIEW
with tab_review:
    rules = current_rules()
    st.caption(
        f"Checking against brand rules for **{rules['brand_name']}**. "
        "Change them in Brand Settings. Your text is checked inside this app only and is not sent to any AI service."
    )

    st.subheader("1. Paste content")
    st.text_area(
        "Marketing content",
        key="draft",
        height=170,
        placeholder="Paste a social post, email, product description or promotional paragraph\u2026",
        help=f"Up to {MAX_CONTENT_CHARS:,} characters. Use sample or non-confidential text.",
    )
    chars = len(st.session_state.draft)
    st.caption(f"{chars:,} / {MAX_CONTENT_CHARS:,} characters")

    c1, c2, c3 = st.columns([1.2, 1.2, 4])
    c1.button("Run review", type="primary", on_click=cb_run_review, width="stretch")
    c2.button("Load sample text", on_click=cb_load_sample, width="stretch")
    c3.button("Clear", on_click=cb_clear)

    if st.session_state.review_error:
        st.error(st.session_state.review_error)

    result = st.session_state.result
    if result is None:
        st.info("Load the sample text or paste your own, then select **Run review** to see findings.")
    else:
        if st.session_state.draft != result["original"]:
            st.warning("The content above has changed since this review. Select **Run review** again to update the findings.")

        st.subheader("2. Findings")
        counts = result["counts"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("High", counts["High"], help="Configured banned terms found")
        m2.metric("Review", counts["Review"], help="Claims or required phrases a human should check")
        m3.metric("Info", counts["Info"], help="Preferred terms not used")
        m4.metric("Words", result["words"])

        with st.expander("Tone guidance for this brand", expanded=False):
            st.write(result["tone"] or "No tone guidance has been configured.")
            st.caption(
                "Automated tone scoring is not implemented in this version. "
                "Please read the content against this guidance yourself."
            )

        if not result["findings"]:
            st.success("No configured rule was triggered. A human should still read the content before publishing.")
        for finding in result["findings"]:
            render_finding(finding)
        st.caption(
            "Findings come from configured rules and transparent wording patterns. "
            "They flag items to check; they do not prove a statement is true or false."
        )

        st.subheader("3. Suggested version (editable)")
        changes = result["changes"]
        applied = [c for c in changes if c["replacement"]]
        manual = [c for c in changes if not c["replacement"]]
        if applied:
            st.write(
                "Configured replacements applied: "
                + "; ".join(f"\u201c{c['term']}\u201d \u2192 \u201c{c['replacement']}\u201d" for c in applied)
                + "."
            )
        if manual:
            st.warning(
                "No replacement is configured for: "
                + ", ".join(f"\u201c{c['term']}\u201d" for c in manual)
                + ". Please rewrite these by hand in the box below."
            )
        if not changes:
            st.write("No configured replacements apply. You can still edit the text below.")
        st.caption("Check every change for meaning and factual accuracy. Claims are not rewritten automatically.")

        col_o, col_e = st.columns(2)
        with col_o:
            st.text_area("Original (kept unchanged)", value=result["original"], height=200, disabled=True)
        with col_e:
            st.text_area("Reviewed version", key="edited", height=200)

        b1, b2, _ = st.columns([1.3, 1.3, 3])
        if b1.button("Re-check reviewed version", width="stretch"):
            try:
                rc = analyze_content(st.session_state.edited, current_rules())
                st.session_state.recheck = rc.counts()
            except ValueError as err:
                st.session_state.recheck = {"error": str(err)}
        b2.button("Reset to suggestion", on_click=cb_reset_edit, width="stretch")
        rc = st.session_state.recheck
        if rc:
            if "error" in rc:
                st.error(rc["error"])
            else:
                st.info(
                    f"Reviewed version: {rc['High']} High, {rc['Review']} Review, {rc['Info']} Info finding(s) remaining."
                )

        st.subheader("4. Human decision")
        saved = st.session_state.saved
        if saved:
            st.markdown(
                f"Saved review **#{saved['id']}** as {status_badge(saved['status'])} on {esc(format_time(saved['created_at']))}.",
                unsafe_allow_html=True,
            )
            st.caption("Open Review History to see the full record. Nothing has been published.")
            st.button("Start a new review", on_click=cb_clear)
        else:
            st.radio(
                "Decision",
                ["Approved", "Needs Changes"],
                index=None,
                key="decision",
                horizontal=True,
            )
            st.checkbox(
                "I have checked the findings and the reviewed version (required to approve).",
                key="confirm_review",
            )
            st.text_area("Reviewer comment (optional)", key="comment", height=90, max_chars=2000)
            st.button("Save decision", type="primary", on_click=cb_save_decision)
            if st.session_state.save_error:
                st.error(st.session_state.save_error)
            st.caption("Saving records the decision only. BrandGuard Lite never publishes or auto-approves content.")

# ================================================================ SETTINGS
with tab_settings:
    rules = current_rules()
    v = st.session_state.rules_version
    st.subheader("Brand settings")
    st.caption("These rules are used by every review. Example rules are demonstration data only.")

    with st.form(f"settings_form_{v}"):
        brand_name = st.text_input("Brand or workspace name", value=rules["brand_name"], max_chars=100)
        tone = st.text_area("Preferred tone and writing style", value=rules["tone"], height=80)
        preferred = st.text_area(
            "Preferred terms (one per line)", value="\n".join(rules["preferred_terms"]), height=100
        )
        st.markdown("**Banned or discouraged terms, with optional replacements**")
        banned_df = st.data_editor(
            pd.DataFrame(rules["banned_terms"], columns=["term", "replacement"]),
            num_rows="dynamic",
            key=f"banned_{v}",
            width="stretch",
            column_config={
                "term": st.column_config.TextColumn("Banned term"),
                "replacement": st.column_config.TextColumn("Suggested replacement (optional)"),
            },
        )
        st.markdown("**Approved facts and their sources**")
        facts_df = st.data_editor(
            pd.DataFrame(rules["approved_facts"], columns=["fact", "source"]),
            num_rows="dynamic",
            key=f"facts_{v}",
            width="stretch",
            column_config={
                "fact": st.column_config.TextColumn("Approved fact"),
                "source": st.column_config.TextColumn("Source note"),
            },
        )
        required = st.text_area(
            "Required phrases (optional, one per line)", value="\n".join(rules["required_phrases"]), height=80
        )
        submitted = st.form_submit_button("Save brand settings", type="primary")

    if submitted:
        new_rules = normalize_rules(
            {
                "brand_name": brand_name,
                "tone": tone,
                "preferred_terms": preferred.splitlines(),
                "banned_terms": banned_df.to_dict("records"),
                "approved_facts": facts_df.to_dict("records"),
                "required_phrases": required.splitlines(),
            }
        )
        try:
            save_rules(new_rules, RULES_PATH)
            st.success("Brand settings saved. Run the review again to apply them.")
        except OSError as err:
            st.error(f"Could not save settings: {err}")

    if st.button("Restore demo rules"):
        try:
            save_rules(load_rules(SEED_RULES_PATH), RULES_PATH)
            st.session_state.rules_version += 1
            st.rerun()
        except OSError as err:
            st.error(f"Could not restore demo rules: {err}")

# ================================================================ HISTORY
with tab_history:
    st.subheader("Review history")
    try:
        reviews = list_reviews(DB_PATH)
    except Exception as err:
        reviews = []
        st.error(f"Could not read saved reviews: {err}")

    if not reviews:
        st.info("No saved reviews yet. Run a review and save a decision on the Review Content tab.")
    else:
        status_filter = st.radio("Show", ["All", "Approved", "Needs Changes"], horizontal=True, key="hist_filter")
        shown = [r for r in reviews if status_filter == "All" or r["status"] == status_filter]
        if not shown:
            st.info(f"No reviews with status {status_filter}.")
        else:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "ID": r["id"],
                            "Saved": format_time(r["created_at"]),
                            "Brand": r["brand_name"],
                            "Status": r["status"],
                            "Findings": r["findings_count"],
                            "Content": r["preview"],
                        }
                        for r in shown
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
            chosen = st.selectbox(
                "Open a review",
                [r["id"] for r in shown],
                format_func=lambda i: next(
                    f"#{r['id']} \u2013 {r['status']} \u2013 {format_time(r['created_at'])}" for r in shown if r["id"] == i
                ),
                key="hist_select",
            )
            record = get_review(DB_PATH, chosen)
            if record:
                st.markdown(
                    f"### Review #{record['id']} &nbsp; {status_badge(record['status'])}", unsafe_allow_html=True
                )
                st.write(f"**Saved:** {format_time(record['created_at'])}  \n**Brand:** {record['brand_name']}")
                st.write(f"**Reviewer comment:** {record['comment'] or 'No comment.'}")
                h1, h2 = st.columns(2)
                h1.text_area("Original content", value=record["original_text"], height=180, disabled=True, key=f"ho_{chosen}")
                h2.text_area("Reviewed version", value=record["reviewed_text"], height=180, disabled=True, key=f"hr_{chosen}")
                st.markdown(f"**Findings at review time ({len(record['findings'])})**")
                if not record["findings"]:
                    st.write("No findings were recorded.")
                for finding in record["findings"]:
                    render_finding(finding)
                st.download_button(
                    "Download this record (JSON)",
                    data=json.dumps(record, indent=2, ensure_ascii=False),
                    file_name=f"brandguard_review_{record['id']}.json",
                    mime="application/json",
                )

    st.caption(
        "Reviews are stored in a SQLite file on the server running this app. "
        "On free cloud hosting this file can be reset when the app restarts or is redeployed."
    )

# ================================================================ ABOUT
with tab_about:
    st.subheader("About BrandGuard Lite")
    st.markdown(
        """
BrandGuard Lite is a pre-publication checker for marketing content. It helps teams keep wording
consistent with their brand rules and spot promotional claims that need evidence, while a person
stays responsible for the final decision.

**How it works**
1. A manager saves brand rules: preferred terms, banned terms with replacements, tone guidance,
   approved facts and required phrases.
2. A writer pastes content and runs a review.
3. The app checks the text with Python rules and regular expressions and explains each finding.
4. Configured replacements are applied to an editable copy. The original is kept unchanged.
5. A reviewer marks the content **Approved** or **Needs Changes**, with an optional comment.
6. The decision, both versions and the findings are saved to Review History.

**Limitations**
- Checks are rule-based. They catch configured terms and common claim patterns, not every problem.
- Claim warnings mean "check this", not "this is false". Missing evidence means it is not supported by configured sources.
- Matching an approved fact uses simple keyword overlap; a reviewer must confirm it actually supports the claim.
- Automated tone scoring, image or logo checks, document upload and accessibility checks are not included in this version.
- Saved data may be reset on free hosting when the app restarts or redeploys.
- English text only has been considered.

**Privacy and responsible use**
- No external AI service is used. Content is processed inside this app.
- Use sample or non-confidential content. Do not paste personal or client-confidential material.
- The app never approves or publishes content by itself.
- This tool is decision support. It does not guarantee factual accuracy or legal compliance.

**Team:** Team DREAMER (FutureStack Round 2). Built with Python, Streamlit and SQLite.
Development was assisted by an AI coding assistant; see the README for the full disclosure.
"""
    )
