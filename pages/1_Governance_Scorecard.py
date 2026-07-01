"""
Page 2 — Governance Scorecard
Per-use-case risk ratings, control patterns, policy snippets, and explainability.
"""

import streamlit as st

from utils import (
    BANKING_USE_CASES,
    CONTROL_EXPLANATION,
    GOVERNANCE_PATTERN,
    INHERENT_RISK,
    INHERENT_RISK_DETAIL,
    INSURANCE_USE_CASES,
    POLICY_SNIPPET,
    RISK_COLORS,
    USE_CASE_ICONS,
    USE_CASE_LABELS,
    USE_CASE_OWNERS,
    governance_score,
    render_sidebar,
    residual_detail,
    residual_risk,
    score_color,
)

df_raw, df, _ = render_sidebar()

st.markdown("# 📊 Governance Scorecard")
st.markdown(
    "Risk ratings, active controls, and policy explainability for every agent use case. "
    "**Inherent risk** is the pre-control judgment made at policy design time. "
    "**Residual risk** is computed live from what the gateway observed in the selected window."
)

for sector_label, uc_group in [
    ("🏦 Banking", BANKING_USE_CASES),
    ("📑 Financial Services / Insurance", INSURANCE_USE_CASES),
]:
    sector_ucs = [uc for uc in uc_group if uc in df_raw["use_case"].values]
    if not sector_ucs:
        continue

    st.divider()
    st.markdown(f"## {sector_label}")

    for uc in sector_ucs:
        label  = USE_CASE_LABELS[uc]
        icon   = USE_CASE_ICONS[uc]
        owner  = USE_CASE_OWNERS.get(uc, "")
        sub    = df_raw[df_raw["use_case"] == uc]

        deny_rate      = (sub["decision"] == "deny").mean()
        redaction_rate = (sub["redactions"] > 0).mean()
        avg_lat        = sub["latency_ms"].mean() if len(sub) else 0
        res            = residual_risk(deny_rate, redaction_rate)
        inh            = INHERENT_RISK[uc]
        inh_color      = RISK_COLORS.get(inh, "#718096")
        res_color      = RISK_COLORS.get(res, "#718096")
        score          = governance_score(1 - deny_rate, redaction_rate, avg_lat)
        sc             = score_color(score)

        with st.container(border=True):
            h_col, score_col, badge_col = st.columns([5, 1, 2])
            h_col.markdown(
                f"#### {icon} {label}  \n"
                f'<span style="color:#718096;font-size:0.78rem">{owner}</span>',
                unsafe_allow_html=True,
            )
            score_col.markdown(
                f'<div style="text-align:center;margin-top:4px">'
                f'<div style="font-size:1.8rem;font-weight:700;color:{sc};line-height:1">{score}</div>'
                f'<div style="font-size:0.7rem;color:#718096">gov score</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            badge_col.markdown(
                f'<div style="text-align:right;margin-top:10px">'
                f'<span style="background:{res_color};color:white;padding:3px 12px;'
                f'border-radius:10px;font-size:0.78rem;font-weight:600">'
                f'Residual: {res}</span></div>',
                unsafe_allow_html=True,
            )

            r1, r2, r3, r4 = st.columns([2, 2, 2, 1])
            r1.markdown(f"**Control pattern**  \n{GOVERNANCE_PATTERN[uc]}")
            r2.markdown(
                f"**Inherent risk**  \n"
                f'<span style="color:{inh_color};font-weight:600">{inh}</span> — '
                f"{INHERENT_RISK_DETAIL[uc]}",
                unsafe_allow_html=True,
            )
            r3.markdown(
                f"**Residual risk**  \n"
                f'<span style="color:{res_color};font-weight:600">{res}</span> — '
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

st.divider()
st.caption(
    "Built on [agentgateway](https://agentgateway.dev) · "
    "Open source · Linux Foundation / AAIF"
)
