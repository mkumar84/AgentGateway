"""
Entry point — defines navigation and routes to page files.
Run:  streamlit run report.py
"""

import streamlit as st

st.set_page_config(
    page_title="Agentic AI Governance Gateway",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

pg = st.navigation(
    {
        "": [
            st.Page("pages/0_Overview.py",              title="Overview",             icon="🛡️", default=True),
        ],
        "Analysis": [
            st.Page("pages/1_Governance_Scorecard.py",  title="Governance Scorecard", icon="📊"),
            st.Page("pages/2_Agent_Monitor.py",         title="Agent Monitor",        icon="🤖"),
            st.Page("pages/3_Decision_Log.py",          title="Decision Log",         icon="📜"),
        ],
    }
)

pg.run()
