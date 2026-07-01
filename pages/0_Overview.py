"""
Page 1 — Overview
Executive KPI strip, anomaly alerts, use-case cards with governance scores,
decisions-over-time chart, and decision breakdown.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from utils import (
    BANKING_USE_CASES,
    DAILY_BUDGET_USD,
    DECISION_COLORS,
    HUMAN_ROLES,
    INSURANCE_USE_CASES,
    USE_CASE_ICONS,
    USE_CASE_LABELS,
    USE_CASE_OWNERS,
    compute_costs,
    governance_score,
    render_sidebar,
    residual_risk,
    score_color,
)

df_raw, df, _ = render_sidebar()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 🛡️ Agentic AI Governance Gateway")
st.markdown(
    "**Control plane for banking and financial-services AI agent use cases** — "
    "decisioning, monitoring, and audit evidence captured by "
    "[agentgateway](https://agentgateway.dev) (open-source LLM/MCP/A2A data plane, "
    "Linux Foundation / AAIF). Every allow, deny, fallback, and redaction is a policy "
    "decision made in the gateway layer, upstream of any tool or model."
)

# ── Anomaly / alert banner ────────────────────────────────────────────────────
alerts = []

# Alert 1: any agent deny rate > 30%
agent_deny = df.groupby("agent_id").apply(lambda x: (x["decision"] == "deny").mean())
for agent, rate in agent_deny.items():
    if rate > 0.30:
        alerts.append(f"**{agent}** has an elevated deny rate of {rate:.0%} — policy violation spike detected.")

# Alert 2: budget > 80% consumed
total_spend, _ = compute_costs(df)
if total_spend >= DAILY_BUDGET_USD * 0.8:
    alerts.append(
        f"Daily spend **${total_spend:.2f}** has crossed 80% of the "
        f"${DAILY_BUDGET_USD:.0f} budget. Fallback routing may trigger soon."
    )

# Alert 3: any use case with overall deny rate jump vs expected baseline (> 25%)
uc_deny = df.groupby("use_case").apply(lambda x: (x["decision"] == "deny").mean())
for uc, rate in uc_deny.items():
    if rate > 0.25:
        label = USE_CASE_LABELS.get(uc, uc)
        alerts.append(f"**{label}** deny rate at {rate:.0%} — above 25% threshold, review policy scope.")

if alerts:
    with st.container():
        for alert in alerts:
            st.warning(alert, icon="⚠️")
else:
    st.success("All systems nominal — no anomalies detected in the selected window.", icon="✅")

# ── KPI strip ─────────────────────────────────────────────────────────────────
st.divider()
total         = len(df)
denied        = int((df["decision"] == "deny").sum())
fallback      = int((df["decision"] == "route-to-fallback").sum())
redactions    = int(df["redactions"].sum())
deny_pct      = denied / total if total else 0
spend, savings = compute_costs(df)
humans_events = int(df[df["role"].isin(HUMAN_ROLES)].shape[0])
humans_unique = int(df[df["role"].isin(HUMAN_ROLES)]["agent_id"].nunique())

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Gateway decisions", total)
c2.metric("Denied", denied,
          delta=f"{deny_pct:.0%} deny rate", delta_color="inverse")
c3.metric("PII redactions", redactions,
          help="Stripped from tool responses before agent context window")
c4.metric("Daily spend", f"${spend:.2f}",
          delta=f"${DAILY_BUDGET_USD - spend:.2f} remaining",
          delta_color="off",
          help=f"Budget: ${DAILY_BUDGET_USD:.0f}/day · ${savings:.2f} saved via fallback routing")
c5.metric("Saved via routing", f"${savings:.2f}",
          help="Cost difference: haiku vs sonnet for fallback calls")
c6.metric("Human-in-the-loop events", humans_events,
          delta=f"{humans_unique} unique humans",
          delta_color="off",
          help="Gateway decisions that required a human identity (adjuster, relationship manager)")

# ── Use-case cards ────────────────────────────────────────────────────────────
st.divider()
st.markdown("### Use cases")

for sector_label, uc_group in [
    ("🏦 Banking", BANKING_USE_CASES),
    ("📑 Financial Services / Insurance", INSURANCE_USE_CASES),
]:
    sector_ucs = [uc for uc in uc_group if uc in df["use_case"].values]
    if not sector_ucs:
        continue
    st.markdown(f"**{sector_label}**")
    cols = st.columns(len(sector_ucs))

    for i, uc in enumerate(sector_ucs):
        sub    = df[df["use_case"] == uc]
        calls  = len(sub)
        icon   = USE_CASE_ICONS[uc]
        label  = USE_CASE_LABELS[uc]
        owner  = USE_CASE_OWNERS.get(uc, "")
        d_rate = (sub["decision"] == "deny").mean()
        r_rate = (sub["redactions"] > 0).mean()
        avg_lat= sub["latency_ms"].mean() if calls else 0
        score  = governance_score(1 - d_rate, r_rate, avg_lat)
        sc     = score_color(score)
        uc_spend, _ = compute_costs(sub)

        with cols[i]:
            with st.container(border=True):
                st.markdown(
                    f"<div style='font-size:1.4rem;margin-bottom:2px'>{icon}</div>"
                    f"<div style='font-weight:700;font-size:0.9rem;line-height:1.3'>{label}</div>"
                    f"<div style='color:#718096;font-size:0.75rem;margin-bottom:8px'>{owner}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;align-items:center'>"
                    f"<span style='font-size:1.6rem;font-weight:700'>{score}</span>"
                    f"<span style='background:{sc};color:white;padding:2px 8px;"
                    f"border-radius:8px;font-size:0.72rem;font-weight:600'>Gov score</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                st.caption(f"{calls} calls · ${uc_spend:.3f} spend · {d_rate:.0%} deny")

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
    legend_title_text="Decision", margin=dict(l=0, r=0, t=10, b=0), height=300,
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
    uc_dec = df.groupby(["use_case", "decision"]).size().reset_index(name="count")
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
