# Agentic AI Governance Gateway — weekend project

A portfolio piece using [agentgateway](https://agentgateway.dev/) (open-source
LLM/MCP/A2A data plane, Linux Foundation / AAIF project) as the control plane
for three RBC Insurance agent use cases, with results reported through a
Streamlit module designed to slot into the AI & ML Governance Command Centre.

## Why agentgateway

It's the connectivity layer underneath an "Agentic AI Platform Engineering"
function — exactly the kind of infrastructure that role exists to operate.
Three governance capabilities map directly to inherent-vs-residual risk
controls:

| Capability | Mechanism | Used for |
|---|---|---|
| Decisioning | CEL-based `AgentgatewayPolicy` (RBAC) | Claims Triage — gate the `access_pii` tool |
| Decisioning | Token budget + model pinning | Underwriting — cap spend, force explainable model version |
| Monitoring/Governance | Response-side regex guardrails | Advisor Assist — redact SIN/policy/banking numbers in real time |
| Monitoring | OTEL access log (JSON) | All three — feeds the report below |

## Structure

```
config/config.yaml          # agentgateway routes for all 3 use cases
policies/01-claims-rbac.yaml          # RBAC: claims-bot vs claims-adjuster
policies/02-underwriting-budget.yaml  # token budget + model pinning
policies/03-advisor-redaction.yaml    # PII guardrail + tool scope
sample_logs/audit-sample.jsonl        # synthetic log, shaped like a real export
report.py                              # Streamlit governance scorecard
```

## Run it for real this weekend

1. Install agentgateway locally (binary, ~2 min):
   ```
   curl -sL https://agentgateway.dev/install | bash
   ```
2. Stand up two trivial mock MCP servers (`claims-mcp`, `advisor-kb-mcp`) —
   even a 20-line stdio script returning canned JSON is enough to exercise
   the policies. Point `config/config.yaml` at them.
3. Apply the policies in `policies/` and run:
   ```
   agentgateway -f config/config.yaml
   ```
4. Fire a handful of requests per use case (including a couple that should
   be denied/redacted on purpose) using the MCP inspector CLI or curl.
5. Your real decisions land in `./logs/agentgateway-audit.jsonl` in the same
   shape as `sample_logs/audit-sample.jsonl`.

## See the report now (no real gateway needed yet)

```
pip install streamlit pandas
streamlit run report.py
```

This runs immediately against the synthetic sample data. Once you've run
agentgateway for real, either point `DEFAULT_LOG_PATH` at your real log file
or use the sidebar upload — no code changes needed, since the schema matches.

## Next step toward the Command Centre

Once you're happy with the standalone report, the same `load_logs()` /
scorecard logic can become a page inside `ai-ml-gov.lovable.app` — pass
real gateway exports in as the data source for a "Control Plane" tab
alongside your existing risk register.
