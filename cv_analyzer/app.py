import json
import re

import boto3
import streamlit as st

from bias_prompt import get_prompt
from simulation_prompt import SIMULATION_SYSTEM_PROMPT

# ── Bedrock client ─────────────────────────────────────────────────────────────
bedrock = boto3.client("bedrock-runtime")
MODEL_ID = "eu.anthropic.claude-sonnet-4-20250514-v1:0"


def call_bedrock(system_prompt: str, user_message: str, max_tokens: int = 6000) -> str:
    response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": user_message}]}],
        inferenceConfig={"maxTokens": max_tokens},
    )
    return response["output"]["message"]["content"][0]["text"]


# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Recruitment Bias Detector", layout="wide")

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
  /* Layout */
  .block-container { padding-top:1.8rem; max-width:1100px; }

  /* Typography — visible headers */
  h1 { font-size:1.7rem !important; font-weight:800 !important; color:#f1f5f9 !important; letter-spacing:-0.02em; }
  h2 { font-size:1.25rem !important; font-weight:700 !important; color:#e2e8f0 !important; }
  h3 { font-size:1.05rem !important; font-weight:700 !important; color:#cbd5e1 !important; }

  /* Section label — clear, bold section dividers */
  .section-label {
    font-size:0.78rem; font-weight:800; color:#94a3b8;
    text-transform:uppercase; letter-spacing:.12em;
    margin:32px 0 10px; border-bottom:1px solid #334155; padding-bottom:8px;
  }

  /* Pills */
  .pill {
    display:inline-block; padding:2px 10px; border-radius:20px;
    font-size:0.72rem; font-weight:700; color:#fff;
  }

  /* Overall score number */
  .score-num  { font-size:3.2rem; font-weight:900; line-height:1; }
  .score-bar  { background:#1e293b; border-radius:99px; height:6px; margin-top:6px; }
  .score-fill { height:6px; border-radius:99px; }

  /* Characteristic cards */
  .char-card  {
    background:#0f172a; border:1px solid #1e293b; border-radius:8px;
    padding:14px 10px; text-align:center;
  }
  .char-score { font-size:1.9rem; font-weight:900; line-height:1; }
  .char-name  { font-size:0.78rem; font-weight:600; color:#94a3b8; margin-top:4px; }

  /* Research stat box */
  .stat-box {
    background:#0f172a; border:1px solid #1e293b; border-radius:8px;
    padding:11px 16px; font-size:0.84rem; color:#94a3b8; margin-top:10px;
    border-left:3px solid #334155;
  }

  /* Takeaway box */
  .takeaway {
    background:#172554; border-left:3px solid #3b82f6;
    border-radius:0 6px 6px 0; padding:10px 14px;
    font-size:0.86rem; color:#bfdbfe; margin-top:10px; font-weight:500;
  }

  /* Finding severity border */
  .finding-wrap {
    border-radius:6px; padding:14px 16px; margin-bottom:12px;
    background:#0b1221;
  }
  .sev-Critical { border-left:4px solid #ef4444; }
  .sev-High     { border-left:4px solid #f97316; }
  .sev-Medium   { border-left:4px solid #eab308; }
  .sev-Low      { border-left:4px solid #22c55e; }

  /* Finding title */
  .finding-title { font-size:0.98rem; font-weight:700; color:#e2e8f0; margin-bottom:6px; }

  /* Quote */
  .evidence { font-style:italic; color:#94a3b8; font-size:0.85rem; margin-bottom:6px; }

  /* Guideline cards */
  .guideline {
    background:#0f172a; border:1px solid #1e293b; border-radius:8px;
    padding:14px 16px; margin-bottom:8px;
  }
  .gl-title { font-weight:700; font-size:0.95rem; color:#e2e8f0; margin-bottom:6px; }
  .gl-do    { color:#86efac; font-size:0.84rem; margin-bottom:2px; }
  .gl-dont  { color:#fca5a5; font-size:0.84rem; margin-bottom:2px; }
  .gl-why   { color:#64748b; font-size:0.79rem; margin-top:4px; font-style:italic; }

  /* Action cards */
  .action-card {
    background:#0f172a; border:1px solid #1e293b; border-radius:8px;
    padding:13px 16px; margin-bottom:8px;
  }
  .action-rank  { font-size:1.1rem; font-weight:900; color:#475569; }
  .action-title { font-size:0.96rem; font-weight:700; color:#e2e8f0; }
  .action-desc  { font-size:0.84rem; color:#64748b; margin-top:4px; }
</style>
""",
    unsafe_allow_html=True,
)

# ── Constants ──────────────────────────────────────────────────────────────────
RISK_COLOR = {
    "Critical": "#ef4444",
    "High": "#ef4444",
    "Elevated": "#f97316",
    "Moderate": "#eab308",
    "Medium": "#eab308",
    "Low": "#22c55e",
}
EFFORT_COLOR = {"Low": "#22c55e", "Medium": "#eab308", "High": "#ef4444"}
CHAR_META = {
    "gender": (
        "Gender",
        "Does this document use language or signals that disadvantage one gender?",
    ),
    "ethnicity_race": (
        "Ethnicity/Race",
        "Are there signals that could trigger unconscious ethnic or racial bias?",
    ),
    "age": ("Age", "Does this document advantage or disadvantage candidates by age?"),
    "socioeconomic": (
        "Socioeconomic",
        "Are class-based proxies used (institution prestige, unpaid work, etc.)?",
    ),
    "disability_neurodiversity": (
        "Disability",
        "Does this document assume a neurotypical or able-bodied candidate?",
    ),
    "religion_culture": (
        "Religion/Culture",
        "Are there implicit assumptions about availability or cultural norms?",
    ),
    "nationality": (
        "Nationality",
        "Are there signals that penalize certain national backgrounds unfairly?",
    ),
}


def score_color(s: int) -> str:
    if s >= 61:
        return "#ef4444"
    if s >= 41:
        return "#f97316"
    if s >= 21:
        return "#eab308"
    return "#22c55e"


def pill(text: str, color: str) -> str:
    return f'<span class="pill" style="background:{color}">{text}</span>'


def gauge(score: int, label: str = ""):
    c = score_color(score)
    st.markdown(
        f'<div style="text-align:center">'
        f'<div class="score-num" style="color:{c}">{score}</div>'
        f"{'<div class=char-name>' + label + '</div>' if label else ''}"
        f'<div class="score-bar"><div class="score-fill" style="width:{score}%;background:{c}"></div></div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def takeaway(text: str):
    st.markdown(f'<div class="takeaway">{text}</div>', unsafe_allow_html=True)


def section_label(text: str):
    st.markdown(f'<div class="section-label">{text}</div>', unsafe_allow_html=True)


# ── Analysis ───────────────────────────────────────────────────────────────────
def analyze(text: str, doc_type: str, perspective: str) -> dict:
    msg = f"document_type: {doc_type}\nperspective: {perspective}\n\n---\n\n{text}"
    raw = call_bedrock(get_prompt(doc_type, perspective), msg)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    return json.loads(match.group() if match else raw)


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Settings")
    doc_type_label = st.radio("Document type", ["CV / Resume", "Job Description"])
    doc_type = "cv" if doc_type_label == "CV / Resume" else "job_description"

    if doc_type == "cv":
        persp_label = st.radio(
            "Analysis perspective",
            ["Candidate — what can I improve?", "Company — what are we overlooking?"],
        )
        perspective = "candidate" if persp_label.startswith("Candidate") else "company"
    else:
        perspective = "company"
        st.info("Job description analysis is always from the company perspective.")

    st.divider()
    st.caption(
        "This tool flags only documented, research-backed bias signals. "
        "Legitimate requirements (location, genuine language needs) are not flagged."
    )

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("## Recruitment Bias Detector")

tab_analyze, tab_simulate = st.tabs(
    ["📄 Single Document Analysis", "⚖️ CV Bias Simulation"]
)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — existing single document analysis
# ═══════════════════════════════════════════════════════════════════════════════
with tab_analyze:
    if perspective == "candidate":
        st.caption(
            "Candidate view — shows what you can rewrite to reduce screener bias. Will never suggest changing your name, background, or identity."
        )
    elif doc_type == "cv":
        st.caption(
            "Company view — shows what your screening process risks penalising unfairly, with recruiter guidelines for AI-assisted hiring."
        )
    else:
        st.caption(
            "Company view — shows who your job description is accidentally excluding and how to fix it."
        )

    doc_text = st.text_area(
        "Paste document",
        height=240,
        placeholder="Paste a CV or job description here…",
        label_visibility="collapsed",
    )
    run = st.button(
        "Analyse for bias",
        type="primary",
        use_container_width=True,
        disabled=not doc_text,
    )

    # ── Results ────────────────────────────────────────────────────────────────────
    if run:
        with st.spinner("Analysing…"):
            try:
                r = analyze(doc_text, doc_type, perspective)
            except Exception as exc:
                st.error(f"Analysis failed: {exc}")
                st.stop()

        brs = r.get("overall_bias_risk_score", 0)
        risk = r.get("risk_level", "Unknown")
        rc = RISK_COLOR.get(risk, "#64748b")
        exsum = r.get("executive_summary", {})

        # ── SECTION 1: Overall verdict ─────────────────────────────────────
        st.divider()
        left, right = st.columns([1, 3], gap="large")
        with left:
            gauge(brs)
            st.markdown(
                f"<div style='text-align:center;margin-top:8px'>"
                f"{pill(risk + ' Bias Risk', rc)}</div>",
                unsafe_allow_html=True,
            )
        with right:
            st.markdown(f"### {exsum.get('headline', '')}")
            st.write(exsum.get("body", ""))
            if exsum.get("top_stat"):
                st.markdown(
                    f'<div class="stat-box">Research context: {exsum["top_stat"]}</div>',
                    unsafe_allow_html=True,
                )

        # ── SECTION 2: Where is the bias? ─────────────────────────────────
        st.divider()
        section_label("Where is the bias? — Bias risk by protected characteristic")
        chars = r.get("protected_characteristic_scores", {})

        cols = st.columns(len(chars))
        for col, (key, val) in zip(cols, chars.items()):
            v = val.get("score", 0) if isinstance(val, dict) else int(val)
            lbl = val.get("label", "") if isinstance(val, dict) else ""
            c = score_color(v)
            display_name, _ = CHAR_META.get(key, (key, ""))
            with col:
                st.markdown(
                    f'<div class="char-card">'
                    f'<div class="char-score" style="color:{c}">{v}</div>'
                    f'<div class="char-name">{display_name}</div>'
                    f'<div style="margin-top:6px">{pill(lbl, RISK_COLOR.get(lbl, "#334155"))}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )

        with st.expander("Why these scores? Expand to see what drives each dimension"):
            for key, val in chars.items():
                v = val.get("score", 0) if isinstance(val, dict) else int(val)
                lbl = val.get("label", "") if isinstance(val, dict) else ""
                why = val.get("why", "") if isinstance(val, dict) else ""
                display_name, description = CHAR_META.get(key, (key, ""))
                c = score_color(v)
                if v > 0:
                    c2a, c2b = st.columns([1, 5])
                    with c2a:
                        st.markdown(
                            f'<div style="text-align:center;padding-top:6px">'
                            f'<span style="font-size:1.4rem;font-weight:900;color:{c}">{v}</span><br>'
                            f"{pill(lbl, RISK_COLOR.get(lbl, '#334155'))}</div>",
                            unsafe_allow_html=True,
                        )
                    with c2b:
                        st.markdown(f"**{display_name}** — {description}")
                        if why:
                            st.caption(why)
                    st.markdown("---")

        # ── SECTION 3: Top actions ─────────────────────────────────────────
        actions = r.get("top_5_actions", [])
        if actions:
            st.divider()
            section_label("Top actions — prioritised by impact")
            for a in actions:
                effort = a.get("effort", "")
                impact = a.get("impact", "")
                ec = EFFORT_COLOR.get(effort, "#64748b")
                ic = RISK_COLOR.get(impact, "#22c55e")
                st.markdown(
                    f'<div class="action-card">'
                    f'<span class="action-rank">#{a.get("rank", "")}</span> &nbsp;'
                    f'<span class="action-title">{a.get("title", "")}</span> &nbsp;'
                    f"{pill('effort ' + effort, ec)} &nbsp;"
                    f"{pill('impact ' + impact, ic)}"
                    f'<div class="action-desc">{a.get("description", "")}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )

        # ── SECTION 4: Detailed findings ──────────────────────────────────
        sections = r.get("sections", [])
        if sections:
            st.divider()
            section_label(
                "Detailed findings — expand each section for evidence and rewrites"
            )
            for sec in sections:
                worst = sec.get("severity_summary", "Low")
                sc = RISK_COLOR.get(worst, "#64748b")
                icon = sec.get("section_icon", "")
                n = sec.get("finding_count", len(sec.get("findings", [])))
                with st.expander(
                    f"{icon}  {sec.get('section_name', '')}   ·   {worst}   ·   {n} finding{'s' if n != 1 else ''}",
                    expanded=worst in ("Critical", "High"),
                ):
                    st.caption(sec.get("section_description", ""))
                    st.markdown("")

                    for finding in sec.get("findings", []):
                        sev = finding.get("severity", "Low")
                        fc = RISK_COLOR.get(sev, "#64748b")
                        cat = finding.get("category", "").replace("_", " ")

                        st.markdown(
                            f'<div class="finding-wrap sev-{sev}">'
                            f'<div class="finding-title">{finding.get("title", "")}</div>'
                            f'<div style="margin-bottom:8px">'
                            f"{pill(sev, fc)} &nbsp;"
                            f"{pill(cat, '#334155')} &nbsp;"
                            f'<span style="color:#475569;font-size:0.76rem">confidence {finding.get("confidence", 0)}%</span>'
                            f"</div>"
                            f'<div class="evidence">"{finding.get("evidence", "")}"</div>'
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                        st.markdown(finding.get("explanation", ""))

                        a1, a2 = st.columns([3, 1])
                        with a1:
                            st.markdown(f"**Action:** {finding.get('action', '')}")
                            if finding.get("research_hook"):
                                st.caption(f"Research: {finding['research_hook']}")
                            takeaway(finding.get("takeaway", ""))
                        with a2:
                            st.caption(finding.get("severity_reason", ""))

                        st.markdown("")

                    if sec.get("section_takeaway"):
                        takeaway(sec["section_takeaway"])

        # ── SECTION 4: Meta-bias awareness (candidate only) ───────────────
        meta = r.get("meta_bias_awareness", [])
        if meta and perspective == "candidate":
            st.divider()
            section_label(
                "Meta-bias awareness — signals you cannot change, but should know about"
            )
            st.caption(
                "These are inferences a biased screener or AI system may make from your CV "
                "before ever reading your experience. You cannot — and should not — change your "
                "identity. But knowing these assumptions exist lets you choose how to respond."
            )
            for m in meta:
                sev = m.get("severity", "Medium")
                sc = RISK_COLOR.get(sev, "#64748b")
                icon = m.get("icon", "")
                with st.expander(
                    f"{icon}  {m.get('title', '')}  ·  {sev}",
                    expanded=sev == "High",
                ):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(
                            f"**What a biased screener may assume:** "
                            f"{m.get('what_a_biased_screener_may_assume', '')}"
                        )
                        if m.get("documented_impact"):
                            st.caption(f"Evidence: {m['documented_impact']}")
                        st.markdown(
                            f'<div style="background:#1c1917;border-left:3px solid #78350f;'
                            f"border-radius:0 6px 6px 0;padding:9px 14px;margin-top:8px;"
                            f'font-size:0.85rem;color:#fcd34d">'
                            f"You cannot change: {m.get('you_cannot_change', '')}</div>",
                            unsafe_allow_html=True,
                        )
                        if m.get("you_can_choose_to"):
                            takeaway(f"You can choose to: {m['you_can_choose_to']}")
                    with c2:
                        st.markdown(
                            f'<div style="text-align:center;padding-top:8px">'
                            f"{pill(sev, sc)}<br>"
                            f'<span style="font-size:0.7rem;color:#64748b;margin-top:4px;display:block">'
                            f"{m.get('signal_type', '').replace('_', ' ')}</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

        # ── SECTION 5: Recruiter & AI Screening Guidelines (company only) ──
        guidelines = r.get("screening_guidelines", [])
        if guidelines and perspective == "company":
            st.divider()
            section_label(
                "Recruiter & AI screening guidelines — what to do and what to stop"
            )
            st.caption(
                "These are concrete process instructions for recruiters and anyone configuring "
                "AI-assisted screening tools based on the signals found in this document."
            )
            for g in guidelines:
                icon = g.get("icon", "")
                applies = g.get("applies_to", "").replace("_", " ")
                st.markdown(
                    f'<div class="guideline">'
                    f'<div class="gl-title">{icon} {g.get("title", "")} '
                    f'<span style="font-size:0.7rem;color:#475569;font-weight:400"> · {applies}</span></div>'
                    f'<div class="gl-do">Do: {g.get("what_to_do", "")}</div>'
                    f'<div class="gl-dont">Stop: {g.get("what_not_to_do", "")}</div>'
                    f'<div class="gl-why">{g.get("why_it_matters", "")}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )

        # ── SECTION 6: Legal risks (company only) ─────────────────────────
        legal = [
            lg for lg in r.get("legal_risk_flags", []) if lg.get("quote", "").strip()
        ]
        if legal and perspective == "company":
            st.divider()
            section_label("Legal risk flags")
            for lg in legal:
                with st.expander(
                    f"{lg.get('title', '')} — {lg.get('jurisdiction', '')} · {lg.get('law_reference', '')}",
                    expanded=True,
                ):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.markdown(f'Flagged phrase: *"{lg.get("quote", "")}"*')
                        st.markdown(f"{lg.get('risk', '')}")
                        st.markdown(f"**Suggested rewrite:** {lg.get('rewrite', '')}")
                        takeaway(lg.get("takeaway", ""))
                    with c2:
                        st.markdown(
                            f"{pill(lg.get('jurisdiction', ''), '#7c3aed')} &nbsp;"
                            f"{pill(lg.get('law_reference', ''), '#334155')}",
                            unsafe_allow_html=True,
                        )

        # ── SECTION 7: Raw JSON ────────────────────────────────────────────
        with st.expander("Raw JSON response"):
            st.json(r)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — CV Bias Simulation
# ═══════════════════════════════════════════════════════════════════════════════
with tab_simulate:
    st.caption(
        "Upload two CVs and a job description. The AI simulates how an LLM-based ATS would score them — and exposes whether any gap is merit-driven or bias-driven."
    )

    sim_col1, sim_col2 = st.columns(2)
    with sim_col1:
        cv_a = st.text_area(
            "Candidate A — CV",
            height=220,
            placeholder="Paste CV for Candidate A here…",
            key="cv_a",
        )
    with sim_col2:
        cv_b = st.text_area(
            "Candidate B — CV",
            height=220,
            placeholder="Paste CV for Candidate B here…",
            key="cv_b",
        )

    jd_text = st.text_area(
        "Job Description",
        height=180,
        placeholder="Paste the job description here…",
        key="sim_jd",
    )

    sim_run = st.button(
        "Run Bias Simulation",
        type="primary",
        use_container_width=True,
        disabled=not (cv_a and cv_b and jd_text),
        key="sim_run",
    )

    if sim_run:
        with st.spinner("Simulating ATS scoring and bias gap analysis…"):
            try:
                msg = f"JOB DESCRIPTION:\n{jd_text}\n\n---\n\nCANDIDATE A CV:\n{cv_a}\n\n---\n\nCANDIDATE B CV:\n{cv_b}"
                raw = call_bedrock(SIMULATION_SYSTEM_PROMPT, msg)
                match = re.search(r"\{.*\}", raw, re.DOTALL)
                sim = json.loads(match.group() if match else raw)
            except Exception as exc:
                st.error(f"Simulation failed: {exc}")
                st.stop()

        # ── ACT 1 — THE SETUP ─────────────────────────────────────────
        scores = sim.get("candidate_scores", {})
        ca = scores.get("candidate_a", {})
        cb = scores.get("candidate_b", {})
        ranking = sim.get("ranking_simulation", {})
        gap_info = sim.get("gap_analysis", {})
        wc = sim.get("what_changed", {})
        fix = sim.get("system_fix", {})
        verdict = sim.get("simulation_verdict", {})

        METRICS = [
            "technical_match",
            "language_framing",
            "prestige_signal",
            "profile_coherence",
        ]
        METRIC_LABELS = {
            "technical_match": "Technical Match",
            "language_framing": "Language & Framing",
            "prestige_signal": "Prestige Signal",
            "profile_coherence": "Profile Coherence",
        }

        st.divider()
        st.markdown(
            '<div style="text-align:center;padding:24px 0 8px">'
            '<div style="font-size:1.3rem;font-weight:800;color:#e2e8f0">Two candidates applied for the same role.</div>'
            '<div style="font-size:0.95rem;color:#64748b;margin-top:6px">Here is what they both brought to the table.</div>'
            "</div>",
            unsafe_allow_html=True,
        )

        # Qualifications side by side — no names yet
        q1, q2 = st.columns(2)
        jd_summary = sim.get("job_description_summary", "")
        rubric = sim.get("scoring_rubric", {})
        for col, cand, label in [(q1, ca, "Candidate A"), (q2, cb, "Candidate B")]:
            with col:
                st.markdown(
                    f'<div style="background:#0f172a;border:1px solid #1e293b;border-radius:8px;padding:16px 18px">'
                    f'<div style="font-size:0.72rem;font-weight:800;color:#64748b;text-transform:uppercase;'
                    f'letter-spacing:0.1em;margin-bottom:10px">{label}</div>'
                    f'<div style="font-size:0.85rem;color:#cbd5e1;line-height:1.7">'
                    f"<b>Skills match:</b> {cand.get('technical_match', {}).get('score', '—')}/100<br>"
                    f"<b>Writing style:</b> {cand.get('language_framing', {}).get('score', '—')}/100<br>"
                    f"<b>Employer background:</b> {cand.get('prestige_signal', {}).get('score', '—')}/100<br>"
                    f"<b>Career consistency:</b> {cand.get('profile_coherence', {}).get('score', '—')}/100"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )

        # ── ACT 2 — THE SYSTEM RUNS ────────────────────────────────────
        st.markdown(
            '<div style="text-align:center;padding:32px 0 8px">'
            '<div style="font-size:1.3rem;font-weight:800;color:#e2e8f0">An LLM-based ATS scored both CVs against the job description.</div>'
            '<div style="font-size:0.95rem;color:#64748b;margin-top:6px">Watch where the gap opens.</div>'
            "</div>",
            unsafe_allow_html=True,
        )

        # Score pipeline — metric by metric, gap visualised
        for metric in METRICS:
            ma = ca.get(metric, {})
            mb = cb.get(metric, {})
            sa = ma.get("score", 0) if isinstance(ma, dict) else 0
            sb = mb.get(metric, {}).get("score", 0) if isinstance(mb, dict) else 0
            sb = mb.get("score", 0) if isinstance(mb, dict) else 0
            delta = abs(sa - sb)
            bar_color_a = "#3b82f6"
            bar_color_b = "#f59e0b"

            st.markdown(
                f'<div style="background:#0f172a;border:1px solid #1e293b;border-radius:8px;'
                f'padding:12px 18px;margin-bottom:8px">'
                f'<div style="font-size:0.72rem;font-weight:800;color:#64748b;text-transform:uppercase;'
                f'letter-spacing:0.1em;margin-bottom:10px">{METRIC_LABELS[metric]}</div>'
                f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:6px">'
                f'<span style="font-size:0.78rem;color:#94a3b8;width:80px">Candidate A</span>'
                f'<div style="flex:1;background:#1e293b;border-radius:99px;height:8px">'
                f'<div style="width:{sa}%;background:{bar_color_a};height:8px;border-radius:99px"></div></div>'
                f'<span style="font-size:0.9rem;font-weight:700;color:{bar_color_a};width:32px;text-align:right">{sa}</span>'
                f"</div>"
                f'<div style="display:flex;align-items:center;gap:12px">'
                f'<span style="font-size:0.78rem;color:#94a3b8;width:80px">Candidate B</span>'
                f'<div style="flex:1;background:#1e293b;border-radius:99px;height:8px">'
                f'<div style="width:{sb}%;background:{bar_color_b};height:8px;border-radius:99px"></div></div>'
                f'<span style="font-size:0.9rem;font-weight:700;color:{bar_color_b};width:32px;text-align:right">{sb}</span>'
                f"</div>"
                f"{'<div style=margin-top:8px><span style=font-size:0.75rem;color:#475569>gap: ' + str(delta) + ' pts</span></div>' if delta > 0 else ''}"
                f"</div>",
                unsafe_allow_html=True,
            )

        # ── ACT 3 — THE OUTCOME ────────────────────────────────────────
        st.markdown(
            '<div style="text-align:center;padding:32px 0 8px">'
            '<div style="font-size:1.3rem;font-weight:800;color:#e2e8f0">Here is where each candidate ended up in a pool of 500.</div>'
            "</div>",
            unsafe_allow_html=True,
        )

        rank_a = ranking.get("candidate_a_rank", "—")
        rank_b = ranking.get("candidate_b_rank", "—")
        total_a = ca.get("total_score", 0)
        total_b = cb.get("total_score", 0)

        o1, o2 = st.columns(2)
        for col, total, rank, label, color in [
            (o1, total_a, rank_a, "Candidate A", "#3b82f6"),
            (o2, total_b, rank_b, "Candidate B", "#f59e0b"),
        ]:
            with col:
                st.markdown(
                    f'<div style="background:#0f172a;border:1px solid #1e293b;border-top:3px solid {color};'
                    f'border-radius:0 0 8px 8px;padding:18px;text-align:center">'
                    f'<div style="font-size:0.72rem;font-weight:800;color:#64748b;text-transform:uppercase;'
                    f'letter-spacing:0.1em;margin-bottom:8px">{label}</div>'
                    f'<div style="font-size:2.4rem;font-weight:900;color:{color}">{total}</div>'
                    f'<div style="font-size:0.78rem;color:#64748b;margin-top:4px">total score · {rank}</div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.markdown(
            '<div style="text-align:center;padding:12px 0 4px;font-size:0.85rem;color:#475569">'
            "The top 5 go to the recruiter. Everyone else is never seen."
            "</div>",
            unsafe_allow_html=True,
        )

        # ── ACT 4 — THE QUESTION ───────────────────────────────────────
        st.divider()
        st.markdown(
            '<div style="text-align:center;padding:20px 0 16px">'
            '<div style="font-size:1.2rem;font-weight:800;color:#e2e8f0">What explains the difference?</div>'
            "</div>",
            unsafe_allow_html=True,
        )

        # ── ACT 5 — THE EVIDENCE (user-triggered) ─────────────────────
        with st.expander("Show me the mechanism →", expanded=False):
            # Now reveal the names
            name_a = ca.get("name", "Candidate A")
            name_b = cb.get("name", "Candidate B")
            changed_var = wc.get("variable_modified", "—")
            sig_a = wc.get("candidate_a_signal", "—")
            sig_b = wc.get("candidate_b_signal", "—")

            st.markdown(
                f'<div style="background:#0f172a;border:1px solid #334155;border-radius:8px;'
                f'padding:16px 20px;margin-bottom:16px">'
                f'<div style="font-size:0.72rem;font-weight:800;color:#64748b;text-transform:uppercase;'
                f'letter-spacing:0.1em;margin-bottom:10px">The candidates</div>'
                f'<div style="display:flex;gap:32px">'
                f'<div><span style="color:#3b82f6;font-weight:700">{name_a}</span>'
                f'<div style="font-size:0.82rem;color:#64748b;margin-top:2px">{sig_a}</div></div>'
                f'<div><span style="color:#f59e0b;font-weight:700">{name_b}</span>'
                f'<div style="font-size:0.82rem;color:#64748b;margin-top:2px">{sig_b}</div></div>'
                f"</div>"
                f'<div style="margin-top:10px;font-size:0.84rem;color:#94a3b8">'
                f'Variable that changed: <b style="color:#e2e8f0">{changed_var}</b> · '
                f'Qualification difference: <b style="color:#e2e8f0">{wc.get("qualification_difference", "—")}</b>'
                f"</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

            # Per-metric evidence — what each candidate wrote, how the system scored it
            for metric in METRICS:
                ma = ca.get(metric, {})
                mb = cb.get(metric, {})
                sa = ma.get("score", 0) if isinstance(ma, dict) else 0
                sb = mb.get("score", 0) if isinstance(mb, dict) else 0
                delta = sa - sb

                # Find matching gap entry
                gap_entry = next(
                    (
                        g
                        for g in gap_info.get("metric_gaps", [])
                        if g.get("metric") == metric
                    ),
                    {},
                )
                plain = gap_entry.get("plain_english", "")

                st.markdown(
                    f'<div style="background:#0b1221;border:1px solid #1e293b;border-radius:8px;'
                    f'padding:14px 18px;margin-bottom:10px">'
                    f'<div style="font-size:0.78rem;font-weight:800;color:#64748b;text-transform:uppercase;'
                    f'letter-spacing:0.1em;margin-bottom:10px">{METRIC_LABELS[metric]}'
                    f'<span style="font-weight:400;color:#475569;margin-left:12px">Δ {delta:+d} pts</span></div>'
                    f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:10px">'
                    f'<div style="background:#0f172a;border-radius:6px;padding:10px 12px">'
                    f'<div style="font-size:0.7rem;color:#3b82f6;font-weight:700;margin-bottom:4px">{name_a} · {sa}</div>'
                    f'<div style="font-size:0.82rem;color:#94a3b8;font-style:italic">"{ma.get("evidence", "—") if isinstance(ma, dict) else "—"}"</div>'
                    f"</div>"
                    f'<div style="background:#0f172a;border-radius:6px;padding:10px 12px">'
                    f'<div style="font-size:0.7rem;color:#f59e0b;font-weight:700;margin-bottom:4px">{name_b} · {sb}</div>'
                    f'<div style="font-size:0.82rem;color:#94a3b8;font-style:italic">"{mb.get("evidence", "—") if isinstance(mb, dict) else "—"}"</div>'
                    f"</div></div>"
                    f"{'<div style=font-size:0.82rem;color:#64748b>' + plain + '</div>' if plain else ''}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        # ── ACT 6 — THE IMPLICATION (user-triggered) ───────────────────
        with st.expander(
            "What would need to change for both candidates to reach the recruiter? →",
            expanded=False,
        ):
            cannot_fix = fix.get("cannot_be_fixed_by_candidate", True)
            if cannot_fix:
                st.markdown(
                    '<div style="background:#1c1917;border-left:3px solid #78350f;border-radius:0 6px 6px 0;'
                    'padding:10px 14px;font-size:0.84rem;color:#fcd34d;margin-bottom:16px">'
                    "This gap cannot be closed by the candidate. It requires a system change."
                    "</div>",
                    unsafe_allow_html=True,
                )

            fix_cols = st.columns(3)
            for col, key, label, color in [
                (fix_cols[0], "for_candidate", "For the candidate", "#3b82f6"),
                (fix_cols[1], "for_company_prompt", "Fix the AI prompt", "#8b5cf6"),
                (fix_cols[2], "for_company_process", "Fix the process", "#06b6d4"),
            ]:
                with col:
                    st.markdown(
                        f'<div style="background:#0f172a;border:1px solid #1e293b;border-top:3px solid {color};'
                        f'border-radius:0 0 8px 8px;padding:14px">'
                        f'<div style="font-size:0.72rem;font-weight:700;color:{color};text-transform:uppercase;'
                        f'letter-spacing:0.08em;margin-bottom:8px">{label}</div>'
                        f'<div style="font-size:0.85rem;color:#cbd5e1">{fix.get(key, "—")}</div>'
                        f"</div>",
                        unsafe_allow_html=True,
                    )

            eu = verdict.get("eu_ai_act_implication", "")
            if eu:
                st.markdown(
                    f'<div style="background:#1e1b4b;border-left:4px solid #6366f1;border-radius:0 8px 8px 0;'
                    f'padding:14px 18px;font-size:0.86rem;color:#c7d2fe;margin-top:16px">'
                    f"<b>🇪🇺 EU AI Act:</b> {eu}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        with st.expander("Raw JSON response"):
            st.json(sim)
