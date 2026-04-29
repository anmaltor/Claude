#!/usr/bin/env python3
"""Event-driven weather monitoring for condensation prediction.

Polls METAR weather stations at regular intervals, predicts condensation risk,
and sends notifications when conditions are met.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from condensation import (
    fetch_station_observation,
    estimate_tile_floor_temp,
    predict,
)
from notifier import Notifier


@dataclass
class MonitorAlert:
    """Tracks alert state to avoid duplicate notifications."""

    station: str
    form: str  # "dew", "frost", "fog"
    last_alert_time: datetime
    cooldown_seconds: int = 3600  # Alert cooldown period


class StationMonitor:
    """Monitors a single weather station for condensation risk."""

    def __init__(
        self,
        station_code: str,
        threshold_margin_c: float = 0.0,
        slab_temp_c: Optional[float] = None,
        notifier: Optional[Notifier] = None,
    ):
        """Initialize monitor for a station.

        Args:
            station_code: ICAO station code (e.g., "CYYZ")
            threshold_margin_c: Alert if margin <= this value (default: 0 = at/below dew point)
            slab_temp_c: Slab temperature for tile surface estimation; if None, uses air temp
            notifier: Notifier instance for alerts; if None, uses console
        """
        self.station_code = station_code
        self.threshold_margin_c = threshold_margin_c
        self.slab_temp_c = slab_temp_c
        self.notifier = notifier or Notifier()
        self.last_observation: Optional[dict] = None
        self.alert_history: dict[str, MonitorAlert] = {}

    def should_alert(self, form: str, last_alert: Optional[MonitorAlert]) -> bool:
        """Determine if an alert should be sent for this condensation form.

        Returns False if:
        - Same form was recently alerted (within cooldown)
        - No previous observation to compare against
        """
        if last_alert is None:
            return True  # First time seeing this condition

        elapsed = datetime.now() - last_alert.last_alert_time
        return elapsed.total_seconds() >= last_alert.cooldown_seconds

    def poll(self) -> Optional[dict]:
        """Fetch current observations and predict condensation.

        Returns:
            Alert dict if condensation triggered, None otherwise.
        """
        try:
            obs = fetch_station_observation(self.station_code)
        except RuntimeError as e:
            print(f"[{self.station_code}] Failed to fetch: {e}")
            return None

        self.last_observation = obs
        air_temp = obs["temp_c"]
        air_rh = obs["relative_humidity_pct"]

        # Estimate surface temperature
        if self.slab_temp_c is not None:
            surface_temp = estimate_tile_floor_temp(
                air_temp, self.slab_temp_c
            )
        else:
            surface_temp = air_temp

        # Predict condensation
        forecast = predict(air_temp, air_rh, surface_temp)

        # Check if alert is needed
        if forecast.margin_c <= self.threshold_margin_c:
            last_alert = self.alert_history.get(forecast.form)
            if self.should_alert(forecast.form, last_alert):
                # Record alert and send notification
                self.alert_history[forecast.form] = MonitorAlert(
                    station=self.station_code,
                    form=forecast.form,
                    last_alert_time=datetime.now(),
                )
                return {
                    "station": self.station_code,
                    "observation_time": obs.get("observation_time"),
                    "air_temp_c": air_temp,
                    "relative_humidity_pct": air_rh,
                    "surface_temp_c": surface_temp,
                    "forecast": {
                        "dew_point_c": forecast.dew_point_c,
                        "margin_c": forecast.margin_c,
                        "form": forecast.form,
                    },
                }
        return None

    def notify(self, alert: dict) -> None:
        """Send alert notification via configured notifier."""
        self.notifier.notify_condensation(alert)


class MonitoringService:
    """Orchestrates monitoring across multiple stations."""

    def __init__(self, config: dict):
        """Initialize service with configuration.

        Args:
            config: Configuration dict with keys:
                - stations: list of {"code": "CYYZ", ...} dicts
                - threshold_margin_c: Alert threshold (default: 0.0)
                - slab_temp_c: Optional slab temperature for surface estimation
                - notifier_config: Notifier configuration
        """
        self.config = config
        self.stations = {}
        self.notifier = Notifier(config.get("notifier_config", {}))

        # Initialize station monitors
        for station_cfg in config.get("stations", []):
            code = station_cfg["code"]
            monitor = StationMonitor(
                station_code=code,
                threshold_margin_c=config.get("threshold_margin_c", 0.0),
                slab_temp_c=config.get("slab_temp_c"),
                notifier=self.notifier,
            )
            self.stations[code] = monitor

    def poll_all(self) -> list[dict]:
        """Poll all stations and return triggered alerts.

        Returns:
            List of alert dicts for conditions that triggered alerts.
        """
        alerts = []
        for station_code, monitor in self.stations.items():
            alert = monitor.poll()
            if alert:
                alerts.append(alert)
                monitor.notify(alert)
        return alerts

    def run_loop(
        self,
        interval_seconds: int = 300,
        max_iterations: Optional[int] = None,
        verbose: bool = False,
    ) -> None:
        """Run continuous monitoring loop.

        Args:
            interval_seconds: Time between polls (default: 300 = 5 min)
            max_iterations: Stop after N iterations; None = infinite
            verbose: Print debug info during execution
        """
        iteration = 0
        try:
            while max_iterations is None or iteration < max_iterations:
                if verbose:
                    print(
                        f"\n[{datetime.now().isoformat()}] "
                        f"Polling {len(self.stations)} station(s)..."
                    )

                alerts = self.poll_all()
                if alerts and verbose:
                    print(f"  -> {len(alerts)} alert(s) triggered")

                iteration += 1
                if max_iterations is None or iteration < max_iterations:
                    time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")


def run_monitor(config_path: str, verbose: bool = False) -> None:
    """Load configuration and run monitoring service.

    Args:
        config_path: Path to JSON configuration file
        verbose: Enable verbose logging
    """
    with open(config_path) as f:
        config = json.load(f)

    service = MonitoringService(config)
    service.run_loop(
        interval_seconds=config.get("polling_interval_seconds", 300),
        verbose=verbose,
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <config.json> [--verbose]")
        sys.exit(1)

    config_file = sys.argv[1]
    verbose = "--verbose" in sys.argv
    run_monitor(config_file, verbose=verbose)
