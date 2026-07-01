"""
Page 4 — Tool Performance
Per-tool compliance rate, latency, PII exposure, token efficiency,
agent-tool heatmap, and redundant call detection.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import DECISION_COLORS, USE_CASE_ICONS, USE_CASE_LABELS, render_sidebar

df_raw, df, _ = render_sidebar()

# ── Pre-filter from Agent Monitor query param ─────────────────────────────────
qp = st.query_params.get("agent", None)
if qp and qp in df["agent_id"].values:
    df = df[df["agent_id"] == qp]
    st.info(f"Filtered to agent **{qp}** — arrived from Agent Monitor. [Clear filter](?)", icon="🔗")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 🔧 Tool Performance")
st.markdown(
    "Compliance rate, latency, PII exposure, and token efficiency per tool — "
    "answers whether agents are calling the right tools, efficiently, "
    "and without triggering unnecessary controls."
)

if df.empty:
    st.warning("No data matches the current filters.")
    st.stop()

# ── Derived metrics per tool ──────────────────────────────────────────────────
tool_stats = (
    df.groupby("tool")
    .agg(
        calls       =("decision", "count"),
        allowed     =("decision", lambda x: (x == "allow").sum()),
        denied      =("decision", lambda x: (x == "deny").sum()),
        fallback    =("decision", lambda x: (x == "route-to-fallback").sum()),
        avg_latency =("latency_ms", "mean"),
        p95_latency =("latency_ms", lambda x: x.quantile(0.95)),
        total_tokens=("tokens_used", "sum"),
        redactions  =("redactions", "sum"),
    )
    .reset_index()
)
tool_stats["deny_rate"]      = tool_stats["denied"]     / tool_stats["calls"]
tool_stats["redaction_rate"] = tool_stats["redactions"] / tool_stats["calls"]
tool_stats["compliance_rate"]= tool_stats["allowed"]    / tool_stats["calls"]

# Identify LLM tools (they have token usage)
llm_tools = tool_stats[tool_stats["total_tokens"] > 0]["tool"].tolist()
mcp_tools = tool_stats[tool_stats["total_tokens"] == 0]["tool"].tolist()

# ── Section 1 — Compliance rate ───────────────────────────────────────────────
st.divider()
st.markdown("## Tool compliance rate")
st.caption(
    "What % of each tool's calls were allowed by the gateway. "
    "A low compliance rate means the agent is repeatedly calling a tool it shouldn't — "
    "either a policy misconfiguration or an agent behaviour issue."
)

# Stacked bar: allow / deny / fallback per tool
compliance_rows = []
for _, r in tool_stats.iterrows():
    for decision, count in [("allow", r["allowed"]), ("deny", r["denied"]), ("fallback", r["fallback"])]:
        if count > 0:
            compliance_rows.append({"tool": r["tool"], "decision": decision, "count": int(count)})

if compliance_rows:
    comp_df = pd.DataFrame(compliance_rows)
    fig_comp = px.bar(
        comp_df, x="tool", y="count", color="decision",
        color_discrete_map={**DECISION_COLORS, "fallback": DECISION_COLORS["route-to-fallback"]},
        barmode="stack", text_auto=True,
        labels={"count": "Calls", "tool": "Tool / Model", "decision": "Decision"},
        height=320,
    )
    fig_comp.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(fig_comp, use_container_width=True)

# Compliance rate table with colour coding
st.markdown("**Compliance summary**")
display_cols = tool_stats[["tool", "calls", "allowed", "denied", "fallback", "compliance_rate", "deny_rate"]].copy()
display_cols.columns = ["Tool", "Total calls", "Allowed", "Denied", "Fallback", "Compliance rate", "Deny rate"]
display_cols["Compliance rate"] = display_cols["Compliance rate"].map("{:.0%}".format)
display_cols["Deny rate"]        = display_cols["Deny rate"].map("{:.0%}".format)

def color_compliance(val):
    try:
        pct = float(val.strip("%")) / 100
    except Exception:
        return ""
    if pct >= 0.90: return "background-color:#c6f6d5"
    if pct >= 0.70: return "background-color:#feebc8"
    return "background-color:#fed7d7"

def color_deny(val):
    try:
        pct = float(val.strip("%")) / 100
    except Exception:
        return ""
    if pct == 0:    return "background-color:#c6f6d5"
    if pct < 0.15:  return "background-color:#feebc8"
    return "background-color:#fed7d7"

st.dataframe(
    display_cols.sort_values("Total calls", ascending=False)
    .style
    .map(color_compliance, subset=["Compliance rate"])
    .map(color_deny,       subset=["Deny rate"]),
    use_container_width=True,
    hide_index=True,
)

# ── Section 2 — Latency per tool ──────────────────────────────────────────────
st.divider()
st.markdown("## Latency per tool")
st.caption(
    "Average and p95 latency per tool. High p95 relative to average signals "
    "occasional spikes — worth investigating if the tool is on a hot path."
)

lat_df = tool_stats[["tool", "avg_latency", "p95_latency"]].melt(
    id_vars="tool", var_name="metric", value_name="ms"
)
lat_df["metric"] = lat_df["metric"].map({"avg_latency": "Avg", "p95_latency": "p95"})

fig_lat = px.bar(
    lat_df, x="tool", y="ms", color="metric",
    barmode="group",
    color_discrete_map={"Avg": "#4299e1", "p95": "#e53e3e"},
    labels={"ms": "Latency (ms)", "tool": "Tool / Model", "metric": ""},
    height=300, text_auto=".0f",
)
fig_lat.update_layout(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=10, b=0),
)
st.plotly_chart(fig_lat, use_container_width=True)

# Latency insight callouts
lc1, lc2 = st.columns(2)
slowest = tool_stats.loc[tool_stats["avg_latency"].idxmax()]
fastest = tool_stats.loc[tool_stats["avg_latency"].idxmin()]
lc1.metric("Slowest tool (avg)", slowest["tool"], f"{slowest['avg_latency']:.0f} ms avg")
lc2.metric("Fastest tool (avg)", fastest["tool"], f"{fastest['avg_latency']:.0f} ms avg", delta_color="off")

# ── Section 3 — PII exposure per tool ────────────────────────────────────────
st.divider()
st.markdown("## PII exposure by tool")
st.caption(
    "Redaction rate per tool — which tools are the most frequent source of PII "
    "in responses. High rates here indicate the tool's data source needs tighter "
    "upstream masking, independent of the gateway guardrail."
)

pii_tools = tool_stats[tool_stats["redactions"] > 0].copy()
if pii_tools.empty:
    st.success("No PII redactions recorded for any tool in this window.", icon="✅")
else:
    fig_pii = px.bar(
        pii_tools.sort_values("redaction_rate", ascending=False),
        x="tool", y="redaction_rate", text_auto=".0%",
        color="redaction_rate",
        color_continuous_scale=["#c6f6d5", "#feebc8", "#fed7d7"],
        labels={"redaction_rate": "Redaction rate", "tool": "Tool"},
        height=260,
    )
    fig_pii.update_coloraxes(showscale=False)
    fig_pii.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(fig_pii, use_container_width=True)

    # Redaction type breakdown if available
    if "redaction_type" in df.columns:
        rt = (
            df[df["redactions"] > 0]
            .groupby(["tool", "redaction_type"])
            .size()
            .reset_index(name="count")
        )
        if not rt.empty:
            fig_rt = px.bar(
                rt, x="tool", y="count", color="redaction_type",
                barmode="stack", text_auto=True,
                labels={"count": "Redactions", "tool": "Tool", "redaction_type": "Type"},
                height=240,
            )
            fig_rt.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=10, b=0),
            )
            st.markdown("**Redaction type breakdown**")
            st.plotly_chart(fig_rt, use_container_width=True)

# ── Section 4 — Token efficiency (LLM tools only) ────────────────────────────
st.divider()
st.markdown("## Token efficiency")

llm_df = tool_stats[tool_stats["total_tokens"] > 0].copy()
if llm_df.empty:
    st.info("No LLM tool calls in the current filter window.")
else:
    st.caption(
        "Token consumption per LLM tool call. High average token counts relative to "
        "peers may indicate oversized prompts or unnecessary context being passed. "
        "Fallback events show where the daily budget cap was hit."
    )

    # Tokens per call
    llm_detail = df[df["tool"].isin(llm_df["tool"].tolist())].copy()
    llm_detail["date"] = llm_detail["timestamp"].dt.date

    tc1, tc2 = st.columns(2)

    with tc1:
        avg_tok = llm_detail.groupby("tool")["tokens_used"].mean().reset_index()
        avg_tok.columns = ["tool", "avg_tokens"]
        fig_tok = px.bar(
            avg_tok, x="tool", y="avg_tokens", text_auto=".0f",
            color_discrete_sequence=["#4299e1"],
            labels={"avg_tokens": "Avg tokens / call", "tool": "Model"},
            height=260,
        )
        fig_tok.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False, margin=dict(l=0, r=0, t=4, b=0),
        )
        st.markdown("**Avg tokens per call by model**")
        st.plotly_chart(fig_tok, use_container_width=True)

    with tc2:
        daily = llm_detail.groupby(["date", "tool"])["tokens_used"].sum().reset_index()
        daily.columns = ["date", "tool", "tokens"]
        fig_daily = px.bar(
            daily, x="date", y="tokens", color="tool",
            barmode="stack", text_auto=".2s",
            labels={"tokens": "Tokens", "date": "Date", "tool": "Model"},
            height=260,
        )
        fig_daily.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=4, b=0),
        )
        st.markdown("**Daily token burn by model**")
        st.plotly_chart(fig_daily, use_container_width=True)

    # Fallback trigger rate
    total_llm   = len(llm_detail)
    fallback_ct = int((llm_detail["decision"] == "route-to-fallback").sum())
    fb_rate     = fallback_ct / total_llm if total_llm else 0
    fbc1, fbc2, fbc3 = st.columns(3)
    fbc1.metric("Total LLM calls", total_llm)
    fbc2.metric("Budget fallback triggers", fallback_ct,
                delta=f"{fb_rate:.0%} of LLM calls", delta_color="inverse")
    fbc3.metric("Total tokens consumed", f"{int(llm_df['total_tokens'].sum()):,}")

# ── Section 5 — Agent × Tool heatmap ─────────────────────────────────────────
st.divider()
st.markdown("## Agent × tool call heatmap")
st.caption(
    "How many times each agent called each tool. "
    "Sparse rows = agents under-utilising permitted tools. "
    "Concentrated columns = over-reliance on a single tool."
)

heatmap_data = (
    df.groupby(["agent_id", "tool"])
    .size()
    .reset_index(name="calls")
)
pivot = heatmap_data.pivot(index="agent_id", columns="tool", values="calls").fillna(0)

fig_heat = go.Figure(data=go.Heatmap(
    z=pivot.values,
    x=pivot.columns.tolist(),
    y=pivot.index.tolist(),
    colorscale="Blues",
    text=pivot.values.astype(int),
    texttemplate="%{text}",
    showscale=True,
    hovertemplate="Agent: %{y}<br>Tool: %{x}<br>Calls: %{z}<extra></extra>",
))
fig_heat.update_layout(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=10, b=0),
    height=max(200, len(pivot) * 60),
    xaxis_title="Tool / Model",
    yaxis_title="Agent",
)
st.plotly_chart(fig_heat, use_container_width=True)

# ── Section 6 — Redundant call detection ──────────────────────────────────────
st.divider()
st.markdown("## Redundant call detection")
st.caption(
    "Consecutive calls to the same tool by the same agent within 60 seconds — "
    "a signal of retry loops, misconfigured agent logic, or prompt inefficiency."
)

df_sorted = df.sort_values(["agent_id", "timestamp"])
df_sorted["prev_tool"]      = df_sorted.groupby("agent_id")["tool"].shift(1)
df_sorted["prev_ts"]        = df_sorted.groupby("agent_id")["timestamp"].shift(1)
df_sorted["gap_s"]          = (df_sorted["timestamp"] - df_sorted["prev_ts"]).dt.total_seconds()
redundant = df_sorted[
    (df_sorted["tool"] == df_sorted["prev_tool"]) &
    (df_sorted["gap_s"] <= 60)
].copy()

if redundant.empty:
    st.success("No redundant consecutive tool calls detected in this window.", icon="✅")
else:
    st.warning(f"**{len(redundant)} redundant call(s)** detected.", icon="⚠️")
    show_cols = [c for c in ["timestamp", "agent_id", "tool", "decision", "gap_s", "latency_ms"] if c in redundant.columns]
    redundant_display = redundant[show_cols].copy()
    redundant_display["gap_s"] = redundant_display["gap_s"].map("{:.0f}s gap".format)
    st.dataframe(redundant_display, use_container_width=True, hide_index=True)

# ── Back-link to Agent Monitor ────────────────────────────────────────────────
st.divider()
st.markdown("**Related pages**")
lnk1, lnk2 = st.columns(2)
with lnk1:
    st.page_link("pages/2_Agent_Monitor.py", label="← Agent Monitor", icon="🤖")
with lnk2:
    st.page_link("pages/4_Decision_Log.py",  label="Decision Log →",  icon="📜")

st.divider()
st.caption(
    "Built on [agentgateway](https://agentgateway.dev) · "
    "Open source · Linux Foundation / AAIF"
)
