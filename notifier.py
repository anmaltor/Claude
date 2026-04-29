#!/usr/bin/env python3
"""Notification backends for condensation alerts.

Supports multiple notification methods:
- Console logging (always available)
- Email (via SMTP)
- Webhooks (for Slack, Discord, custom integrations)
"""

from __future__ import annotations

import json
import smtplib
import urllib.error
import urllib.request
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional


class Notifier:
    """Dispatch condensation alerts through configured channels."""

    def __init__(self, config: Optional[dict] = None):
        """Initialize notifier with configuration.

        Args:
            config: Dict with keys:
                - console: bool - enable console logging (default: True)
                - email: dict with smtp config (optional)
                - webhooks: list of webhook URLs (optional)
        """
        self.config = config or {}
        self.console_enabled = self.config.get("console", True)
        self.email_config = self.config.get("email", {})
        self.webhooks = self.config.get("webhooks", [])

    def notify_condensation(self, alert: dict) -> None:
        """Send condensation alert through all configured channels.

        Args:
            alert: Alert dict from StationMonitor.poll()
        """
        if self.console_enabled:
            self._notify_console(alert)
        if self.email_config:
            self._notify_email(alert)
        if self.webhooks:
            self._notify_webhooks(alert)

    def _notify_console(self, alert: dict) -> None:
        """Log alert to console."""
        station = alert["station"]
        form = alert["forecast"]["form"]
        margin = alert["forecast"]["margin_c"]
        obs_time = alert.get("observation_time", "unknown")

        print(
            f"\n[{datetime.now().isoformat()}] "
            f"CONDENSATION ALERT: {station} @ {obs_time}"
        )
        print(
            f"  Type: {form.upper()} "
            f"(margin: {margin:+.1f}°C, at/below dew point)"
        )
        print(f"  Air: {alert['air_temp_c']:.1f}°C @ {alert['relative_humidity_pct']:.0f}% RH")
        print(f"  Surface: {alert['surface_temp_c']:.1f}°C")
        print(f"  Dew Point: {alert['forecast']['dew_point_c']:.1f}°C")

    def _notify_email(self, alert: dict) -> None:
        """Send alert via SMTP email."""
        config = self.email_config
        smtp_host = config.get("smtp_host")
        smtp_port = config.get("smtp_port", 587)
        smtp_user = config.get("smtp_user")
        smtp_pass = config.get("smtp_password")
        from_addr = config.get("from_address")
        to_addrs = config.get("to_addresses", [])

        if not (smtp_host and from_addr and to_addrs):
            print(
                "[notifier] Email config incomplete, skipping email notification"
            )
            return

        try:
            subject = self._format_email_subject(alert)
            body = self._format_email_body(alert)

            msg = MIMEMultipart()
            msg["From"] = from_addr
            msg["To"] = ", ".join(to_addrs)
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)

            if self.console_enabled:
                print(f"[notifier] Email sent to {', '.join(to_addrs)}")
        except Exception as e:
            print(f"[notifier] Email send failed: {e}")

    def _notify_webhooks(self, alert: dict) -> None:
        """Send alert via webhooks (Slack, Discord, etc.)."""
        payload = self._format_webhook_payload(alert)

        for webhook_url in self.webhooks:
            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    webhook_url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp.read()
                if self.console_enabled:
                    print(f"[notifier] Webhook POST succeeded: {webhook_url}")
            except (urllib.error.URLError, TimeoutError) as e:
                print(f"[notifier] Webhook POST failed ({webhook_url}): {e}")

    def _format_email_subject(self, alert: dict) -> str:
        """Format email subject line."""
        station = alert["station"]
        form = alert["forecast"]["form"].upper()
        return f"Condensation Alert: {form} at {station}"

    def _format_email_body(self, alert: dict) -> str:
        """Format email message body."""
        station = alert["station"]
        form = alert["forecast"]["form"]
        margin = alert["forecast"]["margin_c"]
        obs_time = alert.get("observation_time", "unknown")
        air_temp = alert["air_temp_c"]
        rh = alert["relative_humidity_pct"]
        surface_temp = alert["surface_temp_c"]
        dew_point = alert["forecast"]["dew_point_c"]

        return (
            f"Condensation Alert: {form.upper()}\n"
            f"\n"
            f"Station: {station}\n"
            f"Observation Time: {obs_time}\n"
            f"\n"
            f"Current Conditions:\n"
            f"  Air Temperature: {air_temp:.1f}°C\n"
            f"  Relative Humidity: {rh:.0f}%\n"
            f"  Surface Temperature: {surface_temp:.1f}°C\n"
            f"  Dew Point: {dew_point:.1f}°C\n"
            f"  Margin: {margin:+.1f}°C (at/below dew point = condensation)\n"
            f"\n"
            f"Alert Type: {form}\n"
            f"  • dew: condensation on surfaces above freezing\n"
            f"  • frost: condensation on surfaces at/below freezing\n"
            f"  • fog: condensation in the air (saturated conditions)\n"
        )

    def _format_webhook_payload(self, alert: dict) -> dict:
        """Format webhook payload (supports Slack and generic JSON)."""
        station = alert["station"]
        form = alert["forecast"]["form"]
        margin = alert["forecast"]["margin_c"]

        # Generic JSON payload that works with most webhook systems
        return {
            "alert_type": "condensation",
            "station": station,
            "form": form,
            "margin_c": margin,
            "timestamp": alert.get("observation_time", datetime.now().isoformat()),
            "conditions": {
                "air_temp_c": alert["air_temp_c"],
                "relative_humidity_pct": alert["relative_humidity_pct"],
                "surface_temp_c": alert["surface_temp_c"],
                "dew_point_c": alert["forecast"]["dew_point_c"],
            },
        }


def notify_test(config_path: str) -> None:
    """Test notifier configuration with a mock alert.

    Args:
        config_path: Path to JSON configuration file
    """
    with open(config_path) as f:
        config = json.load(f)

    notifier = Notifier(config.get("notifier_config", {}))

    # Mock alert for testing
    mock_alert = {
        "station": "CYYZ",
        "observation_time": datetime.now().isoformat(),
        "air_temp_c": 15.0,
        "relative_humidity_pct": 85.0,
        "surface_temp_c": 10.0,
        "forecast": {
            "dew_point_c": 12.5,
            "margin_c": -2.5,
            "form": "dew",
        },
    }

    print("Sending test condensation alert...\n")
    notifier.notify_condensation(mock_alert)
    print("\nTest complete")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <config.json>")
        sys.exit(1)

    notify_test(sys.argv[1])
