"""
Agentic AI Governance Gateway — Command Centre
-----------------------------------------------
Governance scorecard, agent monitor, and decision log for banking and
financial-services AI agent use cases, powered by agentgateway
(open-source LLM/MCP/A2A data plane — Linux Foundation / AAIF).

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

# ---- Banking use cases ----
BANKING_USE_CASES = {
    "next_best_action": "Next Best Action Agent",
    "mortgage_fraud":   "Mortgage Fraud Detection Agent",
    "wealth_advisor":   "Wealth Advisor Assist Agent",
    "aml_monitoring":   "AML Transaction Monitor",
}

# ---- Financial services / insurance use cases ----
INSURANCE_USE_CASES = {
    "claims_triage":     "Claims Triage Agent",
    "underwriting_risk": "Underwriting Risk-Scoring Agent",
    "advisor_assist":    "Advisor Assist Agent",
}

USE_CASE_LABELS = {**BANKING_USE_CASES, **INSURANCE_USE_CASES}

USE_CASE_ICONS = {
    "next_best_action":  "🎯",
    "mortgage_fraud":    "🏠",
    "wealth_advisor":    "💼",
    "aml_monitoring":    "🔍",
    "claims_triage":     "📋",
    "underwriting_risk": "⚖️",
    "advisor_assist":    "🧑‍💼",
}

USE_CASE_SECTOR = {
    "next_best_action":  "Banking",
    "mortgage_fraud":    "Banking",
    "wealth_advisor":    "Banking",
    "aml_monitoring":    "Banking",
    "claims_triage":     "Insurance",
    "underwriting_risk": "Insurance",
    "advisor_assist":    "Insurance",
}

INHERENT_RISK = {
    "next_best_action":  "High",
    "mortgage_fraud":    "High",
    "wealth_advisor":    "High",
    "aml_monitoring":    "Critical",
    "claims_triage":     "High",
    "underwriting_risk": "Medium",
    "advisor_assist":    "High",
}

INHERENT_RISK_DETAIL = {
    "next_best_action":  "Autonomous agent accessing full customer financial history to generate personalised offers.",
    "mortgage_fraud":    "LLM scoring regulated mortgage applications — model drift could breach fair-lending obligations.",
    "wealth_advisor":    "Advisor-facing agent querying knowledge base that may surface account numbers or SINs.",
    "aml_monitoring":    "Agent monitoring transaction streams — autonomous account-freezing would be irreversible without human sign-off.",
    "claims_triage":     "PII exposure via an autonomous agent processing claimant records.",
    "underwriting_risk": "Cost runaway and model drift on a regulated underwriting decision.",
    "advisor_assist":    "PII leakage (SIN, policy numbers, banking IDs) into an advisor-facing chat surface.",
}

GOVERNANCE_PATTERN = {
    "next_best_action":  "Tool-level RBAC — CEL policy gates financial history access",
    "mortgage_fraud":    "Token budget cap + pinned-model routing (regulated decision)",
    "wealth_advisor":    "Response-side PII redaction guardrail",
    "aml_monitoring":    "Tool scope enforcement — freeze action blocked, human escalation required",
    "claims_triage":     "Tool-level RBAC — CEL policy gates PII access",
    "underwriting_risk": "Token budget cap + pinned-model routing (regulated decision)",
    "advisor_assist":    "Response-side PII redaction guardrail + tool scope enforcement",
}

POLICY_SNIPPET = {
    "next_best_action": """\
# 01-nba-rbac.yaml
matchExpressions:
  - 'jwt.sub == "nba-agent" && mcp.tool.name in ["get_customer_profile","recommend_offer"]'
  - 'jwt.claims["role"] == "relationship-manager" && mcp.tool.name == "access_financial_history"'
denyByDefault: true""",

    "mortgage_fraud": """\
# 02-fraud-budget.yaml
budget:
  scope: per-team
  team: mortgage-risk
  maxTokensPerDay: 500000
  onExceed: route-to-fallback
modelPin:
  requirePinnedVersion: true    # OSFI E-23 / SR 11-7
audit:
  logPrompt: true
  logCompletion: true
  retentionDays: 2555           # 7 years""",

    "wealth_advisor": """\
# 03-wealth-advisor-redaction.yaml
guardrails:
  direction: response
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
authorization:
  matchExpressions:
    - 'mcp.tool.name in ["search_products","get_client_summary"]'
  denyByDefault: true""",

    "aml_monitoring": """\
# 04-aml-scope.yaml
authorization:
  matchExpressions:
    - 'mcp.tool.name in ["get_transaction_history","flag_transaction"]'
  denyByDefault: true   # freeze_account blocked until human approves
audit:
  logPrompt: true
  logCompletion: true
  retentionDays: 2555   # FINTRAC requirement""",

    "claims_triage": """\
# 05-claims-rbac.yaml
matchExpressions:
  - 'jwt.sub == "claims-bot" && mcp.tool.name in ["get_claim","escalate_claim"]'
  - 'jwt.claims["role"] == "claims-adjuster" && mcp.tool.name == "access_pii"'
denyByDefault: true
rateLimit:
  requestsPerMinute: 60
  scope: per-agent-identity""",

    "underwriting_risk": """\
# 06-underwriting-budget.yaml
budget:
  scope: per-team
  team: underwriting
  maxTokensPerDay: 500000
  onExceed: route-to-fallback
modelPin:
  requirePinnedVersion: true    # OSFI E-23
audit:
  logPrompt: true
  logCompletion: true
  retentionDays: 2555""",

    "advisor_assist": """\
# 07-advisor-redaction.yaml
guardrails:
  direction: response
  rules:
    - name: sin-redaction
      pattern: '\\b\\d{3}-\\d{3}-\\d{3}\\b'
      action: redact
    - name: policy-number-redaction
      pattern: '\\bPOL-\\d{8}\\b'
      action: redact
    - name: banking-redaction
      pattern: '\\b\\d{3}-\\d{3}-\\d{7,12}\\b'
      action: redact
authorization:
  matchExpressions:
    - 'mcp.tool.name in ["search_kb","get_product_summary"]'
  denyByDefault: true""",
}

CONTROL_EXPLANATION = {
    "next_best_action": (
        "The gateway enforces CEL-based RBAC on every MCP tool call. `nba-agent` can fetch "
        "profiles and push offers but is structurally blocked from `access_financial_history`. "
        "Only a JWT with `relationship-manager` role (IdP-issued) passes the allow expression."
    ),
    "mortgage_fraud": (
        "Daily token consumption is tracked per team. When `mortgage-risk` crosses 500k tokens, "
        "calls are rerouted to `claude-haiku-4-5` rather than hard-failing. Model pinning ensures "
        "every scoring decision cites an auditable version (OSFI E-23 / SR 11-7)."
    ),
    "wealth_advisor": (
        "Every tool response from the knowledge base is scanned before it enters the agent's "
        "context window. Account numbers, SINs, and banking IDs are redacted in real time — "
        "the agent never sees raw PII. Tool scope blocks anything outside the allow list."
    ),
    "aml_monitoring": (
        "`freeze_account` is explicitly out of scope. Any attempt by the agent to freeze an "
        "account is denied at the gateway — enforcing human-in-the-loop for all irreversible "
        "financial actions. `denyByDefault` blocks any future tools until reviewed."
    ),
    "claims_triage": (
        "`claims-bot` can read and escalate claims but is structurally blocked from `access_pii`. "
        "Only a JWT carrying `claims-adjuster` (IdP-issued) can pull PII. Rate limiting at "
        "60 req/min per agent prevents bulk extraction attempts."
    ),
    "underwriting_risk": (
        "Daily token cap with fallback routing preserves throughput while controlling cost. "
        "Model pinning ensures every underwriting decision references an exact, auditable model "
        "version for regulatory documentation. Full prompt/completion logs retained 7 years."
    ),
    "advisor_assist": (
        "SINs, policy numbers, and banking IDs are redacted from every tool response before "
        "the agent sees them. Tool scope enforcement blocks destructive operations like "
        "`delete_client_record` — the agent can only read, never write or delete."
    ),
}

REASON_EXPLANATION = {
    "role!=relationship-manager": (
        "**Policy:** `01-nba-rbac.yaml`  \n"
        "**Rule:** Caller does not carry `role=relationship-manager` in JWT.  \n"
        "**To allow:** Must originate from a human relationship manager with an IdP-issued role claim."
    ),
    "role!=claims-adjuster": (
        "**Policy:** `05-claims-rbac.yaml`  \n"
        "**Rule:** Caller (`claims-bot`) does not carry `role=claims-adjuster` in JWT.  \n"
        "**To allow:** Must originate from a verified human adjuster — agent identity cannot be elevated."
    ),
    "daily_token_budget_exceeded": (
        "**Policy:** `02-fraud-budget.yaml` / `06-underwriting-budget.yaml`  \n"
        "**Rule:** Team has consumed ≥ 500k tokens today. `onExceed: route-to-fallback` redirects "
        "to `claude-haiku-4-5` rather than hard-failing.  \n"
        "**To avoid:** Raise `maxTokensPerDay`, reduce prompt size, or spread load across the day."
    ),
    "tool_not_in_scope": (
        "**Policy:** `03-wealth-advisor-redaction.yaml` / `04-aml-scope.yaml` / `07-advisor-redaction.yaml`  \n"
        "**Rule:** Tool is not in the explicit allow list. `denyByDefault: true` blocks it.  \n"
        "**To allow:** Add tool to `matchExpressions` after security review — prevents capability creep."
    ),
}

RISK_COLORS  = {"Critical": "#742a2a", "High": "#e53e3e", "Medium": "#dd6b20", "Low": "#38a169"}
DECISION_COLORS = {
    "allow":             "#38a169",
    "deny":              "#e53e3e",
    "route-to-fallback": "#dd6b20",
}
DECISION_BG = {
    "allow":             "#c6f6d5",
    "deny":              "#fed7d7",
    "route-to-fallback": "#feebc8",
}
DECISION_ICONS = {
    "allow":             "✅",
    "deny":              "🚫",
    "route-to-fallback": "⚠️",
}


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data
def load_logs(file) -> pd.DataFrame:
    if hasattr(file, "read"):
        lines = file.read().decode("utf-8").splitlines()
    else:
        lines = Path(file).read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["redactions"]  = df.get("redactions",  pd.Series(dtype=float)).fillna(0).astype(int)
    df["tokens_used"] = df.get("tokens_used", pd.Series(dtype=float)).fillna(0).astype(int)
    return df


def residual_risk(deny_rate: float, redaction_rate: float) -> str:
    s = max(deny_rate, redaction_rate)
    if s < 0.01:  return "Low"
    if s < 0.15:  return "Low"
    if s < 0.40:  return "Medium"
    return "High"


def residual_detail(deny_rate: float, redaction_rate: float) -> str:
    s = max(deny_rate, redaction_rate)
    if s < 0.01:  return "No violations observed — controls are passive."
    if s < 0.15:  return f"Isolated intercepts ({deny_rate:.0%} deny · {redaction_rate:.0%} redaction). Policy holding."
    if s < 0.40:  return f"Recurring hits ({deny_rate:.0%} deny · {redaction_rate:.0%} redaction). Review scope."
    return f"Frequent hits ({deny_rate:.0%} deny · {redaction_rate:.0%} redaction). Escalate."


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
        help="Export from ./logs/agentgateway-audit.jsonl after running the gateway locally.",
    )
    if not uploaded:
        st.info("Showing synthetic sample data.", icon="ℹ️")
    st.divider()
    st.markdown("### Filters")

df_raw = load_logs(uploaded) if uploaded is not None else load_logs(DEFAULT_LOG_PATH)

with st.sidebar:
    uc_reverse = {v: k for k, v in USE_CASE_LABELS.items()}

    # Group use cases by sector in the selectbox
    all_uc_labels = ["All"] + [
        f"🏦 {USE_CASE_LABELS[k]}" for k in BANKING_USE_CASES
    ] + [
        f"📑 {USE_CASE_LABELS[k]}" for k in INSURANCE_USE_CASES
    ]
    uc_filter_display = st.selectbox("Use case", all_uc_labels)
    # Strip sector prefix for lookup
    uc_filter_clean = uc_filter_display.replace("🏦 ", "").replace("📑 ", "")

    agent_options  = ["All"] + sorted(df_raw["agent_id"].unique().tolist())
    agent_filter   = st.selectbox("Agent", agent_options)

    decision_options = ["All"] + sorted(df_raw["decision"].unique().tolist())
    decision_filter  = st.selectbox("Decision", decision_options)

    min_date   = df_raw["timestamp"].dt.date.min()
    max_date   = df_raw["timestamp"].dt.date.max()
    date_range = st.date_input("Date range", value=(min_date, max_date),
                               min_value=min_date, max_value=max_date)

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
Every decision was made at the **gateway layer** before reaching any tool or model.
        """
    )

# ── Apply filters ─────────────────────────────────────────────────────────────
df = df_raw.copy()
if uc_filter_clean != "All":
    uc_key = uc_reverse.get(uc_filter_clean)
    if uc_key:
        df = df[df["use_case"] == uc_key]
if agent_filter != "All":
    df = df[df["agent_id"] == agent_filter]
if decision_filter != "All":
    df = df[df["decision"] == decision_filter]
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    df = df[
        (df["timestamp"].dt.date >= date_range[0]) &
        (df["timestamp"].dt.date <= date_range[1])
    ]

# ── Header ────────────────────────────────────────────────────────────────────
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
c4.metric("PII redactions applied", redactions, help="Stripped before agent context window")
c5.metric("Avg latency (ms)", f"{avg_lat:.0f}")

# ── Governance scorecard ──────────────────────────────────────────────────────
st.divider()
st.markdown("## Governance scorecard")
st.caption(
    "Inherent risk = pre-control judgment from policy design. "
    "Residual risk = computed live from what the gateway observed in this window."
)

for sector, uc_group in [("🏦 Banking", BANKING_USE_CASES), ("📑 Financial Services / Insurance", INSURANCE_USE_CASES)]:
    sector_ucs = [uc for uc in uc_group if uc in df_raw["use_case"].values]
    if not sector_ucs:
        continue
    st.markdown(f"**{sector}**")
    for uc in sector_ucs:
        label = USE_CASE_LABELS[uc]
        icon  = USE_CASE_ICONS[uc]
        sub   = df_raw[df_raw["use_case"] == uc]

        deny_rate      = (sub["decision"] == "deny").mean()
        redaction_rate = (sub["redactions"] > 0).mean()
        res_risk       = residual_risk(deny_rate, redaction_rate)
        inh_risk       = INHERENT_RISK[uc]
        inh_color      = RISK_COLORS.get(inh_risk, "#718096")
        res_color      = RISK_COLORS.get(res_risk, "#718096")

        with st.container(border=True):
            h_col, badge_col = st.columns([7, 1])
            h_col.markdown(f"#### {icon} {label}")
            badge_col.markdown(
                f'<div style="text-align:right;margin-top:6px">'
                f'<span style="background:{res_color};color:white;padding:3px 10px;'
                f'border-radius:10px;font-size:0.78rem;font-weight:600">Residual: {res_risk}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            r1, r2, r3, r4 = st.columns([2, 2, 2, 1])
            r1.markdown(f"**Control pattern**  \n{GOVERNANCE_PATTERN[uc]}")
            r2.markdown(
                f"**Inherent risk**  \n"
                f'<span style="color:{inh_color};font-weight:600">{inh_risk}</span> — '
                f"{INHERENT_RISK_DETAIL[uc]}",
                unsafe_allow_html=True,
            )
            r3.markdown(
                f"**Residual risk**  \n"
                f'<span style="color:{res_color};font-weight:600">{res_risk}</span> — '
                f"{residual_detail(deny_rate, redaction_rate)}",
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
    color_discrete_map=DECISION_COLORS, barmode="stack",
    labels={"count": "Decisions", "timestamp": "", "decision": "Decision"},
)
fig_time.update_layout(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    legend_title_text="Decision", margin=dict(l=0, r=0, t=10, b=0), height=280,
)
st.plotly_chart(fig_time, use_container_width=True, key="main_timeline")

# ── Agent activity monitor ────────────────────────────────────────────────────
st.divider()
st.markdown("## Agent activity monitor")
st.caption("Per-agent call volume, control hit rates, token burn, and latency.")

for agent in sorted(df["agent_id"].unique()):
    asub       = df[df["agent_id"] == agent]
    a_deny_rt  = (asub["decision"] == "deny").mean()
    a_tokens   = int(asub["tokens_used"].sum())
    a_p50      = asub["latency_ms"].quantile(0.50)
    a_p95      = asub["latency_ms"].quantile(0.95)
    a_calls    = len(asub)
    a_uc       = asub["use_case"].mode()[0] if not asub.empty else ""
    a_label    = USE_CASE_LABELS.get(a_uc, a_uc)
    a_icon     = USE_CASE_ICONS.get(a_uc, "🤖")
    status     = "🔴" if a_deny_rt > 0.30 else ("🟡" if a_deny_rt > 0.10 else "🟢")

    with st.expander(f"{status} **{agent}** · {a_icon} {a_label} · {a_calls} calls"):
        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        mc1.metric("Total calls", a_calls)
        mc2.metric("Deny rate", f"{a_deny_rt:.0%}",
                   delta=f"{int(a_deny_rt * a_calls)} denied", delta_color="inverse")
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

# ── Decision log ──────────────────────────────────────────────────────────────
st.divider()
st.markdown("## Decision log")
st.caption(
    "Tamper-evident access log as emitted by agentgateway — one entry per gateway decision. "
    "Expand any denied or fallback entry to see which policy fired and why."
)

# Filter pills
pill1, pill2, pill3, _, _ = st.columns([1, 1, 1, 1, 3])
show_allow    = pill1.checkbox("✅ Allow",    value=True)
show_deny     = pill2.checkbox("🚫 Deny",     value=True)
show_fallback = pill3.checkbox("⚠️ Fallback", value=True)

to_show = (
    (["allow"]             if show_allow    else []) +
    (["deny"]              if show_deny     else []) +
    (["route-to-fallback"] if show_fallback else [])
)
log_df = df[df["decision"].isin(to_show)].sort_values("timestamp", ascending=False)

# Render as styled log rows
LOG_ROW = """
<div style="
  display:flex; align-items:center; gap:12px;
  padding:8px 12px; margin-bottom:4px; border-radius:6px;
  background:{bg}; font-family:monospace; font-size:0.82rem; line-height:1.4;
">
  <span style="min-width:130px; color:#4a5568;">{ts}</span>
  <span style="
    min-width:90px; text-align:center; font-weight:700;
    background:{badge_bg}; color:{badge_fg};
    padding:2px 8px; border-radius:8px; font-size:0.75rem;
  ">{decision}</span>
  <span style="min-width:160px; color:#2d3748; font-weight:600;">{agent}</span>
  <span style="color:#718096;">→</span>
  <span style="min-width:180px; color:#2b6cb0;">{tool}</span>
  <span style="color:#718096; font-size:0.75rem; flex:1">{use_case_label}</span>
  {extra}
</div>
"""

BADGE_STYLES = {
    "allow":             ("background:#c6f6d5", "#276749", "#f0fff4"),
    "deny":              ("background:#fed7d7", "#9b2c2c", "#fff5f5"),
    "route-to-fallback": ("background:#feebc8", "#7b341e", "#fffaf0"),
}

html_rows = []
expandable_rows = []

for _, row in log_df.iterrows():
    decision = row["decision"]
    badge_bg, badge_fg, row_bg = BADGE_STYLES.get(decision, ("background:#e2e8f0", "#2d3748", "#f7fafc"))
    ts    = row["timestamp"].strftime("%b %d  %H:%M:%S")
    agent = row.get("agent_id", "")
    tool  = row.get("tool", "")
    uc    = row.get("use_case", "")
    uc_label = USE_CASE_LABELS.get(uc, uc)

    extras = []
    if row.get("redactions", 0) > 0:
        extras.append(f'<span style="background:#bee3f8;color:#2a4365;padding:1px 6px;border-radius:6px;font-size:0.72rem">✂️ {int(row["redactions"])} redacted</span>')
    if row.get("tokens_used", 0) > 0:
        extras.append(f'<span style="color:#718096">{int(row["tokens_used"]):,} tok</span>')
    if row.get("latency_ms"):
        extras.append(f'<span style="color:#a0aec0">{int(row["latency_ms"])}ms</span>')
    extra_html = " &nbsp;".join(extras)

    html_rows.append(LOG_ROW.format(
        bg=row_bg, ts=ts,
        badge_bg=badge_bg, badge_fg=badge_fg,
        decision=decision.upper().replace("-", "‑"),
        agent=agent, tool=tool, use_case_label=uc_label,
        extra=extra_html,
    ))

    if decision != "allow":
        expandable_rows.append(row)

# Header row
st.markdown(
    '<div style="display:flex;gap:12px;padding:4px 12px;font-size:0.72rem;'
    'color:#a0aec0;font-family:monospace;border-bottom:1px solid #e2e8f0;margin-bottom:4px">'
    '<span style="min-width:130px">TIMESTAMP</span>'
    '<span style="min-width:90px;text-align:center">DECISION</span>'
    '<span style="min-width:160px">AGENT</span>'
    '<span style="min-width:16px"></span>'
    '<span style="min-width:180px">TOOL / MODEL</span>'
    '<span>USE CASE</span>'
    '</div>',
    unsafe_allow_html=True,
)
st.markdown("".join(html_rows), unsafe_allow_html=True)

# Expandable policy explanations for non-allow events
if expandable_rows:
    st.markdown("### Policy explanations")
    st.caption("Why each denied or fallback decision was made, and what would change the outcome.")
    for row in expandable_rows:
        reason      = str(row.get("reason", ""))
        explanation = REASON_EXPLANATION.get(reason)
        icon        = DECISION_ICONS.get(row["decision"], "•")
        label       = (
            f"{icon} **{row['decision'].upper()}** · "
            f"{row['agent_id']} → `{row['tool']}` · "
            f"{row['timestamp'].strftime('%b %d %H:%M')}"
        )
        with st.expander(label):
            if explanation:
                st.markdown(explanation)
            if reason:
                st.caption(f"Raw reason field: `{reason}`")

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Built on [agentgateway](https://agentgateway.dev) · "
    "Open source · Linux Foundation / AAIF · "
    "Agentic AI governance for financial services."
)
