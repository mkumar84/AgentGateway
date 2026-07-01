# Agentic AI Governance Gateway

A portfolio piece using [agentgateway](https://agentgateway.dev/) (open-source
LLM/MCP/A2A data plane, Linux Foundation / AAIF) as the control plane for four
banking AI agent use cases, with results surfaced through a Streamlit governance
scorecard.

## Use cases

| Agent | Risk being controlled | Governance pattern |
|---|---|---|
| **Next Best Action** | Autonomous agent accessing full customer financial history | Tool-level RBAC (CEL policy) |
| **Mortgage Fraud Detection** | Model drift and cost runaway on a regulated credit decision | Token budget cap + pinned-model routing |
| **Wealth Advisor Assist** | PII leakage (account numbers, SINs) into advisor chat | Response-side PII redaction guardrail |
| **AML Transaction Monitor** | Agent autonomously freezing accounts without human authorisation | Tool scope enforcement (denyByDefault) |

## Why agentgateway

It is the connectivity layer underneath an "Agentic AI Platform Engineering"
function — the infrastructure that governs what agents can do, what models they
can call, and what data they can see, before requests reach any tool or provider.

| Capability | Mechanism | Used for |
|---|---|---|
| Decisioning | CEL-based `AgentgatewayPolicy` (RBAC) | NBA — gate `access_financial_history` |
| Decisioning | Token budget + model pinning | Mortgage Fraud — cap spend, pin model version |
| Monitoring/Governance | Response-side regex guardrails | Wealth Advisor — redact PII in real time |
| Monitoring/Governance | Tool scope enforcement | AML Monitor — block `freeze_account` |
| Monitoring | OTEL access log (JSON) | All four — feeds the report |

## Structure

```
config.yaml                       # agentgateway routes for all 4 use cases
01-claims-rbac.yaml               # RBAC: nba-agent vs relationship-manager
02-underwriting-budget.yaml       # token budget + model pinning
03-advisor-redaction.yaml         # PII guardrail + tool scope
sample_logs/audit-sample.jsonl    # synthetic log, shaped like a real export
report.py                         # Streamlit governance scorecard
```

## Run locally (no gateway needed)

```bash
pip install streamlit pandas plotly
streamlit run report.py
```

Opens immediately against the synthetic sample data.

## Run with a real gateway

1. Install agentgateway (~2 min):
   ```bash
   curl -sL https://agentgateway.dev/install | bash
   ```
2. Stand up mock MCP servers for each use case (a 20-line stdio script
   returning canned JSON is sufficient to exercise the policies).
3. Run the gateway:
   ```bash
   agentgateway -f config.yaml
   ```
4. Fire requests per use case (including deliberate deny/redact cases) via
   the MCP Inspector CLI or curl.
5. Real decisions land in `./logs/agentgateway-audit.jsonl` — drop that file
   into the sidebar upload widget or point `DEFAULT_LOG_PATH` at it.
