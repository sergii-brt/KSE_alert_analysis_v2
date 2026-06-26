"""
Production-grade data loader for Ukrainian air raid alerts.

Handles API calls and caching with graceful degradation, schema validation,
and comprehensive error handling. Implements exponential backoff retry logic
and atomic cache operations for robustness.

Module: data_loader.py
Version: 2.0
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Optional, TypedDict

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# ============================================================================
# TYPE DEFINITIONS
# ============================================================================


class AlertRecord(TypedDict, total=False):
    """Schema for individual alert record."""

    id: int
    region: str
    start: int  # Unix timestamp
    end: Optional[int]  # Unix timestamp or null if ongoing
    type: str


class AlertsResponse(TypedDict, total=False):
    """Schema for API response."""

    alerts: list[AlertRecord]
    timestamp: str


# ============================================================================
# CONFIGURATION WITH VALIDATION
# ============================================================================


@dataclass(frozen=True)
class CacheConfig:
    """Immutable cache configuration with validation."""

    directory: Path
    expiry_hours: int
    filename: str = "alerts.json"

    def __post_init__(self) -> None:
        """Validate configuration parameters."""
        if self.expiry_hours <= 0:
            raise ValueError(f"expiry_hours must be > 0, got {self.expiry_hours}")

        if not isinstance(self.directory, Path):
            object.__setattr__(self, "directory", Path(self.directory))

        # Ensure directory path is absolute
        if not self.directory.is_absolute():
            object.__setattr__(self, "directory", self.directory.resolve())

    @property
    def cache_file(self) -> Path:
        """Get full path to cache file."""
        return self.directory / self.filename


@dataclass(frozen=True)
class APIConfig:
    """Immutable API configuration with validation."""

    url: str
    timeout: int = 10
    max_retries: int = 3
    backoff_factor: float = 1.0

    def __post_init__(self) -> None:
        """Validate API configuration."""
        if not self.url.startswith("https://"):
            logger.warning(
                "API URL does not use HTTPS: %s. "
                "This is not recommended for production.",
                self.url,
            )

        if self.timeout <= 0:
            raise ValueError(f"timeout must be > 0, got {self.timeout}")

        if self.max_retries < 0:
            raise ValueError(f"max_retries must be >= 0, got {self.max_retries}")

        if self.backoff_factor <= 0:
            raise ValueError(
                f"backoff_factor must be > 0, got {self.backoff_factor}"
            )


# ============================================================================
# CONSTANTS
# ============================================================================

DEFAULT_CACHE_CONFIG = CacheConfig(
    directory=Path("cache"),
    expiry_hours=24,
)

DEFAULT_API_CONFIG = APIConfig(
    url="https://sirens.in.ua/api/v3/alerts/",
    timeout=10,
    max_retries=3,
    backoff_factor=1.0,
)

# HTTP status codes to retry on
RETRYABLE_STATUS_CODES = [429, 500, 502, 503, 504]

# ============================================================================
# SCHEMA VALIDATORS
# ============================================================================


class SchemaValidator:
    """Validates alert data against expected schema."""

    @staticmethod
    def validate_alert_record(record: dict) -> bool:
        """
        Validate a single alert record.

        Args:
            record: Alert record to validate

        Returns:
            True if valid, False otherwise
        """
        if not isinstance(record, dict):
            logger.warning("Alert record is not a dict: %s", type(record))
            return False

        # Required fields
        required_fields = {"id", "region", "start"}
        if not required_fields.issubset(record.keys()):
            missing = required_fields - record.keys()
            logger.warning("Alert record missing required fields: %s", missing)
            return False

        # Type validation
        if not isinstance(record.get("id"), int):
            logger.warning("Alert id is not int: %s", type(record.get("id")))
            return False

        if not isinstance(record.get("region"), str):
            logger.warning("Alert region is not str: %s", type(record.get("region")))
            return False

        if not isinstance(record.get("start"), int):
            logger.warning("Alert start is not int: %s", type(record.get("start")))
            return False

        # End can be int or null
        end = record.get("end")
        if end is not None and not isinstance(end, int):
            logger.warning("Alert end is neither int nor null: %s", type(end))
            return False

        return True

    @staticmethod
    def validate_response(data: dict) -> bool:
        """
        Validate complete API response structure.

        Args:
            data: Response data to validate

        Returns:
            True if valid, False otherwise
        """
        if not isinstance(data, dict):
            logger.error("Response is not a dict: %s", type(data))
            return False

        if "alerts" not in data:
            logger.error("Response missing 'alerts' key. Keys: %s", list(data.keys()))
            return False

        if not isinstance(data["alerts"], list):
            logger.error(
                "Response 'alerts' is not a list: %s", type(data["alerts"])
            )
            return False

        if len(data["alerts"]) == 0:
            logger.info("Response contains empty alerts list")
            return True

        # Validate each alert record
        invalid_records = [
            i
            for i, record in enumerate(data["alerts"])
            if not SchemaValidator.validate_alert_record(record)
        ]

        if invalid_records:
            logger.warning(
                "Response contains %d invalid records at indices: %s",
                len(invalid_records),
                invalid_records[:10],  # Show first 10
            )
            # Filter out invalid records
            data["alerts"] = [
                record
                for i, record in enumerate(data["alerts"])
                if i not in invalid_records
            ]

        return True


# ============================================================================
# MAIN DATA LOADER CLASS
# ============================================================================


class DataLoader:
    """
    Production-grade data loader for Ukrainian air raid alerts.

    Implements three-tier fallback strategy:
    1. Valid (non-expired) cache
    2. Fresh API fetch with retry logic
    3. Stale cache as last resort

    Features:
    - Exponential backoff retry with configurable parameters
    - Atomic cache writes to prevent corruption
    - Comprehensive schema validation
    - Thread-safe operations (via atomic file operations)
    - Detailed logging for debugging
    """

    def __init__(
        self,
        api_config: APIConfig = DEFAULT_API_CONFIG,
        cache_config: CacheConfig = DEFAULT_CACHE_CONFIG,
    ) -> None:
        """
        Initialize DataLoader with configuration.

        Args:
            api_config: API configuration (validated)
            cache_config: Cache configuration (validated)

        Raises:
            ValueError: If configuration is invalid
        """
        self.api_config = api_config
        self.cache_config = cache_config
        self._session: Optional[requests.Session] = None

        logger.info(
            "DataLoader initialized with API URL: %s, "
            "cache expiry: %d hours",
            self.api_config.url,
            self.cache_config.expiry_hours,
        )

    @property
    def session(self) -> requests.Session:
        """
        Lazy-load session with retry logic.

        Returns:
            Configured requests.Session with exponential backoff
        """
        if self._session is None:
            self._session = self._create_session()
        return self._session

    def load_alerts(self) -> Optional[AlertsResponse]:
        """
        Load alerts with three-tier fallback strategy.

        Returns valid cache -> fresh API data -> stale cache -> None

        Returns:
            AlertsResponse if successful, None otherwise
        """
        logger.info("Starting alert data load sequence")

        # Tier 1: Valid cache
        if cached := self._load_valid_cache():
            cache_age = self._get_cache_age()
            logger.info("Using valid cache (age: %s)", cache_age)
            return cached

        # Tier 2: Fresh API
        if fresh := self._fetch_from_api():
            self._save_cache(fresh)
            logger.info("Successfully loaded fresh data from API")
            return fresh

        # Tier 3: Stale cache
        if stale := self._load_any_cache():
            logger.warning(
                "Using stale cache as fallback. "
                "API unreachable and no valid cache available."
            )
            return stale

        # Tier 4: Complete failure
        logger.error(
            "No data available. Checked: valid cache, API, stale cache. "
            "All sources exhausted."
        )
        return None

    def _load_valid_cache(self) -> Optional[AlertsResponse]:
        """
        Load cache if it exists and is not expired.

        Returns:
            AlertsResponse if valid cache exists, None otherwise
        """
        cache_file = self.cache_config.cache_file

        if not cache_file.exists():
            logger.debug("Cache file does not exist: %s", cache_file)
            return None

        try:
            # Check expiry
            stat = cache_file.stat()
            file_age = datetime.now() - datetime.fromtimestamp(stat.st_mtime)
            age_hours = file_age.total_seconds() / 3600

            if age_hours > self.cache_config.expiry_hours:
                logger.info(
                    "Cache expired (age: %.1f hours, expiry: %d hours)",
                    age_hours,
                    self.cache_config.expiry_hours,
                )
                return None

            logger.debug("Cache is valid (age: %.1f hours)", age_hours)
            return self._read_and_validate_cache(cache_file)

        except OSError as e:
            logger.exception("Error checking cache validity: %s", e)
            return None

    def _load_any_cache(self) -> Optional[AlertsResponse]:
        """
        Load cache regardless of expiry (stale cache fallback).

        Returns:
            AlertsResponse from cache file, None if cache missing/invalid
        """
        cache_file = self.cache_config.cache_file

        if not cache_file.exists():
            logger.debug("No cache file found for stale fallback: %s", cache_file)
            return None

        try:
            cache_age = self._get_cache_age()
            logger.info("Attempting to load stale cache (age: %s)", cache_age)
            return self._read_and_validate_cache(cache_file)

        except OSError as e:
            logger.exception("Error loading stale cache: %s", e)
            return None

    def _read_and_validate_cache(
        self, cache_file: Path
    ) -> Optional[AlertsResponse]:
        """
        Read cache file and validate schema.

        Args:
            cache_file: Path to cache file

        Returns:
            AlertsResponse if valid, None if invalid
        """
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                logger.error("Cache content is not a dict: %s", type(data))
                return None

            if not SchemaValidator.validate_response(data):
                logger.warning("Cache failed schema validation")
                return None

            logger.debug(
                "Cache loaded and validated: %d alerts",
                len(data.get("alerts", [])),
            )
            return data

        except json.JSONDecodeError as e:
            logger.exception("Cache contains invalid JSON: %s", e)
            return None
        except (OSError, IOError) as e:
            logger.exception("Error reading cache file: %s", e)
            return None

    def _fetch_from_api(self) -> Optional[AlertsResponse]:
        """
        Fetch alerts from API with retry logic.

        Uses exponential backoff for retries on transient failures.

        Returns:
            AlertsResponse if successful, None on persistent failure
        """
        try:
            logger.info("Attempting to fetch from API: %s", self.api_config.url)
            response = self.session.get(
                self.api_config.url, timeout=self.api_config.timeout
            )

            logger.info("API response status: %d", response.status_code)

            # Check for successful response
            response.raise_for_status()

            # Parse and validate
            data = response.json()

            if not SchemaValidator.validate_response(data):
                logger.warning("API response failed schema validation")
                return None

            logger.info(
                "API fetch successful: %d alerts", len(data.get("alerts", []))
            )
            return data

        except requests.Timeout as e:
            logger.exception(
                "API request timed out after %d seconds", self.api_config.timeout
            )
            return None

        except requests.ConnectionError as e:
            logger.exception("Failed to connect to API: %s", e)
            return None

        except requests.HTTPError as e:
            logger.exception("API returned HTTP error: %s", e)
            return None

        except json.JSONDecodeError as e:
            logger.exception("API response is not valid JSON: %s", e)
            return None

        except requests.RequestException as e:
            logger.exception("Unexpected request error: %s", e)
            return None

    def _save_cache(self, data: AlertsResponse) -> None:
        """
        Save data to cache using atomic write operation.

        Writes to temporary file first, then renames atomically
        to prevent corruption if process is interrupted.

        Args:
            data: AlertsResponse to cache
        """
        cache_file = self.cache_config.cache_file
        temp_file = cache_file.with_suffix(".tmp")

        try:
            # Ensure cache directory exists
            cache_file.parent.mkdir(parents=True, exist_ok=True)

            # Write to temporary file
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            # Atomic rename
            temp_file.replace(cache_file)

            logger.info("Cache saved successfully: %s", cache_file)

        except OSError as e:
            logger.exception("Failed to save cache: %s", e)
            # Clean up temporary file if it exists
            try:
                temp_file.unlink(missing_ok=True)
            except OSError:
                pass

    def _get_cache_age(self) -> str:
        """
        Get human-readable cache age.

        Returns:
            Formatted string like "2h 30m" or "N/A" if cache missing
        """
        cache_file = self.cache_config.cache_file

        try:
            if not cache_file.exists():
                return "N/A"

            file_age = datetime.now() - datetime.fromtimestamp(
                cache_file.stat().st_mtime
            )

            hours = int(file_age.total_seconds() // 3600)
            minutes = int((file_age.total_seconds() % 3600) // 60)

            if hours == 0:
                return f"{minutes}m"
            elif minutes == 0:
                return f"{hours}h"
            else:
                return f"{hours}h {minutes}m"

        except OSError:
            return "N/A"

    @staticmethod
    def _create_session() -> requests.Session:
        """
        Create requests.Session with exponential backoff retry logic.

        Retry strategy:
        - Retries on 429 (rate limit), 5xx server errors
        - Exponential backoff: 1s, 2s, 4s, etc.
        - Only retries GET requests (safe to replay)

        Returns:
            Configured requests.Session
        """
        session = requests.Session()

        retry_strategy = Retry(
            total=3,
            status_forcelist=RETRYABLE_STATUS_CODES,
            allowed_methods=["GET"],
            backoff_factor=1.0,  # 1s, 2s, 4s delays
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        logger.debug("Created session with retry strategy: %s", retry_strategy)
        return session

    def close(self) -> None:
        """
        Close the requests session to free resources.

        Should be called when DataLoader is no longer needed.
        """
        if self._session is not None:
            self._session.close()
            logger.info("Session closed")

    def __enter__(self) -> "DataLoader":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


# ============================================================================
# CONVENIENCE FUNCTIONS (Backward compatible API)
# ============================================================================


@lru_cache(maxsize=1)
def _get_default_loader() -> DataLoader:
    """
    Get singleton default DataLoader instance.

    Returns:
        Default DataLoader with standard configuration
    """
    return DataLoader()


def load_alerts_data() -> Optional[AlertsResponse]:
    """
    Load alerts data using default configuration.

    Convenience function that uses a cached singleton DataLoader.

    Returns:
        AlertsResponse if successful, None otherwise

    Example:
        >>> data = load_alerts_data()
        >>> if data:
        ...     print(f"Loaded {len(data['alerts'])} alerts")
        ... else:
        ...     print("Failed to load alerts")
    """
    loader = _get_default_loader()
    return loader.load_alerts()


def load_alerts_data_with_config(
    api_url: str = DEFAULT_API_CONFIG.url,
    cache_expiry_hours: int = DEFAULT_CACHE_CONFIG.expiry_hours,
    api_timeout: int = DEFAULT_API_CONFIG.timeout,
) -> Optional[AlertsResponse]:
    """
    Load alerts with custom configuration.

    Args:
        api_url: API endpoint URL
        cache_expiry_hours: Cache validity period in hours
        api_timeout: API request timeout in seconds

    Returns:
        AlertsResponse if successful, None otherwise

    Example:
        >>> data = load_alerts_data_with_config(
        ...     api_url="https://custom.api/alerts/",
        ...     cache_expiry_hours=12,
        ...     api_timeout=15
        ... )
    """
    api_config = APIConfig(
        url=api_url,
        timeout=api_timeout,
    )
    cache_config = CacheConfig(
        directory=DEFAULT_CACHE_CONFIG.directory,
        expiry_hours=cache_expiry_hours,
    )

    with DataLoader(api_config, cache_config) as loader:
        return loader.load_alerts()


# ============================================================================
# TESTING/DEBUG UTILITIES
# ============================================================================


def get_cache_stats() -> dict:
    """
    Get cache statistics for debugging.

    Returns:
        Dict with cache file info (exists, age, size)
    """
    cache_file = DEFAULT_CACHE_CONFIG.cache_file

    if not cache_file.exists():
        return {"exists": False, "path": str(cache_file)}

    try:
        stat = cache_file.stat()
        age = datetime.now() - datetime.fromtimestamp(stat.st_mtime)

        return {
            "exists": True,
            "path": str(cache_file),
            "size_bytes": stat.st_size,
            "age_hours": age.total_seconds() / 3600,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }
    except OSError as e:
        logger.exception("Error getting cache stats: %s", e)
        return {"exists": True, "path": str(cache_file), "error": str(e)}


# ============================================================================
# TESTING EXAMPLE
# ============================================================================

if __name__ == "__main__":
    # Example usage
    logger.info("=" * 70)
    logger.info("Ukrainian Air Raid Alerts - Data Loader Demo")
    logger.info("=" * 70)

    # Get cache stats
    stats = get_cache_stats()
    logger.info("Cache stats: %s", stats)

    # Load data
    logger.info("\nAttempting to load alerts...")
    data = load_alerts_data()

    if data:
        logger.info("SUCCESS: Loaded %d alerts", len(data.get("alerts", [])))
        logger.info(
            "Sample alert: %s", data["alerts"][0] if data["alerts"] else "No alerts"
        )
    else:
        logger.error("FAILED: Unable to load alerts from any source")

    logger.info("=" * 70)
