"""
Unit tests for data_loader module.

Module: test_data_loader.py
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from src.data_loader import (
    APIConfig,
    CacheConfig,
    DataLoader,
    SchemaValidator,
    load_alerts_data,
)


class TestCacheConfig:
    """Tests for CacheConfig dataclass."""

    def test_valid_config(self, temp_cache_dir: Path) -> None:
        """Test valid configuration."""
        config = CacheConfig(directory=temp_cache_dir, expiry_hours=24)
        assert config.expiry_hours == 24
        assert config.directory.exists()

    def test_invalid_expiry_hours(self, temp_cache_dir: Path) -> None:
        """Test invalid expiry_hours."""
        with pytest.raises(ValueError):
            CacheConfig(directory=temp_cache_dir, expiry_hours=0)

    def test_directory_resolution(self) -> None:
        """Test relative path resolution."""
        config = CacheConfig(directory=Path("./cache"), expiry_hours=24)
        assert config.directory.is_absolute()


class TestAPIConfig:
    """Tests for APIConfig dataclass."""

    def test_valid_config(self) -> None:
        """Test valid configuration."""
        config = APIConfig(url="https://sirens.in.ua/api/v3/alerts/")
        assert config.timeout == 10
        assert config.max_retries == 3

    def test_invalid_timeout(self) -> None:
        """Test invalid timeout."""
        with pytest.raises(ValueError):
            APIConfig(url="https://test.com", timeout=0)

    def test_invalid_max_retries(self) -> None:
        """Test invalid max_retries."""
        with pytest.raises(ValueError):
            APIConfig(url="https://test.com", max_retries=-1)


class TestSchemaValidator:
    """Tests for SchemaValidator."""

    def test_valid_alert_record(self) -> None:
        """Test valid alert record validation."""
        record = {"id": 1, "region": "Kyiv", "start": 1700000000, "end": 1700001800}
        assert SchemaValidator.validate_alert_record(record) is True

    def test_missing_required_field(self) -> None:
        """Test missing required field."""
        record = {"id": 1, "region": "Kyiv"}  # Missing 'start'
        assert SchemaValidator.validate_alert_record(record) is False

    def test_invalid_type(self) -> None:
        """Test invalid field type."""
        record = {"id": "not-int", "region": "Kyiv", "start": 1700000000}
        assert SchemaValidator.validate_alert_record(record) is False

    def test_valid_response(self, sample_alerts_response) -> None:
        """Test valid response validation."""
        assert SchemaValidator.validate_response(sample_alerts_response) is True

    def test_empty_response(self, empty_alerts_response) -> None:
        """Test empty response validation."""
        assert SchemaValidator.validate_response(empty_alerts_response) is True


class TestDataLoader:
    """Tests for DataLoader class."""

    def test_initialization(self, cache_config: CacheConfig) -> None:
        """Test DataLoader initialization."""
        loader = DataLoader(cache_config=cache_config)
        assert loader.cache_config == cache_config
        loader.close()

    def test_cache_age_format(self, cache_config: CacheConfig) -> None:
        """Test cache age formatting."""
        loader = DataLoader(cache_config=cache_config)
        age = loader._get_cache_age()
        assert age == "N/A"  # Cache doesn't exist yet
        loader.close()

    def test_save_and_load_cache(
        self, cache_config: CacheConfig, sample_alerts_response
    ) -> None:
        """Test saving and loading cache."""
        loader = DataLoader(cache_config=cache_config)

        # Save
        loader._save_cache(sample_alerts_response)
        assert cache_config.cache_file.exists()

        # Load
        loaded = loader._read_and_validate_cache(cache_config.cache_file)
        assert loaded is not None
        assert len(loaded["alerts"]) == 3

        loader.close()

    def test_context_manager(self, cache_config: CacheConfig) -> None:
        """Test context manager usage."""
        with DataLoader(cache_config=cache_config) as loader:
            assert loader is not None

    @patch("src.data_loader.requests.Session.get")
    def test_api_fetch_success(
        self, mock_get, cache_config: CacheConfig, sample_alerts_response
    ) -> None:
        """Test successful API fetch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_alerts_response
        mock_get.return_value = mock_response

        loader = DataLoader(cache_config=cache_config)
        result = loader._fetch_from_api()

        assert result is not None
        assert len(result["alerts"]) == 3
        loader.close()

    @patch("src.data_loader.requests.Session.get")
    def test_api_fetch_timeout(self, mock_get, cache_config: CacheConfig) -> None:
        """Test API fetch timeout."""
        mock_get.side_effect = requests.Timeout("Timeout")

        loader = DataLoader(cache_config=cache_config)
        result = loader._fetch_from_api()

        assert result is None
        loader.close()

    @patch("src.data_loader.requests.Session.get")
    def test_api_fetch_http_error(self, mock_get, cache_config: CacheConfig) -> None:
        """Test API fetch HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.HTTPError("Server error")
        mock_get.return_value = mock_response

        loader = DataLoader(cache_config=cache_config)
        result = loader._fetch_from_api()

        assert result is None
        loader.close()


def test_load_alerts_data() -> None:
    """Test convenience function."""
    # This will use actual API or cache
    # For testing, we'd mock it
    assert callable(load_alerts_data)
