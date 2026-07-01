"""
Agentic AI Governance Gateway — Command Centre
-----------------------------------------------
Governance scorecard, agent monitor, and decision explorer for four
banking AI agent use cases, powered by agentgateway (open-source
LLM/MCP/A2A data plane — Linux Foundation / AAIF).

Run:  streamlit run report.py
Data: sample_logs/audit-sample.jsonl (synthetic) or upload a real export.
"""

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agentic AI Governance Gateway",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ─────────────────────────────────────────────────────────────────
DEFAULT_LOG_PATH = Path(__file__).parent / "sample_logs" / "audit-sample.jsonl"

USE_CASE_LABELS = {
    "next_best_action":  "Next Best Action Agent",
    "mortgage_fraud":    "Mortgage Fraud Detection Agent",
    "wealth_advisor":    "Wealth Advisor Assist Agent",
    "aml_monitoring":    "AML Transaction Monitor",
}

USE_CASE_ICONS = {
    "next_best_action": "🎯",
    "mortgage_fraud":   "🏠",
    "wealth_advisor":   "💼",
    "aml_monitoring":   "🔍",
}

INHERENT_RISK = {
    "next_best_action": "High",
    "mortgage_fraud":   "High",
    "wealth_advisor":   "High",
    "aml_monitoring":   "Critical",
}

INHERENT_RISK_DETAIL = {
    "next_best_action": (
        "Autonomous agent accessing full customer profiles and financial history "
        "to generate personalised product recommendations — direct PII exposure risk."
    ),
    "mortgage_fraud":   (
        "LLM scoring regulated mortgage applications for fraud signals. "
        "Model drift or uncapped spend could skew credit decisions and breach fair-lending obligations."
    ),
    "wealth_advisor":   (
        "Advisor-facing agent querying a knowledge base that may surface account numbers, "
        "SINs, or banking identifiers in unstructured responses."
    ),
    "aml_monitoring":   (
        "Agent monitoring transaction streams for AML signals. Autonomous account-freezing "
        "capability would constitute an irreversible financial action without human authorisation."
    ),
}

GOVERNANCE_PATTERN = {
    "next_best_action": "Tool-level RBAC — CEL policy gates financial history access",
    "mortgage_fraud":   "Token budget cap + pinned-model routing (regulated decision)",
    "wealth_advisor":   "Response-side PII redaction guardrail",
    "aml_monitoring":   "Tool scope enforcement — freeze action blocked, human escalation required",
}

POLICY_SNIPPET = {
    "next_best_action": """\
# 01-nba-rbac.yaml — AgentgatewayPolicy
matchExpressions:
  # nba-agent may fetch profile and push recommendations, never financial history
  - 'jwt.sub == "nba-agent" && mcp.tool.name in ["get_customer_profile","recommend_offer"]'
  # only verified relationship managers (IdP claim) may read financial history
  - 'jwt.claims["role"] == "relationship-manager" && mcp.tool.name == "access_financial_history"'
denyByDefault: true""",

    "mortgage_fraud": """\
# 02-fraud-budget.yaml — AgentgatewayPolicy
budget:
  scope: per-team
  team: mortgage-risk
  maxTokensPerDay: 500000
  onExceed: route-to-fallback   # cheaper model, no hard failure
modelPin:
  requirePinnedVersion: true    # OSFI E-23 / SR 11-7 model-risk documentation
audit:
  logPrompt: true
  logCompletion: true
  retentionDays: 2555           # 7 years, matches lending record-retention norms""",

    "wealth_advisor": """\
# 03-advisor-redaction.yaml — AgentgatewayPolicy
guardrails:
  direction: response           # scan tool responses before agent sees them
  rules:
    - name: account-number-redaction
      pattern: '\\b\\d{7,12}\\b'
      action: redact
    - name: sin-redaction
      pattern: '\\b\\d{3}-\\d{3}-\\d{3}\\b'
      action: redact
    - name: banking-redaction
      pattern: '\\b\\d{3}-\\d{3}-\\d{7,12}\\b'
      action: redact
# Tool scope: only read/search tools permitted
authorization:
  matchExpressions:
    - 'mcp.tool.name in ["search_products","get_client_summary"]'
  denyByDefault: true""",

    "aml_monitoring": """\
# 04-aml-scope.yaml — AgentgatewayPolicy
authorization:
  matchExpressions:
    # monitor and flag only — account actions require human authorisation
    - 'mcp.tool.name in ["get_transaction_history","flag_transaction"]'
  denyByDefault: true   # freeze_account and any future tools blocked until reviewed
audit:
  logPrompt: true
  logCompletion: true
  retentionDays: 2555   # FINTRAC record-retention requirement""",
}

CONTROL_EXPLANATION = {
    "next_best_action": (
        "The gateway enforces a CEL-based RBAC rule on every MCP tool call. "
        "The `nba-agent` can fetch customer profiles and push offers, but is "
        "structurally blocked from calling `access_financial_history` — the rule "
        "is evaluated in the data plane before the request reaches the MCP server. "
        "Only a JWT carrying the `relationship-manager` role (issued by the IdP) "
        "may read full financial history, ensuring human accountability for every "
        "sensitive data access."
    ),
    "mortgage_fraud": (
        "The gateway tracks daily token consumption per team. When the "
        "`mortgage-risk` team crosses 500 000 tokens it automatically re-routes "
        "subsequent calls to `claude-haiku-4-5` instead of hard-failing — "
        "preserving throughput while capping cost. Model pinning ensures every "
        "fraud-scoring decision cites an exact, auditable model version, "
        "satisfying OSFI E-23 and SR 11-7 model-risk documentation requirements. "
        "Full prompt and completion logging with 7-year retention meets lending "
        "record-retention norms."
    ),
    "wealth_advisor": (
        "Every tool response from the knowledge base is scanned by the gateway "
        "before it enters the agent's context window. Regex rules redact account "
        "numbers, SINs, and banking identifiers in real time — the agent never "
        "sees raw PII and therefore cannot surface it in an advisor chat response. "
        "Tool scope is also enforced: only `search_products` and `get_client_summary` "
        "are permitted. Any tool added to the MCP server in future is blocked by "
        "default until explicitly reviewed and approved in the policy."
    ),
    "aml_monitoring": (
        "The AML monitor can observe and flag suspicious transactions, but the "
        "`freeze_account` tool is explicitly out of scope. Any attempt by the agent "
        "to freeze an account is denied at the gateway before it reaches the MCP "
        "server — enforcing a human-in-the-loop requirement for all irreversible "
        "financial actions. `denyByDefault: true` also ensures any new tools added "
        "to the server are blocked until reviewed, preventing capability creep. "
        "Full audit logging meets FINTRAC record-retention requirements."
    ),
}

REASON_EXPLANATION = {
    "role!=relationship-manager": (
        "**Policy fired:** `01-nba-rbac.yaml`  \n"
        "**Rule:** The caller (`nba-agent`) does not carry the `relationship-manager` "
        "role in its JWT. The allow expression requires "
        "`jwt.claims[\"role\"] == \"relationship-manager\"` to call `access_financial_history`.  \n"
        "**To allow:** The request must originate from a human relationship manager "
        "whose IdP-issued JWT carries the required role claim. The agent identity "
        "cannot be elevated to this role — by design."
    ),
    "daily_token_budget_exceeded": (
        "**Policy fired:** `02-fraud-budget.yaml`  \n"
        "**Rule:** Team `mortgage-risk` has consumed ≥ 500 000 tokens today. "
        "`onExceed: route-to-fallback` redirects to `claude-haiku-4-5` rather "
        "than hard-failing, preserving throughput at lower cost.  \n"
        "**To avoid fallback:** Raise `maxTokensPerDay` in the policy, reduce "
        "prompt size, or distribute load across the day."
    ),
    "tool_not_in_scope": (
        "**Policy fired:** `03-advisor-redaction.yaml` / `04-aml-scope.yaml`  \n"
        "**Rule:** The requested tool is not in the allow list. "
        "`denyByDefault: true` blocks any tool not explicitly permitted.  \n"
        "**To allow:** Add the tool to `matchExpressions` in the relevant policy "
        "after security review. This gate prevents capability creep — new MCP "
        "tools are blocked until consciously approved."
    ),
}

RISK_COLORS = {"Critical": "#742a2a", "High": "#e53e3e", "Medium": "#dd6b20", "Low": "#38a169"}
DECISION_COLORS = {
    "allow":            "#38a169",
    "deny":             "#e53e3e",
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


def residual_risk_detail(deny_rate: float, redaction_rate: float) -> str:
    signal = max(deny_rate, redaction_rate)
    if signal == 0:
        return "No violations observed in this window — controls are passive."
    if signal < 0.15:
        return f"Controls intercepted isolated attempts ({deny_rate:.0%} deny · {redaction_rate:.0%} redaction). Policy holding."
    if signal < 0.4:
        return f"Recurring control hits ({deny_rate:.0%} deny · {redaction_rate:.0%} redaction). Review policy scope."
    return f"Frequent control hits ({deny_rate:.0%} deny · {redaction_rate:.0%} redaction). Escalate for review."


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛡️ AgentGateway")
    st.caption(
        "Open-source LLM / MCP / A2A data plane  \n"
        "[agentgateway.dev](https://agentgateway.dev) · Linux Foundation / AAIF"
    )
    st.divider()

    st.markdown("### Data source")
    uploaded = st.file_uploader(
        "Upload agentgateway-audit.jsonl",
        type=["jsonl", "json", "log"],
        help="Drop in a real export from ./logs/agentgateway-audit.jsonl after running the gateway locally.",
    )
    if not uploaded:
        st.info("Showing synthetic sample data shaped like a real export.", icon="ℹ️")

    st.divider()
    st.markdown("### Filters")

df_raw = load_logs(uploaded) if uploaded is not None else load_logs(DEFAULT_LOG_PATH)

with st.sidebar:
    uc_reverse = {v: k for k, v in USE_CASE_LABELS.items()}
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
    st.markdown("### How it works")
    st.markdown(
        """
```
  Agent / LLM client
        │
        ▼
  ┌─────────────┐
  │agentgateway │◄── CEL policies
  │  data plane │    budget caps
  │             │    PII guardrails
  └──────┬──────┘
         │
    ┌────┴────┐
    ▼         ▼
  MCP       LLM
 Server    Provider
```
Every decision in this report was made at the **gateway layer** — before reaching any tool or model.
        """
    )

# ── Apply filters ─────────────────────────────────────────────────────────────
df = df_raw.copy()
if uc_filter != "All":
    df = df[df["use_case"] == uc_reverse[uc_filter]]
if agent_filter != "All":
    df = df[df["agent_id"] == agent_filter]
if decision_filter != "All":
    df = df[df["decision"] == decision_filter]
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    df = df[
        (df["timestamp"].dt.date >= date_range[0])
        & (df["timestamp"].dt.date <= date_range[1])
    ]

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 🛡️ Agentic AI Governance Gateway")
st.markdown(
    "**Control plane for four banking AI agent use cases** — decisioning, monitoring, and audit evidence "
    "captured by [agentgateway](https://agentgateway.dev) (open-source LLM/MCP/A2A data plane, "
    "Linux Foundation / AAIF). Every allow, deny, fallback, and redaction below is a policy "
    "decision made in the gateway layer, upstream of any tool or model."
)

# ── KPI strip ─────────────────────────────────────────────────────────────────
st.divider()
total = len(df)
denied = int((df["decision"] == "deny").sum())
fallback = int((df["decision"] == "route-to-fallback").sum())
redactions = int(df["redactions"].sum())
avg_latency = df["latency_ms"].mean() if total > 0 else 0
deny_pct = denied / total if total > 0 else 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total gateway decisions", total)
c2.metric("Denied", denied, delta=f"{deny_pct:.0%} deny rate", delta_color="inverse")
c3.metric("Routed to fallback", fallback, help="Budget exceeded → cheaper model, no hard failure")
c4.metric("PII redactions applied", redactions, help="Fields stripped before agent context window")
c5.metric("Avg latency (ms)", f"{avg_latency:.0f}", help="End-to-end gateway decision latency")

# ── Governance scorecard ──────────────────────────────────────────────────────
st.divider()
st.markdown("## Governance scorecard")
st.caption(
    "Inherent risk is the pre-control judgment from policy design. "
    "Residual risk is computed live from what the gateway actually observed in this window."
)

for uc, label in USE_CASE_LABELS.items():
    sub = df_raw[df_raw["use_case"] == uc]
    if sub.empty:
        continue

    deny_rate = (sub["decision"] == "deny").mean()
    redaction_rate = (sub["redactions"] > 0).mean()
    res_risk = residual_risk(deny_rate, redaction_rate)
    inh_risk = INHERENT_RISK[uc]
    inh_color = RISK_COLORS.get(inh_risk, "#718096")
    res_color = RISK_COLORS.get(res_risk, "#718096")
    icon = USE_CASE_ICONS[uc]

    with st.container(border=True):
        h_col, badge_col = st.columns([7, 1])
        h_col.markdown(f"### {icon} {label}")
        badge_col.markdown(
            f'<div style="text-align:right">'
            f'<span style="background:{res_color};color:white;padding:4px 12px;'
            f'border-radius:12px;font-size:0.8rem;font-weight:600">Residual: {res_risk}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        r1, r2, r3, r4 = st.columns([2, 2, 2, 1])
        r1.markdown(f"**Control pattern**  \n{GOVERNANCE_PATTERN[uc]}")
        r2.markdown(
            f"**Inherent risk**  \n"
            f'<span style="color:{inh_color};font-weight:600">{inh_risk}</span>  \n'
            f"{INHERENT_RISK_DETAIL[uc]}",
            unsafe_allow_html=True,
        )
        r3.markdown(
            f"**Residual risk**  \n"
            f'<span style="color:{res_color};font-weight:600">{res_risk}</span>  \n'
            f"{residual_risk_detail(deny_rate, redaction_rate)}",
            unsafe_allow_html=True,
        )
        r4.metric("Calls", len(sub))

        with st.expander("Policy & explainability"):
            pc1, pc2 = st.columns([1, 1])
            with pc1:
                st.markdown("**Active agentgateway policy**")
                st.code(POLICY_SNIPPET[uc], language="yaml")
            with pc2:
                st.markdown("**How this control works**")
                st.markdown(CONTROL_EXPLANATION[uc])
                m1, m2 = st.columns(2)
                m1.metric("Deny rate", f"{deny_rate:.0%}")
                m2.metric("Redaction rate", f"{redaction_rate:.0%}")

# ── Decisions over time ───────────────────────────────────────────────────────
st.divider()
st.markdown("## Decisions over time")

time_df = (
    df.set_index("timestamp")
    .groupby([pd.Grouper(freq="3h"), "decision"])
    .size()
    .reset_index(name="count")
)
time_df.columns = ["timestamp", "decision", "count"]

fig_time = px.bar(
    time_df, x="timestamp", y="count", color="decision",
    color_discrete_map=DECISION_COLORS,
    labels={"count": "Decisions", "timestamp": "", "decision": "Decision"},
    barmode="stack",
)
fig_time.update_layout(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    legend_title_text="Decision", margin=dict(l=0, r=0, t=10, b=0), height=280,
)
st.plotly_chart(fig_time, use_container_width=True, key="main_timeline")

# ── Agent activity monitor ────────────────────────────────────────────────────
st.divider()
st.markdown("## Agent activity monitor")
st.caption("Per-agent call volume, control hit rates, token burn, and latency distribution.")

for agent in sorted(df["agent_id"].unique()):
    asub = df[df["agent_id"] == agent]
    a_deny_rate = (asub["decision"] == "deny").mean()
    a_tokens = int(asub["tokens_used"].sum())
    a_p50 = asub["latency_ms"].quantile(0.5)
    a_p95 = asub["latency_ms"].quantile(0.95)
    a_calls = len(asub)
    a_uc = asub["use_case"].iloc[0] if not asub.empty else ""
    a_label = USE_CASE_LABELS.get(a_uc, a_uc)
    status = "🔴" if a_deny_rate > 0.3 else ("🟡" if a_deny_rate > 0.1 else "🟢")

    with st.expander(f"{status} **{agent}** · {a_label} · {a_calls} calls"):
        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        mc1.metric("Total calls", a_calls)
        mc2.metric("Deny rate", f"{a_deny_rate:.0%}", delta=f"{int(a_deny_rate * a_calls)} denied", delta_color="inverse")
        mc3.metric("Tokens used", f"{a_tokens:,}")
        mc4.metric("p50 latency ms", f"{a_p50:.0f}")
        mc5.metric("p95 latency ms", f"{a_p95:.0f}")

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
                height=150, labels={"count": "", "timestamp": ""},
            )
            fig_a.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False, margin=dict(l=0, r=0, t=4, b=0),
            )
            st.plotly_chart(fig_a, use_container_width=True, key=f"timeline_{agent}")

        tool_counts = asub.groupby(["tool", "decision"]).size().reset_index(name="count")
        if not tool_counts.empty:
            fig_t = px.bar(
                tool_counts, x="tool", y="count", color="decision",
                color_discrete_map=DECISION_COLORS, barmode="stack",
                height=180, labels={"count": "Calls", "tool": "Tool / Model"},
            )
            fig_t.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False, margin=dict(l=0, r=0, t=4, b=0),
            )
            st.plotly_chart(fig_t, use_container_width=True, key=f"tools_{agent}")

# ── Decision explorer ─────────────────────────────────────────────────────────
st.divider()
st.markdown("## Decision explorer")
st.caption(
    "Every gateway decision in the filtered window. "
    "Expand any denied or fallback row to see which policy fired and why."
)

pill1, pill2, pill3 = st.columns(3)
show_allow    = pill1.checkbox("✅ Allow",    value=True)
show_deny     = pill2.checkbox("🚫 Deny",     value=True)
show_fallback = pill3.checkbox("⚠️ Fallback", value=True)

decisions_to_show = (
    (["allow"] if show_allow else [])
    + (["deny"] if show_deny else [])
    + (["route-to-fallback"] if show_fallback else [])
)
explorer_df = df[df["decision"].isin(decisions_to_show)].sort_values("timestamp", ascending=False)

show_cols = [c for c in [
    "timestamp", "use_case", "agent_id", "role", "tool", "action",
    "decision", "reason", "redactions", "tokens_used", "latency_ms",
] if c in explorer_df.columns]


def style_decision(val):
    bg = {"allow": "#c6f6d5", "deny": "#fed7d7", "route-to-fallback": "#feebc8"}.get(val, "")
    return f"background-color: {bg}"


st.dataframe(
    explorer_df[show_cols].style.applymap(style_decision, subset=["decision"]),
    use_container_width=True,
    hide_index=True,
)

non_allow = explorer_df[explorer_df["decision"] != "allow"]
if not non_allow.empty:
    st.markdown("### Why these decisions were made")
    for _, row in non_allow.iterrows():
        reason = str(row.get("reason", ""))
        explanation = REASON_EXPLANATION.get(reason)
        icon = "🚫" if row["decision"] == "deny" else "⚠️"
        label = (
            f"{icon} **{row['decision'].upper()}** · {row['agent_id']} → "
            f"`{row['tool']}` · {row['timestamp'].strftime('%b %d %H:%M')}"
        )
        with st.expander(label):
            if explanation:
                st.markdown(explanation)
            st.caption(f"Raw reason field: `{reason or 'not specified'}`")

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Built on [agentgateway](https://agentgateway.dev) · "
    "Open source · Linux Foundation / AAIF · "
    "Agentic AI governance for financial services use cases."
)
