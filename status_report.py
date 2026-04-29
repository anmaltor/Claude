#!/usr/bin/env python3
"""Send periodic status reports with condensation risk indicators.

Usage:
    python3 status_report.py config.json
"""

import sys
import json
import smtplib
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from condensation import fetch_station_observation, predict, estimate_tile_floor_temp


def get_risk_indicator(margin_c: float) -> str:
    """Return indicator based on condensation risk margin."""
    if margin_c > 5.0:
        return "GREEN - SAFE"
    elif margin_c > 1.0:
        return "YELLOW - CAUTION"
    else:
        return "RED - RISK"


def format_station_report(station_code: str, config: dict) -> str:
    """Fetch and format weather report for a station."""
    try:
        obs = fetch_station_observation(station_code)
        temp_c = obs["temp_c"]
        rh = obs["relative_humidity_pct"]
        dp = obs["dew_point_c"]
        
        # Estimate tile surface if slab temp provided
        surface_temp = temp_c
        if config.get("slab_temp_c"):
            surface_temp = estimate_tile_floor_temp(temp_c, config["slab_temp_c"])
        
        # Predict condensation
        forecast = predict(temp_c, rh, surface_temp)
        
        # Risk indicator
        risk = get_risk_indicator(forecast.margin_c)
        
        report = f"""
{station_code} ({obs.get('observation_time', 'N/A')})
{'-' * 50}
Temperature:      {temp_c:6.1f}C
Dew Point:        {dp:6.1f}C
Humidity:         {rh:6.1f}%
Margin:           {forecast.margin_c:+6.1f}C

Surface Temp:     {surface_temp:6.1f}C
Condensation:     {forecast.form.upper()}
Risk Level:       {risk}
"""
        return report
    except Exception as e:
        return f"{station_code}: Error - {e}\n"


def send_status_report(config_path: str) -> None:
    """Load config, fetch weather, and send status report."""
    # Load config
    with open(config_path) as f:
        config = json.load(f)
    
    # Build report
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = f"CONDENSATION STATUS REPORT\n{timestamp}\n{'=' * 50}\n"
    
    for station in config.get("stations", []):
        code = station.get("code")
        if code:
            report += format_station_report(code, config)
    
    report += f"\n{'=' * 50}\n"
    report += "Threshold: " + str(config.get("threshold_margin_c", 0.0)) + "C\n"
    if config.get("slab_temp_c"):
        report += "Slab Temp: " + str(config.get("slab_temp_c")) + "C\n"
    
    # Send email if configured
    email_config = config.get("notifier_config", {}).get("email", {})
    if email_config:
        smtp_host = email_config.get("smtp_host")
        smtp_port = email_config.get("smtp_port", 587)
        smtp_user = email_config.get("smtp_user")
        smtp_pass = email_config.get("smtp_password")
        from_addr = email_config.get("from_address", smtp_user)
        to_addrs = email_config.get("to_addresses", [])
        
        if smtp_host and from_addr and to_addrs:
            try:
                msg = MIMEMultipart()
                msg["From"] = from_addr
                msg["To"] = ", ".join(to_addrs)
                msg["Subject"] = f"Condensation Status Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                msg.attach(MIMEText(report, "plain"))
                
                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                    server.sendmail(from_addr, to_addrs, msg.as_string())
                
                print("[OK] Status report sent via email")
            except Exception as e:
                print(f"[ERROR] Failed to send email: {e}")
    
    # Also print to console
    print(report)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 status_report.py <config.json>")
        sys.exit(1)
    
    config_path = sys.argv[1]
    if not Path(config_path).exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    
    send_status_report(config_path)
