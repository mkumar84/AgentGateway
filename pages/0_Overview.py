"""
Page 1 — Overview
Executive KPI strip, decisions-over-time chart, use-case summary, and decision mix.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from utils import DECISION_COLORS, USE_CASE_ICONS, USE_CASE_LABELS, render_sidebar

df_raw, df, _ = render_sidebar()

st.markdown("# 🛡️ Agentic AI Governance Gateway")
st.markdown(
    "**Control plane for banking and financial-services AI agent use cases** — "
    "decisioning, monitoring, and audit evidence captured by "
    "[agentgateway](https://agentgateway.dev) (open-source LLM/MCP/A2A data plane, "
    "Linux Foundation / AAIF). Every allow, deny, fallback, and redaction is a policy "
    "decision made in the gateway layer, upstream of any tool or model."
)

# ── KPI strip ─────────────────────────────────────────────────────────────────
st.divider()
total      = len(df)
denied     = int((df["decision"] == "deny").sum())
fallback   = int((df["decision"] == "route-to-fallback").sum())
redactions = int(df["redactions"].sum())
avg_lat    = df["latency_ms"].mean() if total else 0
deny_pct   = denied / total if total else 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total gateway decisions", total)
c2.metric("Denied", denied, delta=f"{deny_pct:.0%} deny rate", delta_color="inverse")
c3.metric("Routed to fallback", fallback, help="Budget exceeded → cheaper model, no hard failure")
c4.metric("PII redactions applied", redactions, help="Stripped from tool responses before agent context window")
c5.metric("Avg latency (ms)", f"{avg_lat:.0f}")

# ── Active use cases ──────────────────────────────────────────────────────────
st.divider()
st.markdown("### Active use cases")
uc_counts = df["use_case"].value_counts()
cols = st.columns(min(len(uc_counts), 7))
for i, (uc, count) in enumerate(uc_counts.items()):
    icon  = USE_CASE_ICONS.get(uc, "🤖")
    label = USE_CASE_LABELS.get(uc, uc)
    cols[i % len(cols)].metric(f"{icon} {label}", count)

# ── Decisions over time ───────────────────────────────────────────────────────
st.divider()
st.markdown("### Decisions over time")
st.caption("All gateway decisions in the selected window, bucketed by 3-hour intervals.")

time_df = (
    df.set_index("timestamp")
    .groupby([pd.Grouper(freq="3h"), "decision"])
    .size()
    .reset_index(name="count")
)
time_df.columns = ["timestamp", "decision", "count"]

fig = px.bar(
    time_df, x="timestamp", y="count", color="decision",
    color_discrete_map=DECISION_COLORS, barmode="stack",
    labels={"count": "Decisions", "timestamp": "", "decision": "Decision"},
)
fig.update_layout(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    legend_title_text="Decision", margin=dict(l=0, r=0, t=10, b=0), height=320,
)
st.plotly_chart(fig, use_container_width=True)

# ── Decision breakdown ────────────────────────────────────────────────────────
st.divider()
st.markdown("### Decision breakdown")
dc1, dc2 = st.columns([1, 2])

with dc1:
    mix = df["decision"].value_counts().reset_index()
    mix.columns = ["decision", "count"]
    fig_d = px.pie(
        mix, names="decision", values="count",
        color="decision", color_discrete_map=DECISION_COLORS, hole=0.55,
    )
    fig_d.update_traces(textinfo="percent+label")
    fig_d.update_layout(
        showlegend=False, margin=dict(l=0, r=0, t=10, b=0),
        height=260, paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_d, use_container_width=True)

with dc2:
    uc_dec = (
        df.groupby(["use_case", "decision"])
        .size()
        .reset_index(name="count")
    )
    uc_dec["label"] = uc_dec["use_case"].map(
        lambda x: f"{USE_CASE_ICONS.get(x,'🤖')} {USE_CASE_LABELS.get(x, x)}"
    )
    fig_uc = px.bar(
        uc_dec, x="count", y="label", color="decision",
        color_discrete_map=DECISION_COLORS, barmode="stack", orientation="h",
        labels={"count": "Decisions", "label": "", "decision": "Decision"},
    )
    fig_uc.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0), height=260,
        yaxis={"categoryorder": "total ascending"},
    )
    st.plotly_chart(fig_uc, use_container_width=True)

st.divider()
st.caption(
    "Built on [agentgateway](https://agentgateway.dev) · "
    "Open source · Linux Foundation / AAIF · "
    "Agentic AI governance for financial services."
)
