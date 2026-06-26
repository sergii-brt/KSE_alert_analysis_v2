"""
Main Streamlit application for Ukrainian Air Raid Alerts Analysis.

Production-grade web application for time-series analysis of air raid alerts
sourced from sirens.in.ua API with robust error handling and graceful
degradation.

Usage:
    streamlit run streamlit_app.py
"""

import logging
import sys
from pathlib import Path

import streamlit as st

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.alert_analyzer import AlertAnalyzer
from src.data_loader import get_cache_stats, load_alerts_data
from src.ui_components import UIComponents

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="🇺🇦 Air Raid Alerts Analysis",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# SIDEBAR SETUP
# ============================================================================


def setup_sidebar() -> None:
    """Configure sidebar with info and controls."""
    with st.sidebar:
        st.markdown("# 🔧 Controls")

        if st.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()

        st.markdown("---")

        # Cache stats
        cache_stats = get_cache_stats()
        UIComponents.display_cache_info(cache_stats)

        st.markdown("---")

        # About section
        st.markdown("## ℹ️ About")
        st.markdown(
            """
This application provides real-time analysis of Ukrainian air raid alerts 
from [sirens.in.ua](https://sirens.in.ua/).

**Data Source:** sirens.in.ua API v3

**Features:**
- Real-time alert tracking
- Regional analysis
- Temporal patterns
- Duration statistics

**Update Frequency:** Cache refreshes every 24 hours

**Version:** 2.0.0

---

**⚠️ Note:** This is a demonstration application for educational purposes.
        """
        )


# ============================================================================
# MAIN APPLICATION
# ============================================================================


def main() -> None:
    """Main application flow."""
    # Header
    st.markdown(
        """
    # 🚨 Ukrainian Air Raid Alerts Analysis
    
    Real-time analysis and visualization of air raid alert patterns 
    from [sirens.in.ua](https://sirens.in.ua/)
    """
    )

    # Load data
    logger.info("Loading alerts data...")

    with st.spinner("Loading data from API..."):
        data = load_alerts_data()

    # Error handling
    if data is None:
        UIComponents.display_error(
            "Unable to load alerts data. "
            "The API is unreachable and no cached data is available. "
            "Please try again later."
        )

    if not data.get("alerts"):
        UIComponents.display_warning(
            "No alerts available. The server is connected but returned an empty list."
        )
        st.stop()

    # Success
    alerts_count = len(data.get("alerts", []))
    UIComponents.display_success(f"Loaded {alerts_count} alerts")

    # Initialize analyzer
    try:
        analyzer = AlertAnalyzer(data)
    except Exception as e:
        logger.exception("Error initializing analyzer: %s", e)
        UIComponents.display_error(
            f"Error processing data: {str(e)}"
        )

    # Display summary metrics
    st.markdown("---")
    st.subheader("📊 Summary Metrics")
    UIComponents.display_summary_metrics(analyzer)

    st.markdown("---")

    # Create tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📍 Regional Analysis", "📈 Timeline", "🕐 Hourly Pattern", "🔍 Region Details"]
    )

    with tab1:
        UIComponents.display_regional_breakdown(analyzer)

    with tab2:
        UIComponents.display_timeline(analyzer)

    with tab3:
        UIComponents.display_hourly_distribution(analyzer)

    with tab4:
        st.subheader("Region Details Explorer")
        regions = sorted(analyzer.df["region"].unique())

        if regions:
            selected_region = st.selectbox(
                "Select a region to analyze:",
                regions,
                index=0,
            )
            UIComponents.display_region_details(analyzer, selected_region)
        else:
            st.warning("No regions available for analysis")

    st.markdown("---")

    # Data export section
    st.subheader("📥 Export Data")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Download as CSV"):
            csv = analyzer.df.to_csv(index=False)
            st.download_button(
                label="Click to download",
                data=csv,
                file_name="alerts.csv",
                mime="text/csv",
            )

    with col2:
        if st.button("Download as JSON"):
            import json

            json_data = json.dumps(data, indent=2, default=str)
            st.download_button(
                label="Click to download",
                data=json_data,
                file_name="alerts.json",
                mime="application/json",
            )

    st.markdown("---")

    # Footer
    st.markdown(
        """
    <div style="text-align: center; color: gray; font-size: 12px;">
    <p>Data updated: Last fetch from sirens.in.ua API</p>
    <p>© 2024 Ukrainian Air Raid Alerts Analysis | 
    <a href="https://github.com/sergii-brt/KSE_alert_analysis">GitHub</a></p>
    </div>
    """,
        unsafe_allow_html=True,
    )


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    setup_sidebar()
    main()
