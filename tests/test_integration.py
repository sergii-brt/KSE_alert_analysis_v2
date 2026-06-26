"""
Integration tests for the full application.

Module: test_integration.py
"""

import pytest

from src.alert_analyzer import AlertAnalyzer
from src.data_loader import DataLoader


class TestIntegration:
    """Integration tests."""

    def test_data_loader_to_analyzer(self, cache_config, sample_alerts_response) -> None:
        """Test data loader to analyzer pipeline."""
        # Load data
        loader = DataLoader(cache_config=cache_config)
        loader._save_cache(sample_alerts_response)

        # Load from cache
        cached = loader._load_valid_cache()
        assert cached is not None

        # Analyze
        analyzer = AlertAnalyzer(cached)
        stats = analyzer.get_summary_statistics()

        assert stats["total_alerts"] == 3
        assert stats["regions"] == 3

        loader.close()

    def test_full_pipeline(self, cache_config, sample_alerts_response) -> None:
        """Test full application pipeline."""
        loader = DataLoader(cache_config=cache_config)
        loader._save_cache(sample_alerts_response)

        data = loader._load_valid_cache()
        assert data is not None

        analyzer = AlertAnalyzer(data)

        # Test all analyzer methods
        summary = analyzer.get_summary_statistics()
        assert summary is not None

        by_region = analyzer.get_alerts_by_region()
        assert not by_region.empty

        by_date = analyzer.get_alerts_by_date()
        assert not by_date.empty

        regions = analyzer.df["region"].unique()
        for region in regions:
            timeline = analyzer.get_region_timeline(region)
            assert not timeline.empty

        hourly = analyzer.get_hourly_distribution()
        assert not hourly.empty

        top = analyzer.get_top_affected_regions()
        assert len(top) > 0

        loader.close()
