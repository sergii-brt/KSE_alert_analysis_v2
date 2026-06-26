"""
Alert analysis module for time-series analysis of Ukrainian air raid alerts.

Provides statistical analysis, trend detection, regional breakdowns,
and duration calculations.

Module: alert_analyzer.py
Version: 2.0
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from src.data_loader import AlertRecord, AlertsResponse

logger = logging.getLogger(__name__)


class AlertAnalyzer:
    """Analyzes alert data for patterns, trends, and statistics."""

    def __init__(self, data: AlertsResponse) -> None:
        """
        Initialize analyzer with alert data.

        Args:
            data: AlertsResponse from data loader
        """
        self.raw_data = data
        self.alerts = data.get("alerts", [])
        self.df = self._convert_to_dataframe()

    def _convert_to_dataframe(self) -> pd.DataFrame:
        """
        Convert alert records to pandas DataFrame.

        Returns:
            DataFrame with parsed timestamps and durations
        """
        if not self.alerts:
            logger.warning("No alerts to convert to DataFrame")
            return pd.DataFrame()

        try:
            df = pd.DataFrame(self.alerts)

            # Convert timestamps
            df["start_time"] = pd.to_datetime(df["start"], unit="s")
            df["end_time"] = pd.to_datetime(df["end"], unit="s", errors="coerce")

            # Calculate duration in minutes
            df["duration_minutes"] = (
                (df["end_time"] - df["start_time"]).dt.total_seconds() / 60
            )

            # Extract date for grouping
            df["date"] = df["start_time"].dt.date

            logger.info("Converted %d alerts to DataFrame", len(df))
            return df

        except Exception as e:
            logger.exception("Error converting alerts to DataFrame: %s", e)
            return pd.DataFrame()

    def get_summary_statistics(self) -> dict:
        """
        Get overall summary statistics.

        Returns:
            Dictionary with total alerts, date range, and other metrics
        """
        if self.df.empty:
            logger.warning("Cannot generate summary: DataFrame is empty")
            return {
                "total_alerts": 0,
                "date_range": "No data",
                "regions": 0,
                "avg_duration_minutes": 0,
            }

        try:
            return {
                "total_alerts": len(self.df),
                "date_range": f"{self.df['start_time'].min().date()} to {self.df['start_time'].max().date()}",
                "regions": self.df["region"].nunique(),
                "avg_duration_minutes": self.df["duration_minutes"].mean(),
                "max_duration_minutes": self.df["duration_minutes"].max(),
                "ongoing_alerts": self.df["end_time"].isna().sum(),
            }
        except Exception as e:
            logger.exception("Error calculating summary statistics: %s", e)
            return {}

    def get_alerts_by_region(self) -> pd.DataFrame:
        """
        Get alert counts grouped by region.

        Returns:
            DataFrame with region and alert count
        """
        if self.df.empty:
            return pd.DataFrame({"region": [], "count": []})

        try:
            region_stats = (
                self.df.groupby("region")
                .size()
                .reset_index(name="count")
                .sort_values("count", ascending=False)
            )

            logger.info("Regional breakdown: %d regions", len(region_stats))
            return region_stats

        except Exception as e:
            logger.exception("Error grouping by region: %s", e)
            return pd.DataFrame()

    def get_alerts_by_date(self) -> pd.DataFrame:
        """
        Get alert counts grouped by date.

        Returns:
            DataFrame with date and alert count
        """
        if self.df.empty:
            return pd.DataFrame({"date": [], "count": []})

        try:
            date_stats = (
                self.df.groupby("date").size().reset_index(name="count").sort_values("date")
            )

            logger.info("Timeline: %d unique dates", len(date_stats))
            return date_stats

        except Exception as e:
            logger.exception("Error grouping by date: %s", e)
            return pd.DataFrame()

    def get_region_timeline(self, region: str) -> pd.DataFrame:
        """
        Get alerts for a specific region over time.

        Args:
            region: Region name to filter

        Returns:
            DataFrame with timeline for specified region
        """
        if self.df.empty:
            return pd.DataFrame()

        try:
            region_df = self.df[self.df["region"] == region].sort_values("start_time")

            logger.info("Retrieved timeline for region: %s (%d alerts)", 
                       region, len(region_df))
            return region_df

        except Exception as e:
            logger.exception("Error retrieving region timeline: %s", e)
            return pd.DataFrame()

    def get_hourly_distribution(self) -> pd.DataFrame:
        """
        Get alert distribution by hour of day.

        Returns:
            DataFrame with hour and alert count
        """
        if self.df.empty:
            return pd.DataFrame()

        try:
            hourly = (
                self.df.assign(hour=self.df["start_time"].dt.hour)
                .groupby("hour")
                .size()
                .reset_index(name="count")
            )

            logger.info("Hourly distribution calculated")
            return hourly

        except Exception as e:
            logger.exception("Error calculating hourly distribution: %s", e)
            return pd.DataFrame()

    def get_duration_statistics(self, region: Optional[str] = None) -> dict:
        """
        Get duration statistics (min, max, median, std).

        Args:
            region: Optional region filter

        Returns:
            Dictionary with duration statistics
        """
        if self.df.empty:
            return {}

        try:
            data = self.df[self.df["region"] == region] if region else self.df
            durations = data["duration_minutes"].dropna()

            if len(durations) == 0:
                logger.warning("No duration data available")
                return {}

            return {
                "min_minutes": durations.min(),
                "max_minutes": durations.max(),
                "median_minutes": durations.median(),
                "mean_minutes": durations.mean(),
                "std_minutes": durations.std(),
                "count": len(durations),
            }

        except Exception as e:
            logger.exception("Error calculating duration statistics: %s", e)
            return {}

    def get_top_affected_regions(self, top_n: int = 10) -> list[dict]:
        """
        Get top N most affected regions.

        Args:
            top_n: Number of top regions to return

        Returns:
            List of dicts with region name and alert count
        """
        if self.df.empty:
            return []

        try:
            top_regions = (
                self.df.groupby("region")
                .agg(
                    {
                        "id": "count",
                        "duration_minutes": ["mean", "max"],
                    }
                )
                .round(2)
                .reset_index()
                .sort_values(("id", "count"), ascending=False)
                .head(top_n)
            )

            result = []
            for _, row in top_regions.iterrows():
                result.append(
                    {
                        "region": row["region"],
                        "total_alerts": int(row[("id", "count")]),
                        "avg_duration": float(row[("duration_minutes", "mean")]),
                        "max_duration": float(row[("duration_minutes", "max")]),
                    }
                )

            logger.info("Retrieved top %d regions", len(result))
            return result

        except Exception as e:
            logger.exception("Error getting top affected regions: %s", e)
            return []

    def get_recent_alerts(self, hours: int = 24) -> pd.DataFrame:
        """
        Get alerts from the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            DataFrame with recent alerts
        """
        if self.df.empty:
            return pd.DataFrame()

        try:
            cutoff = datetime.now() - timedelta(hours=hours)
            recent = self.df[self.df["start_time"] >= cutoff].sort_values(
                "start_time", ascending=False
            )

            logger.info("Retrieved %d alerts from last %d hours", len(recent), hours)
            return recent

        except Exception as e:
            logger.exception("Error retrieving recent alerts: %s", e)
            return pd.DataFrame()
