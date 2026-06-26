# 🇺🇦 Ukrainian Air Raid Alerts Analysis

[![Tests](https://github.com/sergii-brt/KSE_alert_analysis/workflows/tests/badge.svg)](https://github.com/sergii-brt/KSE_alert_analysis/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://kse-alert-analysis.streamlit.app)

A production-grade Streamlit application for real-time analysis and visualization of Ukrainian air raid alerts from [sirens.in.ua](https://sirens.in.ua/).

## Features

✨ **Core Capabilities:**
- 📊 Real-time alert data visualization
- 📍 Regional breakdown and analysis
- 📈 Temporal trend analysis
- 🕐 Hourly distribution patterns
- 💾 Intelligent caching with fallback strategies
- 🔄 Automatic retry logic with exponential backoff
- 📥 Export data as CSV or JSON

🛡️ **Production Quality:**
- Complete type hints and schema validation
- Comprehensive error handling and logging
- Atomic file operations for data safety
- Three-tier fallback data loading strategy
- Thread-safe operations
- Full test coverage with pytest

## Installation

### Prerequisites
- Python 3.11+
- pip or poetry

### Quick Start

1. **Clone the repository:**
```bash
git clone https://github.com/sergii-brt/KSE_alert_analysis.git
cd KSE_alert_analysis
