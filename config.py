#!/usr/bin/env python3
"""Configuration management for condensation monitoring automation.

Supports loading from JSON files and environment variables.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


class Config:
    """Manages monitoring configuration."""

    # Default configuration
    DEFAULTS = {
        "polling_interval_seconds": 300,  # 5 minutes
        "threshold_margin_c": 0.0,  # Alert at/below dew point
        "slab_temp_c": None,  # If set, estimate tile surface temp
        "stations": [],
        "seasonal_thresholds": {
            "january": 0.0,
            "february": 0.0,
            "march": 0.0,
            "april": 0.0,
            "may": 0.5,
            "june": 1.0,
            "july": 1.0,
            "august": 1.0,
            "september": 0.5,
            "october": 0.0,
            "november": 0.0,
            "december": 0.0,
        },
        "notifier_config": {
            "console": True,
            "email": {},
            "webhooks": [],
        },
    }

    @staticmethod
    def load_from_file(path: str) -> dict:
        """Load configuration from JSON file.

        Args:
            path: Path to JSON config file

        Returns:
            Configuration dict merged with defaults

        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If JSON is malformed
        """
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(config_path) as f:
            user_config = json.load(f)

        return Config.merge_with_defaults(user_config)

    @staticmethod
    def load_from_env() -> dict:
        """Load configuration from environment variables.

        Environment variables:
        - CONDENSATION_CONFIG: Path to JSON config file
        - CONDENSATION_STATIONS: Comma-separated station codes
        - CONDENSATION_INTERVAL: Polling interval in seconds
        - CONDENSATION_THRESHOLD: Margin threshold in Celsius
        - CONDENSATION_SLAB_TEMP: Slab temperature in Celsius

        Returns:
            Configuration dict merged with defaults
        """
        config = Config.DEFAULTS.copy()

        # Load from config file if specified
        config_file = os.getenv("CONDENSATION_CONFIG")
        if config_file:
            config.update(Config.load_from_file(config_file))

        # Override with environment variables
        if interval := os.getenv("CONDENSATION_INTERVAL"):
            config["polling_interval_seconds"] = int(interval)

        if threshold := os.getenv("CONDENSATION_THRESHOLD"):
            config["threshold_margin_c"] = float(threshold)

        if slab_temp := os.getenv("CONDENSATION_SLAB_TEMP"):
            config["slab_temp_c"] = float(slab_temp)

        if stations := os.getenv("CONDENSATION_STATIONS"):
            station_codes = [s.strip().upper() for s in stations.split(",")]
            config["stations"] = [
                {"code": code} for code in station_codes
            ]

        return config

    @staticmethod
    def merge_with_defaults(user_config: dict) -> dict:
        """Merge user config with defaults, deep-merging nested dicts.

        Args:
            user_config: User-provided configuration

        Returns:
            Merged configuration with defaults for missing keys
        """
        config = Config.DEFAULTS.copy()

        for key, value in user_config.items():
            if isinstance(value, dict) and key in config:
                if isinstance(config[key], dict):
                    # Deep merge for nested dicts
                    merged = config[key].copy()
                    merged.update(value)
                    config[key] = merged
                else:
                    config[key] = value
            else:
                config[key] = value

        return config

    @staticmethod
    def get_threshold_for_month(config: dict, month: int = None) -> float:
        """Get alert threshold for current (or specified) month.

        Args:
            config: Configuration dict
            month: Month number (1-12). If None, uses current month.

        Returns:
            Alert threshold in degrees Celsius
        """
        import datetime

        if month is None:
            month = datetime.datetime.now().month

        month_names = [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december"
        ]

        if 1 <= month <= 12:
            month_name = month_names[month - 1]
            seasonal = config.get("seasonal_thresholds", {})
            if month_name in seasonal:
                return seasonal[month_name]

        # Fallback to default threshold
        return config.get("threshold_margin_c", 0.0)

    @staticmethod
    def validate(config: dict) -> tuple[bool, list[str]]:
        """Validate configuration for required fields and types.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check stations
        if not isinstance(config.get("stations"), list):
            errors.append("'stations' must be a list")
        elif not config["stations"]:
            errors.append("'stations' list is empty")
        else:
            for i, station in enumerate(config["stations"]):
                if not isinstance(station, dict):
                    errors.append(f"Station {i} must be a dict")
                elif "code" not in station:
                    errors.append(f"Station {i} missing 'code' field")

        # Check polling interval
        interval = config.get("polling_interval_seconds")
        if not isinstance(interval, (int, float)) or interval <= 0:
            errors.append("'polling_interval_seconds' must be > 0")

        # Check threshold
        threshold = config.get("threshold_margin_c")
        if not isinstance(threshold, (int, float)):
            errors.append("'threshold_margin_c' must be numeric")

        # Check slab temp (optional)
        if config.get("slab_temp_c") is not None:
            slab_temp = config["slab_temp_c"]
            if not isinstance(slab_temp, (int, float)):
                errors.append("'slab_temp_c' must be numeric")

        # Check notifier config
        notifier_cfg = config.get("notifier_config", {})
        if not isinstance(notifier_cfg, dict):
            errors.append("'notifier_config' must be a dict")

        return len(errors) == 0, errors

    @staticmethod
    def create_example() -> str:
        """Generate example configuration JSON.

        Returns:
            JSON string for example config
        """
        example = {
            "polling_interval_seconds": 300,
            "threshold_margin_c": 0.0,
            "slab_temp_c": None,
            "stations": [
                {"code": "CYYZ"},  # Toronto Pearson
                {"code": "KJFK"},  # New York JFK
            ],
            "notifier_config": {
                "console": True,
                "email": {
                    "smtp_host": "smtp.gmail.com",
                    "smtp_port": 587,
                    "smtp_user": "your-email@gmail.com",
                    "smtp_password": "your-app-password",
                    "from_address": "your-email@gmail.com",
                    "to_addresses": ["alert@example.com"],
                },
                "webhooks": [
                    "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
                ],
            },
        }
        return json.dumps(example, indent=2)


def main():
    """CLI for config management."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: config.py <command> [args]")
        print("\nCommands:")
        print("  example              Print example configuration")
        print("  validate <file>      Validate configuration file")
        print("  from-env             Load and print config from env vars")
        sys.exit(1)

    command = sys.argv[1]

    if command == "example":
        print(Config.create_example())

    elif command == "validate":
        if len(sys.argv) < 3:
            print("Usage: config.py validate <file>")
            sys.exit(1)
        try:
            config = Config.load_from_file(sys.argv[2])
            is_valid, errors = Config.validate(config)
            if is_valid:
                print("✓ Configuration is valid")
                print(f"  Stations: {', '.join(s['code'] for s in config['stations'])}")
                print(
                    f"  Polling interval: {config['polling_interval_seconds']}s"
                )
                print(
                    f"  Threshold margin: {config['threshold_margin_c']}°C"
                )
            else:
                print("✗ Configuration errors:")
                for error in errors:
                    print(f"  - {error}")
                sys.exit(1)
        except Exception as e:
            print(f"✗ Failed to load config: {e}")
            sys.exit(1)

    elif command == "from-env":
        config = Config.load_from_env()
        print(json.dumps(config, indent=2))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
