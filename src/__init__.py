"""
Ukrainian Air Raid Alerts Analysis Application.

Production-grade Streamlit application for time-series analysis of Ukrainian
air raid alerts sourced from sirens.in.ua API with robust data handling,
schema validation, and comprehensive error recovery.

Version: 2.0.0
Python: 3.11+
"""

__version__ = "2.0.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from src.alert_analyzer import AlertAnalyzer
from src.data_loader import (
    APIConfig,
    CacheConfig,
    DataLoader,
    load_alerts_data,
    load_alerts_data_with_config,
)
from src.ui_components import UIComponents

__all__ = [
    "DataLoader",
    "AlertAnalyzer",
    "UIComponents",
    "APIConfig",
    "CacheConfig",
    "load_alerts_data",
    "load_alerts_data_with_config",
]
