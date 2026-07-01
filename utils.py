"""
Shared constants, data loading, and risk logic for all pages.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

DEFAULT_LOG_PATH = Path(__file__).parent / "sample_logs" / "audit-sample.jsonl"

# ── Use cases ─────────────────────────────────────────────────────────────────
BANKING_USE_CASES = {
    "next_best_action": "Next Best Action Agent",
    "mortgage_fraud":   "Mortgage Fraud Detection Agent",
    "wealth_advisor":   "Wealth Advisor Assist Agent",
    "aml_monitoring":   "AML Transaction Monitor",
}

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

RISK_COLORS = {
    "Critical": "#742a2a",
    "High":     "#e53e3e",
    "Medium":   "#dd6b20",
    "Low":      "#38a169",
}

DECISION_COLORS = {
    "allow":             "#38a169",
    "deny":              "#e53e3e",
    "route-to-fallback": "#dd6b20",
}

DECISION_BG = {
    "allow":             ("#c6f6d5", "#276749", "#f0fff4"),
    "deny":              ("#fed7d7", "#9b2c2c", "#fff5f5"),
    "route-to-fallback": ("#feebc8", "#7b341e", "#fffaf0"),
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
    df["timestamp"]  = pd.to_datetime(df["timestamp"])
    df["redactions"]  = df.get("redactions",  pd.Series(dtype=float)).fillna(0).astype(int)
    df["tokens_used"] = df.get("tokens_used", pd.Series(dtype=float)).fillna(0).astype(int)
    return df


# ── Risk helpers ──────────────────────────────────────────────────────────────
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


# ── Sidebar (shared across all pages) ────────────────────────────────────────
def render_sidebar() -> tuple:
    """
    Renders the common sidebar and returns (df_raw, df_filtered, uploaded_file).
    Call this at the top of every page.
    """
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
            help="Export from ./logs/agentgateway-audit.jsonl after running the gateway.",
        )
        if not uploaded:
            st.info("Showing synthetic sample data.", icon="ℹ️")

        st.divider()
        st.markdown("### Filters")

    df_raw = load_logs(uploaded) if uploaded is not None else load_logs(DEFAULT_LOG_PATH)

    with st.sidebar:
        uc_reverse = {v: k for k, v in USE_CASE_LABELS.items()}
        all_uc_labels = ["All"] + [
            f"🏦 {USE_CASE_LABELS[k]}" for k in BANKING_USE_CASES
        ] + [
            f"📑 {USE_CASE_LABELS[k]}" for k in INSURANCE_USE_CASES
        ]
        uc_display  = st.selectbox("Use case", all_uc_labels)
        uc_clean    = uc_display.replace("🏦 ", "").replace("📑 ", "")

        agent_opts  = ["All"] + sorted(df_raw["agent_id"].unique().tolist())
        agent_sel   = st.selectbox("Agent", agent_opts)

        dec_opts    = ["All"] + sorted(df_raw["decision"].unique().tolist())
        dec_sel     = st.selectbox("Decision", dec_opts)

        min_d, max_d = df_raw["timestamp"].dt.date.min(), df_raw["timestamp"].dt.date.max()
        date_range  = st.date_input("Date range", value=(min_d, max_d),
                                    min_value=min_d, max_value=max_d)

        st.divider()
        st.markdown("### Architecture")
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
Every decision is made at the **gateway layer**.
            """
        )

    # Apply filters
    df = df_raw.copy()
    if uc_clean != "All":
        key = uc_reverse.get(uc_clean)
        if key:
            df = df[df["use_case"] == key]
    if agent_sel != "All":
        df = df[df["agent_id"] == agent_sel]
    if dec_sel != "All":
        df = df[df["decision"] == dec_sel]
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        df = df[
            (df["timestamp"].dt.date >= date_range[0]) &
            (df["timestamp"].dt.date <= date_range[1])
        ]

    return df_raw, df, uploaded
