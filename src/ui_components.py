"""
Streamlit UI components for alert visualization and interaction.

Provides reusable components for displaying alerts, charts, and metrics.

Module: ui_components.py
Version: 2.0
"""

import logging
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from src.alert_analyzer import AlertAnalyzer

logger = logging.getLogger(__name__)


class UIComponents:
    """Reusable Streamlit UI components."""

    @staticmethod
    def display_error(message: str) -> None:
        """
        Display error message and stop execution.

        Args:
            message: Error message to display
        """
        st.error(f"❌ {message}")
        st.stop()

    @staticmethod
    def display_warning(message: str) -> None:
        """
        Display warning message.

        Args:
            message: Warning message to display
        """
        st.warning(f"⚠️ {message}")

    @staticmethod
    def display_success(message: str) -> None:
        """
        Display success message.

        Args:
            message: Success message to display
        """
        st.success(f"✅ {message}")

    @staticmethod
    def display_info(message: str) -> None:
        """
        Display info message.

        Args:
            message: Info message to display
        """
        st.info(f"ℹ️ {message}")

    @staticmethod
    def display_summary_metrics(analyzer: AlertAnalyzer) -> None:
        """
        Display summary metrics in columns.

        Args:
            analyzer: AlertAnalyzer instance
        """
        stats = analyzer.get_summary_statistics()

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Alerts", stats.get("total_alerts", 0))

        with col2:
            st.metric("Regions Affected", stats.get("regions", 0))

        with col3:
            avg_duration = stats.get("avg_duration_minutes", 0)
            st.metric("Avg Duration (min)", f"{avg_duration:.1f}")

        with col4:
            ongoing = stats.get("ongoing_alerts", 0)
            st.metric("Ongoing Alerts", ongoing)

    @staticmethod
    def display_regional_breakdown(analyzer: AlertAnalyzer) -> None:
        """
        Display alerts by region.

        Args:
            analyzer: AlertAnalyzer instance
        """
        st.subheader("📍 Regional Breakdown")

        top_regions = analyzer.get_top_affected_regions(top_n=15)

        if not top_regions:
            st.warning("No regional data available")
            return

        # Convert to DataFrame for display
        df_regions = pd.DataFrame(top_regions)

        # Create columns for layout
        col1, col2 = st.columns(2)

        with col1:
            st.dataframe(
                df_regions,
                use_container_width=True,
                hide_index=True,
            )

        with col2:
            # Bar chart
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.barh(
                df_regions["region"].head(10),
                df_regions["total_alerts"].head(10),
                color="steelblue",
            )
            ax.set_xlabel("Number of Alerts")
            ax.set_title("Top 10 Most Affected Regions")
            ax.invert_yaxis()
            st.pyplot(fig)

    @staticmethod
    def display_timeline(analyzer: AlertAnalyzer) -> None:
        """
        Display alerts over time.

        Args:
            analyzer: AlertAnalyzer instance
        """
        st.subheader("📈 Alerts Over Time")

        date_stats = analyzer.get_alerts_by_date()

        if date_stats.empty:
            st.warning("No timeline data available")
            return

        # Line chart
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(date_stats["date"], date_stats["count"], marker="o", linewidth=2)
        ax.set_xlabel("Date")
        ax.set_ylabel("Number of Alerts")
        ax.set_title("Alert Frequency Over Time")
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        st.pyplot(fig)

        # Statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Peak Day", date_stats.loc[date_stats["count"].idxmax(), "date"])
        with col2:
            st.metric("Avg Alerts/Day", f"{date_stats['count'].mean():.1f}")
        with col3:
            st.metric("Total Days", len(date_stats))

    @staticmethod
    def display_hourly_distribution(analyzer: AlertAnalyzer) -> None:
        """
        Display alerts by hour of day.

        Args:
            analyzer: AlertAnalyzer instance
        """
        st.subheader("🕐 Hourly Distribution")

        hourly = analyzer.get_hourly_distribution()

        if hourly.empty:
            st.warning("No hourly data available")
            return

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.bar(hourly["hour"], hourly["count"], color="coral", width=0.8)
        ax.set_xlabel("Hour of Day (UTC)")
        ax.set_ylabel("Number of Alerts")
        ax.set_title("Alert Distribution by Hour")
        ax.set_xticks(range(0, 24))
        ax.grid(True, alpha=0.3, axis="y")
        st.pyplot(fig)

    @staticmethod
    def display_region_details(analyzer: AlertAnalyzer, region: str) -> None:
        """
        Display detailed information for a region.

        Args:
            analyzer: AlertAnalyzer instance
            region: Region name
        """
        st.subheader(f"🔍 Details: {region}")

        timeline = analyzer.get_region_timeline(region)

        if timeline.empty:
            st.warning(f"No data for region: {region}")
            return

        # Duration statistics
        stats = analyzer.get_duration_statistics(region)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Alerts", len(timeline))
        with col2:
            st.metric("Avg Duration (min)", f"{stats.get('mean_minutes', 0):.1f}")
        with col3:
            st.metric("Max Duration (min)", f"{stats.get('max_minutes', 0):.1f}")
        with col4:
            st.metric("Median Duration (min)", f"{stats.get('median_minutes', 0):.1f}")

        # Timeline for this region
        st.write("**Recent Alerts:**")
        display_timeline_df = timeline[
            ["start_time", "end_time", "duration_minutes", "type"]
        ].tail(20)
        st.dataframe(display_timeline_df, use_container_width=True, hide_index=True)

    @staticmethod
    def display_cache_info(cache_stats: dict) -> None:
        """
        Display cache information in sidebar.

        Args:
            cache_stats: Cache statistics dictionary
        """
        with st.sidebar:
            st.markdown("---")
            st.subheader("📦 Cache Status")

            if cache_stats.get("exists"):
                age_hours = cache_stats.get("age_hours", 0)
                if age_hours < 1:
                    age_str = f"{int(age_hours * 60)}m"
                else:
                    age_str = f"{age_hours:.1f}h"

                st.metric("Cache Age", age_str)
                st.metric("Size (KB)", f"{cache_stats.get('size_bytes', 0) / 1024:.1f}")
                st.text(f"Modified: {cache_stats.get('modified', 'N/A')[:10]}")
            else:
                st.warning("Cache not found")
