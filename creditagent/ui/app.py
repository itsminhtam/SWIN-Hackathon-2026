"""
ui/app.py — Streamlit Credit Assessment Dashboard
"""

import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import streamlit as st
import httpx
import json
import time
import plotly.graph_objects as go
import plotly.express as px

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CreditAgent — Vietnam SME Credit Assessment",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_URL = "http://localhost:8000"

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.main { background-color: #f8fafc; }
.stApp { background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 50%, #f8fafc 100%); }

.metric-card {
    background: #ffffff; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 24px;
    text-align: center;
    margin: 8px 0;
}

.score-display {
    font-size: 72px;
    font-weight: 700;
    line-height: 1;
    background: linear-gradient(135deg, #2563eb, #7c3aed);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.badge-approve {
    background: linear-gradient(135deg, #10b981, #059669);
    color: white;
    padding: 12px 32px;
    border-radius: 50px;
    font-size: 24px;
    font-weight: 700;
    letter-spacing: 2px;
    display: inline-block;
    box-shadow: 0 0 30px rgba(16,185,129,0.4);
}

.badge-escalate {
    background: linear-gradient(135deg, #f59e0b, #d97706);
    color: white;
    padding: 12px 32px;
    border-radius: 50px;
    font-size: 24px;
    font-weight: 700;
    letter-spacing: 2px;
    display: inline-block;
    box-shadow: 0 0 30px rgba(245,158,11,0.4);
}

.badge-deny {
    background: linear-gradient(135deg, #ef4444, #dc2626);
    color: white;
    padding: 12px 32px;
    border-radius: 50px;
    font-size: 24px;
    font-weight: 700;
    letter-spacing: 2px;
    display: inline-block;
    box-shadow: 0 0 30px rgba(239,68,68,0.4);
}

.thin-file-banner {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    border-radius: 12px;
    padding: 16px 24px;
    margin: 16px 0;
    border-left: 4px solid #a78bfa;
    color: white;
    font-size: 16px;
    font-weight: 600;
    box-shadow: 0 0 20px rgba(99,102,241,0.3);
}

.agent-step {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 12px 16px;
    margin: 6px 0;
    font-size: 14px;
}

.agent-done { border-left: 3px solid #10b981; }
.agent-override { border-left: 3px solid #f59e0b; }
.agent-running { border-left: 3px solid #3b82f6; }

.info-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid #e2e8f0;
}

.sidebar-persona {
    background: #ffffff; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    border-radius: 12px;
    padding: 16px;
    margin: 8px 0;
    border: 1px solid #e2e8f0;
}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=5)
def fetch_personas():
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{API_URL}/personas")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    
    # Fallback if API is offline
    return [
        {"borrower_id": "borrower_001", "name": "Nguyen Van A", "scenario": "Strong Traditional"},
        {"borrower_id": "borrower_002", "name": "Tran Thi B", "scenario": "Thin-file Alternative"},
    ]

PERSONA_LABELS = {}
PERSONA_DESCRIPTIONS = {}

for p in fetch_personas():
    bid = p["borrower_id"]
    name = p.get("name", "")
    business_name = p.get("business_name", name)
    scenario = p.get("scenario", "")
    loan_purpose = p.get("loan_purpose", scenario)
    PERSONA_LABELS[bid] = f"{business_name} — {loan_purpose}"
    PERSONA_DESCRIPTIONS[bid] = scenario


def get_decision_badge(decision: str) -> str:
    css_class = {
        "APPROVE": "badge-approve",
        "ESCALATE": "badge-escalate",
        "DENY": "badge-deny",
    }.get(decision, "badge-approve")
    return f'<div style="text-align:center; margin: 16px 0"><span class="{css_class}">{decision}</span></div>'


def get_score_color(score: int) -> str:
    if score >= 750:
        return "#10b981"
    elif score >= 600:
        return "#f59e0b"
    elif score >= 450:
        return "#ef4444"
    return "#7f1d1d"


def run_assessment(borrower_id: str, agentic: bool = False) -> dict:
    endpoint = "/assess/agentic" if agentic else "/assess"
    try:
        with httpx.Client(timeout=180) as client:
            resp = client.post(f"{API_URL}{endpoint}", json={"borrower_id": borrower_id})
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        st.error("Cannot connect to CreditAgent API. Please start the server:\n\n`uvicorn api.main:app --reload`")
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def score_gauge(score: int, title: str) -> go.Figure:
    color = get_score_color(score)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": title, "font": {"color": "#1e293b", "size": 14}},
        number={"font": {"color": color, "size": 36}},
        gauge={
            "axis": {"range": [0, 1000], "tickcolor": "#cbd5e1", "tickfont": {"color": "#64748b"}},
            "bar": {"color": color, "thickness": 0.3},
            "bgcolor": "#1e293b",
            "bordercolor": "#334155",
            "steps": [
                {"range": [0, 449], "color": "#fef2f2"},
                {"range": [450, 599], "color": "#fffbeb"},
                {"range": [600, 749], "color": "#fefce8"},
                {"range": [750, 1000], "color": "#ecfdf5"},
            ],
            "threshold": {
                "line": {"color": color, "width": 3},
                "thickness": 0.8,
                "value": score,
            },
        },
    ))
    fig.update_layout(
        height=200,
        margin=dict(l=20, r=20, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#1e293b"},
    )
    return fig


def shap_chart(shap_summary: dict, feature_names: list) -> go.Figure:
    if not shap_summary:
        return None

    items = [(k, v) for k, v in shap_summary.items() if k in feature_names]
    items.sort(key=lambda x: x[1])

    labels = [x[0].replace("_", " ").title() for x in items]
    values = [x[1] for x in items]
    colors = ["#10b981" if v < 0 else "#ef4444" for v in values]

    fig = go.Figure(go.Bar(
        x=values,
        y=labels,
        orientation="h",
        marker_color=colors,
        text=[f"{v:+.3f}" for v in values],
        textposition="outside",
        textfont={"color": "#1e293b"},
    ))
    fig.update_layout(
        title={"text": "SHAP Feature Impact on Default Risk", "font": {"color": "#1e293b"}},
        xaxis={"title": "SHAP Value", "color": "#64748b", "gridcolor": "#e2e8f0"},
        yaxis={"color": "#64748b"},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=350,
        margin=dict(l=10, r=80, t=50, b=10),
    )
    return fig


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## CREDITAGENT")
    st.markdown("*AI Multi-Agent Credit Assessment*")
    st.divider()

    selected_id = st.selectbox(
        "Select Borrower Persona",
        options=list(PERSONA_LABELS.keys()),
        format_func=lambda x: PERSONA_LABELS[x],
    )

    st.markdown(f"""
    <div class="sidebar-persona">
        <b>{PERSONA_LABELS[selected_id]}</b><br>
        <small style="color:#64748b">{PERSONA_DESCRIPTIONS[selected_id]}</small>
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    agentic_mode = st.toggle(
        "Agentic Mode (ReAct Loop)",
        value=True,
        help="Uses LLM-driven ReAct loop: the AI autonomously reasons and selects tools. Falls back to deterministic pipeline if LLM unavailable.",
    )
    run_btn = st.button("RUN CREDIT ASSESSMENT", type="primary", use_container_width=True)

    st.divider()
    st.markdown("**Stack:**")
    st.markdown("- ReAct Agentic Loop\n- Tool Registry\n- Agent Memory\n- XGBoost + SHAP\n- Claude/Gemini AI\n- Fairness Metrics")


# ── Main content ───────────────────────────────────────────────────────────────
st.markdown("# CREDITAGENT — VIETNAM SME CREDIT ASSESSMENT SYSTEM")
st.markdown("*AI multi-agent system for micro-loans — empowering undocumented household businesses*")

if "result" not in st.session_state:
    st.session_state.result = None

if run_btn:
    with st.spinner("Running agent pipeline…"):
        result = run_assessment(selected_id, agentic=agentic_mode)
        if result:
            st.session_state.result = result
            st.session_state.selected_id = selected_id

result = st.session_state.result

if result is None:
    # Welcome screen
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class="metric-card">
            <h3 style="color:#1e293b; text-transform:uppercase;">6 AI AGENTS</h3>
            <p style="color:#64748b">Parallel specialist agents evaluate financial, alternative, and behavioral signals</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="metric-card">
            <h3 style="color:#1e293b; text-transform:uppercase;">SUPPORT THIN-FILE</h3>
            <p style="color:#64748b">Approve micro-SMEs with no bank history using MoMo transactions & utility bills</p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class="metric-card">
            <h3 style="color:#1e293b; text-transform:uppercase;">FAIR & TRANSPARENT</h3>
            <p style="color:#64748b">Disparate impact and counterfactual fairness checks on every decision</p>
        </div>
        """, unsafe_allow_html=True)

    st.info("Select a borrower persona from the sidebar and click Run Credit Assessment")
else:
    # ── Thin-file banner ──────────────────────────────────────────────────────
    if result.get("is_underbanked") and result.get("decision") in ("APPROVE", "ESCALATE"):
        st.markdown("""
        <div class="thin-file-banner">
            THIN-FILE APPLICANT — Decision powered by <strong>Alternative Data</strong>
            (EVN/VNPT Utility Payments + MoMo/ZaloPay/ViettelPay Transactions) — No bank account required!
        </div>
        """, unsafe_allow_html=True)

    # ── Agentic mode badge ────────────────────────────────────────────────────
    agentic_mode_label = result.get("agentic_mode", "")
    if agentic_mode_label == "react_llm":
        st.markdown("""
        <div style="background:linear-gradient(135deg,#0f172a,#1e3a5f);border-radius:10px;padding:10px 20px;margin:8px 0;border-left:4px solid #38bdf8;color:#e0f2fe;font-size:14px">
            🤖 <strong>ReAct Agentic Mode</strong> — LLM autonomously reasoned through tool selection and decision logic
        </div>
        """, unsafe_allow_html=True)
    elif agentic_mode_label == "fallback_pipeline":
        st.markdown("""
        <div style="background:linear-gradient(135deg,#1c1917,#292524);border-radius:10px;padding:10px 20px;margin:8px 0;border-left:4px solid #a78bfa;color:#ede9fe;font-size:14px">
            ⚙️ <strong>Agentic Fallback Pipeline</strong> — Tool registry + agent memory (LLM unavailable)
        </div>
        """, unsafe_allow_html=True)

    # ── Top metrics row ───────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

    with col1:
        score = result["composite_score"]
        color = get_score_color(score)
        st.markdown(f"""
        <div class="metric-card">
            <div style="color:#64748b; font-size:12px; text-transform:uppercase; letter-spacing:1px">COMPOSITE SCORE</div>
            <div class="score-display">{score}</div>
            <div style="color:{color}; font-weight:600">{result["risk_tier"]}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(get_decision_badge(result["decision"]), unsafe_allow_html=True)
        if result["decision"] == "APPROVE":
            limit_m = result["credit_limit"] / 1_000_000
            st.markdown(f"""
            <div style="text-align:center; color:#64748b; font-size:13px">
                Up to <b style="color:#1e293b">{limit_m:.0f} million VND</b> @ {result["interest_rate_range"]}
            </div>
            """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div style="color:#64748b; font-size:11px">FINANCIAL SCORE</div>
            <div style="font-size:32px; font-weight:700; color:#3b82f6">{result["financial_score"]}</div>
            <div style="color:#64748b; font-size:11px">ALTERNATIVE SCORE</div>
            <div style="font-size:32px; font-weight:700; color:#8b5cf6">{result["alternative_score"]}</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.metric("TIME", f"{result['processing_time_ms']}ms")
        st.metric("COMPLETENESS", f"{result['data_completeness']:.0%}")
        bias_icon = "FAIL" if result['bias_detected'] else "PASS"
        st.metric("BIAS", f"{bias_icon}")

    st.divider()

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "SCORE BREAKDOWN",
        "AGENT PIPELINE",
        "FULL REPORT",
        "FAIRNESS METRICS",
        "REASONING TRACE",
    ])

    with tab1:
        col_a, col_b = st.columns(2)
        with col_a:
            st.plotly_chart(score_gauge(result["composite_score"], "Composite Score"), use_container_width=True)
        with col_b:
            # Score breakdown bar
            breakdown = result.get("score_breakdown", {})
            fig_break = go.Figure(go.Bar(
                x=["Financial", "Alternative", "Behavioral"],
                y=[
                    breakdown.get("financial_score", result["financial_score"]),
                    breakdown.get("alternative_score", result["alternative_score"]),
                    breakdown.get("behavioral_score", 500),
                ],
                marker_color=["#60a5fa", "#a78bfa", "#34d399"],
                text=[
                    f'{breakdown.get("financial_score", result["financial_score"])}',
                    f'{breakdown.get("alternative_score", result["alternative_score"])}',
                    f'{breakdown.get("behavioral_score", 500)}',
                ],
                textposition="outside",
                textfont={"color": "#1e293b"},
            ))
            fig_break.update_layout(
                title={"text": "Component Scores (0-1000)", "font": {"color": "#1e293b"}},
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=200,
                margin=dict(l=10, r=10, t=50, b=10),
                yaxis={"range": [0, 1050], "color": "#64748b", "gridcolor": "#e2e8f0"},
                xaxis={"color": "#64748b"},
                showlegend=False,
            )
            st.plotly_chart(fig_break, use_container_width=True)

        # SHAP chart
        shap_fig = shap_chart(result.get("shap_summary", {}), list(result.get("shap_summary", {}).keys()))
        if shap_fig:
            st.plotly_chart(shap_fig, use_container_width=True)
        else:
            st.info("ℹ️ SHAP values computed from trained model. Run `python data/train_model.py` first for full SHAP analysis.")

        col_s, col_c = st.columns(2)
        with col_s:
            st.markdown("### KEY STRENGTHS")
            for s in result.get("key_strengths", []):
                st.success(s)
        with col_c:
            st.markdown("### KEY CONCERNS")
            for c in result.get("key_concerns", []):
                st.warning(c)

    with tab2:
        st.markdown("### AGENT EXECUTION PIPELINE")
        pipeline = result.get("agent_pipeline", [])
        for i, step in enumerate(pipeline):
            css = f"agent-{step.get('status', 'done')}"
            st.markdown(f"""
            <div class="agent-step {css}">
                <b style="color:#1e293b; text-transform:uppercase;">STEP {i+1}: {step.get("agent", "")}</b>
                <span style="color:#64748b; float:right; font-size:12px">{step.get("status", "").upper()}</span><br>
                <span style="color:#64748b; font-size:13px">{step.get("output", "")}</span>
            </div>
            """, unsafe_allow_html=True)

        st.divider()
        st.markdown("### ALTERNATIVE DATA SIGNALS")
        signals = result.get("alternative_signals", {})
        if signals:
            cols = st.columns(len(signals))
            for i, (k, v) in enumerate(signals.items()):
                with cols[i]:
                    if isinstance(v, float):
                        st.metric(k.replace("_", " ").title(), f"{v:.2f}")
                    else:
                        st.metric(k.replace("_", " ").title(), f"{v:,}")

    with tab3:
        st.markdown("### AI-GENERATED CREDIT ASSESSMENT REPORT")
        borrower_name = result.get("borrower_name", "")
        decision = result.get("decision", "")
        if result.get("is_underbanked"):
            st.info("This report was generated for a **thin-file** applicant evaluated primarily on alternative data.")

        report_text = result.get("report", "No report generated.")
        st.markdown(f"""
        <div style="background:#ffffff; border-radius:12px; padding:24px; border:1px solid #e2e8f0; color:#1e293b; line-height:1.7; white-space:pre-wrap; font-size:14px">
{report_text}
        </div>
        """, unsafe_allow_html=True)

    with tab4:
        st.markdown("### FAIRNESS & BIAS ANALYSIS")

        if result.get("bias_detected"):
            st.error("**BIAS DETECTED** — Decision has been reviewed for potential fairness issues")
        else:
            st.success("**FAIRNESS PASS** — No significant bias detected across protected attributes")

        metrics = result.get("fairness_metrics", {})

        # Display metrics table
        fairness_rows = []
        metric_map = {
            "gender_disparate_impact": ("Gender Disparate Impact", "≥ 0.80", 0.80, True),
            "gender_statistical_parity": ("Gender Statistical Parity", "≤ 0.10", 0.10, False),
            "regional_disparate_impact": ("Regional Disparate Impact", "≥ 0.80", 0.80, True),
            "employment_disparate_impact": ("Employment Disparate Impact", "≥ 0.80", 0.80, True),
        }

        for key, (label, threshold, thresh_val, higher_better) in metric_map.items():
            if key in metrics:
                val = metrics[key]
                if higher_better:
                    status = "✅ Pass" if val >= thresh_val else "❌ Fail"
                else:
                    status = "✅ Pass" if val <= thresh_val else "❌ Fail"
                fairness_rows.append({"Metric": label, "Value": f"{val:.3f}", "Threshold": threshold, "Status": status})

        if fairness_rows:
            import pandas as pd
            df = pd.DataFrame(fairness_rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

        # Counterfactual
        cf = metrics.get("counterfactual_fairness", {})
        if cf:
            st.markdown("#### COUNTERFACTUAL FAIRNESS (GENDER FLIP TEST)")
            col1, col2, col3 = st.columns(3)
            col1.metric("Original Score", cf.get("original_score", "N/A"))
            col2.metric("Counterfactual Score", cf.get("counterfactual_score", "N/A"))
            col3.metric("Score Change", f"{cf.get('score_change_pct', 0):.1f}%",
                       delta=None,
                       help="Threshold: ≤ 5%")
            if cf.get("is_fair"):
                st.success(f"Counterfactual fair — score changes by only {cf.get('score_change_pct', 0):.1f}%")
            else:
                st.warning(f"Score changes by {cf.get('score_change_pct', 0):.1f}% when gender is flipped")

        bias_flags = metrics.get("bias_flags", [])
        if bias_flags:
            st.error(f"Bias flags triggered: {', '.join(bias_flags)}")

    with tab5:
        st.markdown("### AGENT REASONING TRACE")
        st.caption("Step-by-step record of every thought and tool call made during this assessment.")

        reasoning_summary = result.get("reasoning_summary", "")
        if reasoning_summary:
            st.info(f"**Final Reasoning:** {reasoning_summary}")

        trace = result.get("reasoning_trace", [])
        if not trace:
            st.warning("No reasoning trace available for this run.")
        else:
            for i, step in enumerate(trace):
                step_type = step.get("type", "")
                agent = step.get("agent", "Agent")
                ts = step.get("ts", "")[:19].replace("T", " ")

                if step_type == "thought":
                    st.markdown(f"""
                    <div style="background:#f0f9ff;border-left:3px solid #38bdf8;border-radius:6px;padding:10px 14px;margin:4px 0;font-size:13px">
                        <span style="color:#0369a1;font-weight:600">💭 THOUGHT</span>
                        <span style="color:#94a3b8;font-size:11px;float:right">{ts}</span><br>
                        <span style="color:#1e293b">{step.get('content','')}</span>
                    </div>
                    """, unsafe_allow_html=True)
                elif step_type == "action":
                    tool = step.get("tool", "")
                    args = step.get("args", {})
                    res = str(step.get("result", ""))[:200]
                    st.markdown(f"""
                    <div style="background:#f0fdf4;border-left:3px solid #22c55e;border-radius:6px;padding:10px 14px;margin:4px 0;font-size:13px">
                        <span style="color:#15803d;font-weight:600">⚡ ACTION: {tool}</span>
                        <span style="color:#94a3b8;font-size:11px;float:right">{ts}</span><br>
                        <span style="color:#64748b;font-size:12px">args: {json.dumps(args, default=str)[:150]}</span><br>
                        <span style="color:#1e293b">→ {res}</span>
                    </div>
                    """, unsafe_allow_html=True)

        st.divider()
        st.markdown("### SESSION DECISION HISTORY")
        try:
            with httpx.Client(timeout=10) as client:
                hist_resp = client.get(f"{API_URL}/history")
                if hist_resp.status_code == 200:
                    history = hist_resp.json().get("history", [])
                    if history:
                        import pandas as pd
                        df_hist = pd.DataFrame(history)[["ts", "borrower_id", "decision", "composite_score"]]
                        df_hist.columns = ["Timestamp", "Borrower", "Decision", "Score"]
                        st.dataframe(df_hist, use_container_width=True, hide_index=True)
                    else:
                        st.info("No prior decisions in this session.")
        except Exception:
            st.info("Start the API server to see session history.")
