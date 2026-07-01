"""
Page 3 — Agent Monitor
Per-agent call volume, deny rates, token burn, latency distribution,
activity timelines, and tool breakdowns.
"""

import plotly.express as px
import streamlit as st

from utils import DECISION_COLORS, USE_CASE_ICONS, USE_CASE_LABELS, render_sidebar

df_raw, df, _ = render_sidebar()

st.markdown("# 🤖 Agent Monitor")
st.markdown(
    "Per-agent call volume, control hit rates, token burn, and latency distribution. "
    "Status dot: 🟢 healthy · 🟡 elevated deny rate (>10%) · 🔴 high deny rate (>30%)"
)
st.divider()

agents = sorted(df["agent_id"].unique())

if not agents:
    st.info("No agents match the current filters.")
    st.stop()

for agent in agents:
    asub      = df[df["agent_id"] == agent]
    deny_rt   = (asub["decision"] == "deny").mean()
    tokens    = int(asub["tokens_used"].sum())
    p50       = asub["latency_ms"].quantile(0.50)
    p95       = asub["latency_ms"].quantile(0.95)
    calls     = len(asub)
    uc        = asub["use_case"].mode()[0] if not asub.empty else ""
    uc_label  = USE_CASE_LABELS.get(uc, uc)
    uc_icon   = USE_CASE_ICONS.get(uc, "🤖")
    status    = "🔴" if deny_rt > 0.30 else ("🟡" if deny_rt > 0.10 else "🟢")

    with st.expander(f"{status} **{agent}** · {uc_icon} {uc_label} · {calls} calls"):

        # Metrics row
        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        mc1.metric("Total calls", calls)
        mc2.metric("Deny rate", f"{deny_rt:.0%}",
                   delta=f"{int(deny_rt * calls)} denied", delta_color="inverse")
        mc3.metric("Tokens used", f"{tokens:,}")
        mc4.metric("p50 latency ms", f"{p50:.0f}")
        mc5.metric("p95 latency ms", f"{p95:.0f}")

        tab1, tab2 = st.tabs(["Activity timeline", "Tool breakdown"])

        with tab1:
            import pandas as pd
            agent_time = (
                asub.set_index("timestamp")
                .groupby([pd.Grouper(freq="2h"), "decision"])
                .size()
                .reset_index(name="count")
            )
            agent_time.columns = ["timestamp", "decision", "count"]
            if not agent_time.empty:
                fig_a = px.bar(
                    agent_time, x="timestamp", y="count", color="decision",
                    color_discrete_map=DECISION_COLORS, barmode="stack",
                    height=220,
                    labels={"count": "Decisions", "timestamp": "", "decision": "Decision"},
                )
                fig_a.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=0, r=0, t=4, b=0),
                )
                st.plotly_chart(fig_a, use_container_width=True, key=f"timeline_{agent}")
            else:
                st.caption("No data in selected window.")

        with tab2:
            tool_counts = asub.groupby(["tool", "decision"]).size().reset_index(name="count")
            if not tool_counts.empty:
                fig_t = px.bar(
                    tool_counts, x="tool", y="count", color="decision",
                    color_discrete_map=DECISION_COLORS, barmode="stack",
                    height=220,
                    labels={"count": "Calls", "tool": "Tool / Model", "decision": "Decision"},
                )
                fig_t.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=0, r=0, t=4, b=0),
                )
                st.plotly_chart(fig_t, use_container_width=True, key=f"tools_{agent}")
                st.page_link(
                    f"pages/3_Tool_Performance.py",
                    label="→ Full tool analysis for this agent",
                    icon="🔧",
                    help=f"Opens Tool Performance pre-filtered to {agent}",
                )
            else:
                st.caption("No tool data in selected window.")

st.divider()
st.caption(
    "Built on [agentgateway](https://agentgateway.dev) · "
    "Open source · Linux Foundation / AAIF"
)
