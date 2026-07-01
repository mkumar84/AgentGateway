"""
Agentic AI Governance Gateway — Command Centre
-----------------------------------------------
Governance scorecard, agent monitor, and decision explorer for three
RBC Insurance agent use cases, powered by agentgateway (open-source
LLM/MCP/A2A data plane — Linux Foundation / AAIF).

Run:  streamlit run report.py
Data: sample_logs/audit-sample.jsonl (synthetic) or upload a real export.
"""

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agentic AI Governance Gateway",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ─────────────────────────────────────────────────────────────────
DEFAULT_LOG_PATH = Path(__file__).parent / "sample_logs" / "audit-sample.jsonl"

USE_CASE_LABELS = {
    "claims_triage": "Claims Triage Agent",
    "underwriting_risk": "Underwriting Risk-Scoring Agent",
    "advisor_assist": "Advisor Assist Agent",
}

INHERENT_RISK = {
    "claims_triage": "High",
    "underwriting_risk": "Medium",
    "advisor_assist": "High",
}

INHERENT_RISK_DETAIL = {
    "claims_triage": "PII exposure via an autonomous agent processing claimant records",
    "underwriting_risk": "Cost runaway and model drift on a regulated underwriting decision",
    "advisor_assist": "PII leakage into an advisor-facing chat surface from knowledge base",
}

GOVERNANCE_PATTERN = {
    "claims_triage": "Tool-level RBAC (CEL policy)",
    "underwriting_risk": "Token budget cap + pinned-model routing",
    "advisor_assist": "Response-side PII redaction guardrail",
}

POLICY_SNIPPET = {
    "claims_triage": """\
# 01-claims-rbac.yaml — AgentgatewayPolicy
matchExpressions:
  # claims-bot may read and escalate, never touch PII
  - 'jwt.sub == "claims-bot" && mcp.tool.name in ["get_claim","escalate_claim"]'
  # only verified adjusters (claim from IdP) may pull PII
  - 'jwt.claims["role"] == "claims-adjuster" && mcp.tool.name == "access_pii"'
denyByDefault: true""",
    "underwriting_risk": """\
# 02-underwriting-budget.yaml — AgentgatewayPolicy
budget:
  scope: per-team
  team: underwriting
  maxTokensPerDay: 500000
  onExceed: route-to-fallback   # forces claude-haiku instead of hard-failing
modelPin:
  requirePinnedVersion: true    # OSFI E-23 model-risk documentation""",
    "advisor_assist": """\
# 03-advisor-redaction.yaml — AgentgatewayPolicy
guardrails:
  direction: response           # scan what comes back from the tool
  rules:
    - name: sin-redaction
      pattern: '\\b\\d{3}-\\d{3}-\\d{3}\\b'
      action: redact
    - name: policy-number-redaction
      pattern: '\\bPOL-\\d{8}\\b'
      action: redact
    - name: banking-redaction
      pattern: '\\b\\d{3}-\\d{3}-\\d{7,12}\\b'
      action: redact""",
}

CONTROL_EXPLANATION = {
    "claims_triage": (
        "The gateway enforces a CEL-based RBAC rule on every MCP tool call. "
        "`claims-bot` can read and escalate claims but is structurally blocked "
        "from calling `access_pii` — the rule is evaluated in the data plane "
        "before the request ever reaches the MCP server, so no application-layer "
        "code change can bypass it. Only a JWT carrying the `claims-adjuster` role "
        "(issued by the IdP) is permitted to pull PII."
    ),
    "underwriting_risk": (
        "The gateway tracks daily token consumption per team. When the "
        "`underwriting` team crosses 500 000 tokens it automatically re-routes "
        "subsequent calls to `claude-haiku-4-5` instead of hard-failing — "
        "preserving throughput while capping cost. Model pinning ensures every "
        "underwriting decision cites an exact, auditable model version, satisfying "
        "OSFI E-23 model-risk documentation requirements."
    ),
    "advisor_assist": (
        "Every tool response from the knowledge base MCP is scanned by the gateway "
        "before it enters the agent's context window. Regex rules redact SINs, "
        "policy numbers, and banking identifiers in real time — the agent never "
        "sees raw PII and therefore cannot surface it in a chat response. Tool "
        "scope is also enforced: only `search_kb` and `get_product_summary` are "
        "permitted; any other tool call is denied at the gateway."
    ),
}

RISK_COLORS = {"High": "#e53e3e", "Medium": "#dd6b20", "Low": "#38a169"}
DECISION_COLORS = {
    "allow": "#38a169",
    "deny": "#e53e3e",
    "route-to-fallback": "#dd6b20",
}


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data
def load_logs(file) -> pd.DataFrame:
    if hasattr(file, "read"):
        lines = file.read().decode("utf-8").splitlines()
    else:
        lines = Path(file).read_text().splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["redactions"] = df.get("redactions", pd.Series(dtype=float)).fillna(0).astype(int)
    df["tokens_used"] = df.get("tokens_used", pd.Series(dtype=float)).fillna(0).astype(int)
    return df


def residual_risk(deny_rate: float, redaction_rate: float) -> str:
    signal = max(deny_rate, redaction_rate)
    if signal == 0:
        return "Low"
    if signal < 0.15:
        return "Low"
    if signal < 0.4:
        return "Medium"
    return "High"


def residual_risk_detail(deny_rate: float, redaction_rate: float, uc: str) -> str:
    signal = max(deny_rate, redaction_rate)
    if signal == 0:
        return "No violations observed in this window — controls are passive."
    if signal < 0.15:
        return f"Controls intercepted isolated attempts ({deny_rate:.0%} deny rate, {redaction_rate:.0%} redaction rate). Policy holding."
    if signal < 0.4:
        return f"Recurring control hits ({deny_rate:.0%} deny rate, {redaction_rate:.0%} redaction rate). Review policy scope."
    return f"Frequent control hits ({deny_rate:.0%} deny rate, {redaction_rate:.0%} redaction rate). Escalate for review."


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://agentgateway.dev/img/logo.svg", width=160) if False else None
    st.markdown("## 🛡️ AgentGateway")
    st.caption(
        "Open-source LLM/MCP/A2A data plane · "
        "[agentgateway.dev](https://agentgateway.dev) · "
        "Linux Foundation / AAIF"
    )
    st.divider()

    st.markdown("### Data source")
    uploaded = st.file_uploader(
        "Upload agentgateway-audit.jsonl",
        type=["jsonl", "json", "log"],
        help="Export from ./logs/agentgateway-audit.jsonl after running the gateway locally.",
    )
    if not uploaded:
        st.info("Showing synthetic sample data shaped like a real export.", icon="ℹ️")

    st.divider()
    st.markdown("### Filters")

df_raw = load_logs(uploaded) if uploaded is not None else load_logs(DEFAULT_LOG_PATH)

with st.sidebar:
    uc_options = ["All"] + list(USE_CASE_LABELS.values())
    uc_filter = st.selectbox("Use case", uc_options)

    agent_options = ["All"] + sorted(df_raw["agent_id"].unique().tolist())
    agent_filter = st.selectbox("Agent", agent_options)

    decision_options = ["All"] + sorted(df_raw["decision"].unique().tolist())
    decision_filter = st.selectbox("Decision", decision_options)

    min_date = df_raw["timestamp"].dt.date.min()
    max_date = df_raw["timestamp"].dt.date.max()
    date_range = st.date_input("Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)

    st.divider()
    st.markdown("### Architecture")
    st.markdown(
        """
```
  Agent / LLM client
        │
        ▼
  ┌─────────────┐
  │agentgateway │  ◄── CEL policies
  │  data plane │      budget caps
  │             │      PII guardrails
  └──────┬──────┘
         │
    ┌────┴────┐
    ▼         ▼
  MCP       LLM
 Server    Provider
```
        """
    )
    st.caption("Every decision in this report was made at the gateway layer — before reaching the tool or model.")

# ── Apply filters ─────────────────────────────────────────────────────────────
df = df_raw.copy()
uc_reverse = {v: k for k, v in USE_CASE_LABELS.items()}
if uc_filter != "All":
    df = df[df["use_case"] == uc_reverse[uc_filter]]
if agent_filter != "All":
    df = df[df["agent_id"] == agent_filter]
if decision_filter != "All":
    df = df[df["decision"] == decision_filter]
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    df = df[(df["timestamp"].dt.date >= date_range[0]) & (df["timestamp"].dt.date <= date_range[1])]

# ── Section 0 — Header ────────────────────────────────────────────────────────
st.markdown("# 🛡️ Agentic AI Governance Gateway")
st.markdown(
    "**Control plane for three RBC Insurance agent use cases** — "
    "decisioning, monitoring, and audit evidence captured by "
    "[agentgateway](https://agentgateway.dev) (open-source LLM/MCP/A2A data plane, Linux Foundation / AAIF). "
    "Every allow, deny, fallback, and redaction below is a policy decision made in the gateway layer, "
    "upstream of any tool or model."
)

# ── Section 1 — Executive KPI strip ──────────────────────────────────────────
st.divider()
total = len(df)
denied = int((df["decision"] == "deny").sum())
fallback = int((df["decision"] == "route-to-fallback").sum())
redactions = int(df["redactions"].sum())
avg_latency = df["latency_ms"].mean() if total > 0 else 0
deny_pct = denied / total if total > 0 else 0

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total gateway decisions", total)
col2.metric("Denied", denied, delta=f"{deny_pct:.0%} deny rate", delta_color="inverse")
col3.metric("Routed to fallback", fallback, help="Budget exceeded → cheaper model, no hard failure")
col4.metric("PII redactions applied", redactions, help="Fields stripped in real time before reaching agent context")
col5.metric("Avg latency (ms)", f"{avg_latency:.0f}", help="End-to-end gateway decision latency")

# ── Section 2 — Risk scorecard ────────────────────────────────────────────────
st.divider()
st.markdown("## Governance scorecard by use case")
st.caption(
    "Inherent risk is the pre-control judgment from policy design. "
    "Residual risk is computed live from what the gateway actually observed in this window."
)

for uc, label in USE_CASE_LABELS.items():
    sub = df_raw[df_raw["use_case"] == uc]  # always use full dataset for scorecard
    if sub.empty:
        continue

    deny_rate = (sub["decision"] == "deny").mean()
    redaction_rate = (sub["redactions"] > 0).mean()
    res_risk = residual_risk(deny_rate, redaction_rate)
    inh_risk = INHERENT_RISK[uc]
    inh_color = RISK_COLORS[inh_risk]
    res_color = RISK_COLORS[res_risk]

    with st.container(border=True):
        h_col, badge_col = st.columns([6, 1])
        h_col.markdown(f"### {label}")
        badge_col.markdown(
            f'<span style="background:{res_color};color:white;padding:4px 10px;border-radius:12px;font-size:0.8rem;font-weight:600">'
            f'Residual: {res_risk}</span>',
            unsafe_allow_html=True,
        )

        r1c1, r1c2, r1c3, r1c4 = st.columns([2, 2, 2, 1])
        r1c1.markdown(f"**Control pattern**  \n{GOVERNANCE_PATTERN[uc]}")
        r1c2.markdown(
            f"**Inherent risk**  \n"
            f'<span style="color:{inh_color};font-weight:600">{inh_risk}</span> — {INHERENT_RISK_DETAIL[uc]}',
            unsafe_allow_html=True,
        )
        r1c3.markdown(
            f"**Residual risk**  \n"
            f'<span style="color:{res_color};font-weight:600">{res_risk}</span> — {residual_risk_detail(deny_rate, redaction_rate, uc)}',
            unsafe_allow_html=True,
        )
        r1c4.metric("Calls (all time)", len(sub))

        with st.expander("Policy details & explainability"):
            exp_col1, exp_col2 = st.columns([1, 1])
            with exp_col1:
                st.markdown("**Active policy (agentgateway YAML)**")
                st.code(POLICY_SNIPPET[uc], language="yaml")
            with exp_col2:
                st.markdown("**How this control works**")
                st.markdown(CONTROL_EXPLANATION[uc])

                # Mini metrics
                m1, m2 = st.columns(2)
                m1.metric("Deny rate", f"{deny_rate:.0%}")
                m2.metric("Redaction rate", f"{redaction_rate:.0%}")

# ── Section 3 — Decisions over time ──────────────────────────────────────────
st.divider()
st.markdown("## Decisions over time")

time_df = (
    df.set_index("timestamp")
    .groupby([pd.Grouper(freq="3h"), "decision"])
    .size()
    .reset_index(name="count")
)
time_df.columns = ["timestamp", "decision", "count"]
time_df["color"] = time_df["decision"].map(DECISION_COLORS)

fig_time = px.bar(
    time_df,
    x="timestamp",
    y="count",
    color="decision",
    color_discrete_map=DECISION_COLORS,
    labels={"count": "Decisions", "timestamp": "Time", "decision": "Decision"},
    barmode="stack",
)
fig_time.update_layout(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    legend_title_text="Decision",
    margin=dict(l=0, r=0, t=10, b=0),
    height=280,
)
st.plotly_chart(fig_time, use_container_width=True)

# ── Section 4 — Agent activity monitor ───────────────────────────────────────
st.divider()
st.markdown("## Agent activity monitor")
st.caption("Per-agent call volume, control hit rates, token burn, and latency distribution.")

agents = df["agent_id"].unique().tolist()

for agent in sorted(agents):
    asub = df[df["agent_id"] == agent]
    a_deny_rate = (asub["decision"] == "deny").mean()
    a_tokens = int(asub["tokens_used"].sum())
    a_p50 = asub["latency_ms"].quantile(0.5)
    a_p95 = asub["latency_ms"].quantile(0.95)
    a_calls = len(asub)
    a_uc = asub["use_case"].iloc[0] if not asub.empty else ""
    a_label = USE_CASE_LABELS.get(a_uc, a_uc)

    with st.expander(f"{'🔴' if a_deny_rate > 0.3 else ('🟡' if a_deny_rate > 0.1 else '🟢')} **{agent}** · {a_label} · {a_calls} calls", expanded=False):
        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        mc1.metric("Total calls", a_calls)
        mc2.metric("Deny rate", f"{a_deny_rate:.0%}", delta_color="inverse",
                   delta=f"{int(a_deny_rate * a_calls)} denied")
        mc3.metric("Tokens used", f"{a_tokens:,}")
        mc4.metric("p50 latency (ms)", f"{a_p50:.0f}")
        mc5.metric("p95 latency (ms)", f"{a_p95:.0f}")

        # Timeline for this agent
        agent_time = (
            asub.set_index("timestamp")
            .groupby([pd.Grouper(freq="2h"), "decision"])
            .size()
            .reset_index(name="count")
        )
        agent_time.columns = ["timestamp", "decision", "count"]
        if not agent_time.empty:
            fig_agent = px.bar(
                agent_time, x="timestamp", y="count", color="decision",
                color_discrete_map=DECISION_COLORS, barmode="stack",
                height=160, labels={"count": "", "timestamp": ""},
            )
            fig_agent.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False, margin=dict(l=0, r=0, t=4, b=0),
            )
            st.plotly_chart(fig_agent, use_container_width=True, key=f"timeline_{agent}")

        # Tool breakdown
        tool_counts = asub.groupby(["tool", "decision"]).size().reset_index(name="count")
        if not tool_counts.empty:
            fig_tools = px.bar(
                tool_counts, x="tool", y="count", color="decision",
                color_discrete_map=DECISION_COLORS, barmode="stack",
                height=180, labels={"count": "Calls", "tool": "Tool / Model"},
            )
            fig_tools.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False, margin=dict(l=0, r=0, t=4, b=0),
            )
            st.plotly_chart(fig_tools, use_container_width=True, key=f"tools_{agent}")

# ── Section 5 — Decision explorer ─────────────────────────────────────────────
st.divider()
st.markdown("## Decision explorer")
st.caption(
    "Every gateway decision in the filtered window. "
    "Expand any denied or fallback row to see the policy that fired and what would change the outcome."
)

REASON_EXPLANATION = {
    "role!=claims-adjuster": (
        "**Policy fired:** `claims-pii-rbac` (01-claims-rbac.yaml)  \n"
        "**Rule:** `jwt.sub == \"claims-bot\"` does not satisfy the PII allow expression, "
        "which requires `jwt.claims[\"role\"] == \"claims-adjuster\"`.  \n"
        "**To allow:** The caller must present a JWT with `role=claims-adjuster` issued by the IdP. "
        "The agent identity (`claims-bot`) cannot be granted this — by design."
    ),
    "daily_token_budget_exceeded": (
        "**Policy fired:** `underwriting-token-budget` (02-underwriting-budget.yaml)  \n"
        "**Rule:** Team `underwriting` has consumed ≥ 500 000 tokens today. "
        "`onExceed: route-to-fallback` redirects to `claude-haiku-4-5` instead of hard-failing.  \n"
        "**To avoid fallback:** Either raise `maxTokensPerDay` in the policy, or reduce prompt size / call frequency."
    ),
    "tool_not_in_scope": (
        "**Policy fired:** `advisor-tool-scope` (03-advisor-redaction.yaml)  \n"
        "**Rule:** Only `search_kb` and `get_product_summary` are in the allow list. "
        "`delete_client_record` is not — and `denyByDefault: true` blocks it.  \n"
        "**To allow:** Explicitly add the tool to `matchExpressions` in the policy. "
        "This is intentional: any new tool added to the MCP server is blocked until reviewed."
    ),
}

# Decision filter pills
pill_col1, pill_col2, pill_col3, pill_col4 = st.columns(4)
show_allow = pill_col1.checkbox("✅ Allow", value=True)
show_deny = pill_col2.checkbox("🚫 Deny", value=True)
show_fallback = pill_col3.checkbox("⚠️ Fallback", value=True)

decisions_to_show = []
if show_allow:
    decisions_to_show.append("allow")
if show_deny:
    decisions_to_show.append("deny")
if show_fallback:
    decisions_to_show.append("route-to-fallback")

explorer_df = df[df["decision"].isin(decisions_to_show)].sort_values("timestamp", ascending=False)

show_cols = [c for c in [
    "timestamp", "use_case", "agent_id", "role", "tool", "action",
    "decision", "reason", "redactions", "tokens_used", "latency_ms",
] if c in explorer_df.columns]

# Colour-code the decision column
def style_decision(val):
    colors = {"allow": "#c6f6d5", "deny": "#fed7d7", "route-to-fallback": "#feebc8"}
    bg = colors.get(val, "")
    return f"background-color: {bg}"

styled = explorer_df[show_cols].style.applymap(style_decision, subset=["decision"])
st.dataframe(styled, use_container_width=True, hide_index=True)

# Expandable explainability for non-allow events
non_allow = explorer_df[explorer_df["decision"] != "allow"]
if not non_allow.empty:
    st.markdown("### Why these decisions were made")
    for _, row in non_allow.iterrows():
        reason = row.get("reason", "")
        explanation = REASON_EXPLANATION.get(reason)
        icon = "🚫" if row["decision"] == "deny" else "⚠️"
        label = (
            f"{icon} **{row['decision'].upper()}** · {row['agent_id']} → `{row['tool']}` "
            f"· {row['timestamp'].strftime('%b %d %H:%M')}"
        )
        if explanation:
            with st.expander(label):
                st.markdown(explanation)
                st.caption(f"Raw reason field: `{reason}`")
        else:
            with st.expander(label):
                st.markdown(f"Reason: `{reason or 'not specified'}`")

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Built on [agentgateway](https://agentgateway.dev) · "
    "Open source (Linux Foundation / AAIF) · "
    "Governance report for RBC Insurance agentic AI use cases · "
    "Designed to slot into the AI & ML Governance Command Centre."
)
