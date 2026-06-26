"""
Unit tests for alert_analyzer module.

Module: test_alert_analyzer.py
"""

import pandas as pd
import pytest

from src.alert_analyzer import AlertAnalyzer


class TestAlertAnalyzer:
    """Tests for AlertAnalyzer class."""

    def test_initialization(self, sample_alerts_response) -> None:
        """Test analyzer initialization."""
        analyzer = AlertAnalyzer(sample_alerts_response)
        assert not analyzer.df.empty
        assert len(analyzer.df) == 3

    def test_summary_statistics(self, sample_alerts_response) -> None:
        """Test summary statistics."""
        analyzer = AlertAnalyzer(sample_alerts_response)
        stats = analyzer.get_summary_statistics()

        assert stats["total_alerts"] == 3
        assert stats["regions"] == 3
        assert stats["ongoing_alerts"] == 1

    def test_alerts_by_region(self, sample_alerts_response) -> None:
        """Test regional breakdown."""
        analyzer = AlertAnalyzer(sample_alerts_response)
        by_region = analyzer.get_alerts_by_region()

        assert len(by_region) == 3
        assert "Kyiv" in by_region["region"].values

    def test_alerts_by_date(self, sample_alerts_response) -> None:
        """Test date grouping."""
        analyzer = AlertAnalyzer(sample_alerts_response)
        by_date = analyzer.get_alerts_by_date()

        assert not by_date.empty
        assert "date" in by_date.columns

    def test_region_timeline(self, sample_alerts_response) -> None:
        """Test region timeline."""
        analyzer = AlertAnalyzer(sample_alerts_response)
        timeline = analyzer.get_region_timeline("Kyiv")

        assert len(timeline) == 1
        assert timeline.iloc[0]["region"] == "Kyiv"

    def test_hourly_distribution(self, sample_alerts_response) -> None:
        """Test hourly distribution."""
        analyzer = AlertAnalyzer(sample_alerts_response)
        hourly = analyzer.get_hourly_distribution()

        assert not hourly.empty
        assert "hour" in hourly.columns

    def test_duration_statistics(self, sample_alerts_response) -> None:
        """Test duration statistics."""
        analyzer = AlertAnalyzer(sample_alerts_response)
        stats = analyzer.get_duration_statistics()

        assert "min_minutes" in stats
        assert "max_minutes" in stats
        assert "mean_minutes" in stats

    def test_top_affected_regions(self, sample_alerts_response) -> None:
        """Test top regions."""
        analyzer = AlertAnalyzer(sample_alerts_response)
        top = analyzer.get_top_affected_regions(top_n=2)

        assert len(top) <= 2
        assert "region" in top[0]
        assert "total_alerts" in top[0]

    def test_recent_alerts(self, sample_alerts_response) -> None:
        """Test recent alerts (note: sample data is old)."""
        analyzer = AlertAnalyzer(sample_alerts_response)
        recent = analyzer.get_recent_alerts(hours=24)

        # Sample data is from 2023, so no recent alerts
        assert recent.empty

    def test_empty_data(self, empty_alerts_response) -> None:
        """Test analyzer with empty data."""
        analyzer = AlertAnalyzer(empty_alerts_response)
        assert analyzer.df.empty
        stats = analyzer.get_summary_statistics()
        assert stats["total_alerts"] == 0
