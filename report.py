"""
Agentic AI Governance Gateway — Reporting Module
--------------------------------------------------
Reads agentgateway's JSON access-log output (one decision per line) and
renders a governance scorecard: decisioning summary, inherent vs residual
risk view per use case, and a full audit trail.

This is designed to slot into the AI & ML Governance Command Centre
(ai-ml-gov.lovable.app) as a standalone module, or run on its own:

    streamlit run report.py

By default it reads sample_logs/audit-sample.jsonl (synthetic data shaped
exactly like agentgateway's real access log). To use real data, run
agentgateway locally with the config in config/config.yaml, then either:
  (a) point LOG_PATH below at your real ./logs/agentgateway-audit.jsonl, or
  (b) use the file-upload widget in the sidebar to drop in a real export.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Agentic AI Governance Gateway", layout="wide")

DEFAULT_LOG_PATH = Path(__file__).parent / "sample_logs" / "audit-sample.jsonl"

USE_CASE_LABELS = {
    "claims_triage": "Claims Triage Agent",
    "underwriting_risk": "Underwriting Risk-Scoring Agent",
    "advisor_assist": "Advisor Assist Agent",
}

# Inherent risk ratings are a judgment call made when the policy was designed
# (see comments in policies/*.yaml). Residual risk is computed live below
# from what the gateway actually observed (deny rate, redaction rate).
INHERENT_RISK = {
    "claims_triage": "High — PII exposure via an autonomous agent",
    "underwriting_risk": "Medium — cost runaway / model drift on a regulated decision",
    "advisor_assist": "High — PII leakage into an advisor-facing chat surface",
}

GOVERNANCE_PATTERN = {
    "claims_triage": "Tool-level RBAC (access control decisioning)",
    "underwriting_risk": "Budget cap + pinned-model routing (cost/decision governance)",
    "advisor_assist": "Response-side guardrail / PII redaction",
}


@st.cache_data
def load_logs(file) -> pd.DataFrame:
    if hasattr(file, "read"):
        lines = file.read().decode("utf-8").splitlines()
    else:
        lines = Path(file).read_text().splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def residual_risk_label(deny_rate: float, redaction_rate: float) -> str:
    signal = max(deny_rate, redaction_rate)
    if signal == 0:
        return "Low — no violations observed in this window"
    if signal < 0.15:
        return "Low — controls intercepted isolated attempts"
    if signal < 0.4:
        return "Medium — recurring control hits, review policy scope"
    return "High — frequent control hits, escalate for review"


st.title("Agentic AI Governance Gateway")
st.caption(
    "Decisioning, monitoring, and audit evidence captured by agentgateway "
    "across three RBC Insurance agent use cases."
)

with st.sidebar:
    st.header("Data source")
    uploaded = st.file_uploader("Upload a real agentgateway-audit.jsonl", type=["jsonl", "json", "log"])
    st.caption("No upload yet? Showing synthetic sample data shaped like a real export.")

df = load_logs(uploaded) if uploaded is not None else load_logs(DEFAULT_LOG_PATH)

# ---------------- Top-line monitoring ----------------
total_calls = len(df)
denied = (df["decision"] == "deny").sum()
fallback = (df["decision"] == "route-to-fallback").sum()
redactions = df.get("redactions", pd.Series(dtype=float)).fillna(0).sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total gateway decisions", total_calls)
c2.metric("Denied", int(denied))
c3.metric("Routed to fallback (budget)", int(fallback))
c4.metric("PII redactions applied", int(redactions))

st.divider()

# ---------------- Per-use-case governance scorecard ----------------
st.subheader("Governance scorecard by use case")

for uc, label in USE_CASE_LABELS.items():
    sub = df[df["use_case"] == uc]
    if sub.empty:
        continue
    deny_rate = (sub["decision"] == "deny").mean()
    redaction_rate = (
        sub.get("redactions", pd.Series(dtype=float)).fillna(0) > 0
    ).mean()

    with st.container(border=True):
        st.markdown(f"**{label}**")
        cols = st.columns([2, 2, 2, 1])
        cols[0].markdown(f"*Pattern:* {GOVERNANCE_PATTERN[uc]}")
        cols[1].markdown(f"*Inherent risk:* {INHERENT_RISK[uc]}")
        cols[2].markdown(f"*Residual risk:* {residual_risk_label(deny_rate, redaction_rate)}")
        cols[3].metric("Calls", len(sub))

st.divider()

# ---------------- Decisions over time ----------------
st.subheader("Decisions over time")
chart_df = (
    df.set_index("timestamp")
    .groupby([pd.Grouper(freq="h"), "decision"])
    .size()
    .unstack(fill_value=0)
)
st.bar_chart(chart_df)

st.divider()

# ---------------- Full audit trail ----------------
st.subheader("Audit trail")
st.caption("Tamper-evident log of every routed decision, as emitted by the gateway.")
show_cols = [c for c in [
    "timestamp", "use_case", "agent_id", "role", "tool", "decision",
    "reason", "redactions", "tokens_used", "latency_ms",
] if c in df.columns]
st.dataframe(
    df[show_cols].sort_values("timestamp", ascending=False),
    use_container_width=True,
    hide_index=True,
)
