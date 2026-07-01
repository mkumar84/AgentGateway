"""
Page 4 — Decision Log
Tamper-evident access log with log-row rendering and policy explanations
for every denied or fallback event.
"""

import streamlit as st

from utils import (
    DECISION_BG,
    DECISION_ICONS,
    REASON_EXPLANATION,
    USE_CASE_LABELS,
    render_sidebar,
)

st.set_page_config(
    page_title="AgentGateway · Decision Log",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded",
)

df_raw, df, _ = render_sidebar()

st.markdown("# 📜 Decision Log")
st.markdown(
    "Tamper-evident access log of every routed decision as emitted by agentgateway. "
    "Expand any denied or fallback entry to see which policy fired and why."
)
st.divider()

# Filter pills
p1, p2, p3, _, _ = st.columns([1, 1, 1, 1, 3])
show_allow    = p1.checkbox("✅ Allow",    value=True)
show_deny     = p2.checkbox("🚫 Deny",     value=True)
show_fallback = p3.checkbox("⚠️ Fallback", value=True)

to_show = (
    (["allow"]             if show_allow    else []) +
    (["deny"]              if show_deny     else []) +
    (["route-to-fallback"] if show_fallback else [])
)

log_df = df[df["decision"].isin(to_show)].sort_values("timestamp", ascending=False)

st.caption(f"Showing **{len(log_df)}** of **{len(df)}** decisions in selected window.")

# ── Log header ────────────────────────────────────────────────────────────────
st.markdown(
    '<div style="display:flex;gap:12px;padding:5px 14px;'
    'font-size:0.7rem;color:#a0aec0;font-family:monospace;'
    'border-bottom:1px solid #e2e8f0;margin-bottom:2px">'
    '<span style="min-width:135px">TIMESTAMP</span>'
    '<span style="min-width:110px;text-align:center">DECISION</span>'
    '<span style="min-width:170px">AGENT</span>'
    '<span style="min-width:12px"></span>'
    '<span style="min-width:190px">TOOL / MODEL</span>'
    '<span style="flex:1">USE CASE</span>'
    '<span style="min-width:80px;text-align:right">LATENCY</span>'
    '</div>',
    unsafe_allow_html=True,
)

# ── Log rows ──────────────────────────────────────────────────────────────────
LOG_ROW = (
    '<div style="display:flex;align-items:center;gap:12px;'
    'padding:7px 14px;margin-bottom:3px;border-radius:6px;'
    'background:{row_bg};font-family:monospace;font-size:0.81rem;line-height:1.4;">'
    '<span style="min-width:135px;color:#4a5568">{ts}</span>'
    '<span style="min-width:110px;text-align:center">'
    '<span style="background:{badge_bg};color:{badge_fg};'
    'padding:2px 8px;border-radius:8px;font-size:0.72rem;font-weight:700">'
    '{decision}</span></span>'
    '<span style="min-width:170px;color:#2d3748;font-weight:600">{agent}</span>'
    '<span style="color:#cbd5e0">→</span>'
    '<span style="min-width:190px;color:#2b6cb0">{tool}</span>'
    '<span style="flex:1;color:#718096;font-size:0.75rem">{uc_label}</span>'
    '<span style="min-width:80px;text-align:right;color:#a0aec0;font-size:0.75rem">{extras}</span>'
    '</div>'
)

html_rows     = []
flagged_rows  = []

for _, row in log_df.iterrows():
    decision = row["decision"]
    badge_bg, badge_fg, row_bg = DECISION_BG.get(
        decision, ("#e2e8f0", "#2d3748", "#f7fafc")
    )

    parts = []
    if row.get("redactions", 0) > 0:
        parts.append(
            f'<span style="background:#bee3f8;color:#2a4365;'
            f'padding:1px 5px;border-radius:5px;font-size:0.7rem">'
            f'✂️{int(row["redactions"])}</span>'
        )
    if row.get("tokens_used", 0) > 0:
        parts.append(f'{int(row["tokens_used"]):,}tok')
    parts.append(f'{int(row["latency_ms"])}ms')
    extras = " · ".join(parts)

    uc_label = USE_CASE_LABELS.get(row.get("use_case", ""), row.get("use_case", ""))

    html_rows.append(LOG_ROW.format(
        row_bg=row_bg,
        ts=row["timestamp"].strftime("%b %d  %H:%M:%S"),
        badge_bg=badge_bg, badge_fg=badge_fg,
        decision=decision.upper().replace("-", "‑"),
        agent=row.get("agent_id", ""),
        tool=row.get("tool", ""),
        uc_label=uc_label,
        extras=extras,
    ))

    if decision != "allow":
        flagged_rows.append(row)

st.markdown("".join(html_rows), unsafe_allow_html=True)

# ── Policy explanations ───────────────────────────────────────────────────────
if flagged_rows:
    st.divider()
    st.markdown("### Policy explanations")
    st.caption(
        "Every denied or fallback event — which policy fired, "
        "which rule triggered, and what would change the outcome."
    )
    for row in flagged_rows:
        reason      = str(row.get("reason", ""))
        explanation = REASON_EXPLANATION.get(reason)
        icon        = DECISION_ICONS.get(row["decision"], "•")
        label = (
            f"{icon} **{row['decision'].upper()}** · "
            f"{row['agent_id']} → `{row['tool']}` · "
            f"{row['timestamp'].strftime('%b %d  %H:%M:%S')}"
        )
        with st.expander(label):
            if explanation:
                st.markdown(explanation)
            if reason:
                st.caption(f"Raw reason: `{reason}`")
            # Show full raw event JSON
            with st.expander("Raw log entry"):
                st.json(row.dropna().to_dict())

st.divider()
st.caption(
    "Built on [agentgateway](https://agentgateway.dev) · "
    "Open source · Linux Foundation / AAIF"
)
