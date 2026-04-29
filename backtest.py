#!/usr/bin/env python3
"""Backtest condensation predictions against historical weather events."""

import sys
import json
import urllib.request
from pathlib import Path
from datetime import datetime
from condensation import predict, estimate_tile_floor_temp


def fetch_historical_weather(lat: float, lon: float, date_str: str) -> list:
    """Fetch historical hourly weather from Open-Meteo API (free, no key needed).
    
    Args:
        lat, lon: Toronto coordinates (43.6629, -79.3957)
        date_str: Date in format YYYY-MM-DD
    
    Returns:
        List of hourly observations
    """
    # Toronto coordinates
    url = f"https://archive-api.open-meteo.com/v1/archive?latitude=43.6629&longitude=-79.3957&start_date={date_str}&end_date={date_str}&hourly=temperature_2m,relative_humidity_2m,dew_point_2m&timezone=America/Toronto"
    
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        return data
    except Exception as e:
        print(f"  Error fetching weather for {date_str}: {e}")
        return {}


def backtest_events(config_path: str) -> None:
    """Backtest against ECLRT condensation events."""
    with open(config_path) as f:
        config = json.load(f)
    
    slab_temp = config.get("slab_temp_c")
    threshold = config.get("threshold_margin_c", 0.0)
    
    print("\n" + "=" * 90)
    print("CONDENSATION BACKTEST: Historical Weather vs ECLRT Events")
    print("=" * 90)
    
    events = [
        ("2026-04-14", "12:48 - 17:26", "Mount Dennis, Keelesdale, Eglinton - Active condensation"),
        ("2026-04-15", "All day", "Widespread condensation, persistent at Mount Dennis"),
        ("2026-04-16", "05:07, 06:03", "Kennedy (damp); Don Valley/Science Centre (severe)"),
    ]
    
    for event_date, event_time, description in events:
        print(f"\n{'-' * 90}")
        print(f"Date: {event_date} | Time: {event_time}")
        print(f"ECLRT Report: {description}")
        print(f"{'-' * 90}")
        
        weather = fetch_historical_weather(43.6629, -79.3957, event_date)
        
        if not weather or "hourly" not in weather:
            print("  [NO DATA] Could not fetch historical weather")
            continue
        
        hourly = weather["hourly"]
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        rhs = hourly.get("relative_humidity_2m", [])
        dews = hourly.get("dew_point_2m", [])
        
        print(f"\n  Hourly weather and condensation risk:\n")
        print(f"  {'Hour (EST)':<12} {'Temp':<8} {'RH':<8} {'DP':<8} {'Surface':<8} {'Margin':<8} {'Status':<20}")
        print(f"  {'-' * 90}")
        
        alert_count = 0
        for i, time_str in enumerate(times):
            if i >= len(temps):
                break
                
            temp = temps[i]
            rh = rhs[i]
            dp = dews[i]
            
            # Estimate surface temp
            surface = temp
            if slab_temp is not None:
                surface = estimate_tile_floor_temp(temp, slab_temp)
            
            # Predict
            forecast = predict(temp, rh, surface)
            
            # Extract hour from timestamp
            hour = time_str.split("T")[1][:5] if "T" in time_str else "?"
            
            # Alert status
            status = "ALERT - " + forecast.form.upper() if forecast.will_condense else "OK"
            if forecast.will_condense:
                alert_count += 1
                status = ">>> " + status + " <<<"
            
            print(f"  {hour}         {temp:6.1f}C  {rh:6.1f}%  {dp:6.1f}C  {surface:6.1f}C  {forecast.margin_c:+6.1f}C  {status}")
        
        print(f"\n  Summary: {alert_count} hours with condensation risk detected")
        if alert_count > 0:
            print(f"  >>> SYSTEM WOULD HAVE ALERTED <<<")
        else:
            print(f"  [!] No condensation risk detected by model")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 backtest.py <config.json>")
        sys.exit(1)
    
    config_path = sys.argv[1]
    if not Path(config_path).exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    
    backtest_events(config_path)
