"""
Pytest configuration and shared fixtures.

Module: conftest.py
"""

import json
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from src.data_loader import CacheConfig, AlertsResponse


@pytest.fixture
def temp_cache_dir() -> Generator[Path, None, None]:
    """
    Create temporary cache directory for testing.

    Yields:
        Path to temporary directory
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def cache_config(temp_cache_dir: Path) -> CacheConfig:
    """
    Create cache config with temporary directory.

    Args:
        temp_cache_dir: Temporary cache directory

    Returns:
        CacheConfig instance
    """
    return CacheConfig(
        directory=temp_cache_dir,
        expiry_hours=24,
    )


@pytest.fixture
def sample_alerts_response() -> AlertsResponse:
    """
    Create sample alerts response for testing.

    Returns:
        Sample AlertsResponse
    """
    return {
        "alerts": [
            {
                "id": 1,
                "region": "Kyiv",
                "start": 1700000000,
                "end": 1700001800,
                "type": "AIR_RAID",
            },
            {
                "id": 2,
                "region": "Kharkiv",
                "start": 1700001000,
                "end": None,
                "type": "AIR_RAID",
            },
            {
                "id": 3,
                "region": "Lviv",
                "start": 1700002000,
                "end": 1700002600,
                "type": "AIR_RAID",
            },
        ]
    }


@pytest.fixture
def empty_alerts_response() -> AlertsResponse:
    """
    Create empty alerts response for testing.

    Returns:
        Empty AlertsResponse
    """
    return {"alerts": []}
