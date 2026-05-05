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


def parse_timestamp(ts: str) -> tuple:
    """Parse DD/MM/YYYY HH:MM:SS to (YYYY-MM-DD, hour)."""
    dt = datetime.strptime(ts, "%d/%m/%Y %H:%M:%S")
    return dt.strftime("%Y-%m-%d"), dt.hour


def backtest_events(config_path: str) -> None:
    """Backtest against ECLRT condensation events."""
    with open(config_path) as f:
        config = json.load(f)

    slab_temp = config.get("slab_temp_c")

    # Observed condensation events
    observed_events = [
        "18/04/2026 17:09:00",
        "18/04/2026 16:43:00",
        "18/04/2026 16:55:00",
        "18/04/2026 16:45:00",
        "16/04/2026 12:15:00",
        "16/04/2026 12:13:00",
        "16/04/2026 11:16:00",
        "16/04/2026 10:55:00",
        "16/04/2026 09:14:00",
        "16/04/2026 08:30:00",
        "16/04/2026 08:01:00",
        "16/04/2026 07:56:00",
        "16/04/2026 07:28:00",
        "16/04/2026 06:30:00",
        "16/04/2026 06:03:00",
        "16/04/2026 05:32:00",
        "16/04/2026 05:31:00",
        "16/04/2026 05:26:00",
        "15/04/2026 15:33:00",
        "15/04/2026 15:29:00",
        "14/04/2026 09:40:00",
    ]

    # Group by date
    events_by_date = {}
    for event in observed_events:
        date, hour = parse_timestamp(event)
        if date not in events_by_date:
            events_by_date[date] = []
        events_by_date[date].append(hour)

    print("\n" + "=" * 100)
    print("CONDENSATION BACKTEST: Historical Weather vs ECLRT Observed Events")
    print("=" * 100)
    print(f"Total events: {len(observed_events)}")
    print(f"Date range: {min(events_by_date.keys())} to {max(events_by_date.keys())}")
    if slab_temp:
        print(f"Slab temperature: {slab_temp}C")

    detected_total = 0
    missed_total = 0

    for event_date in sorted(events_by_date.keys()):
        expected_hours = sorted(events_by_date[event_date])
        print(f"\n{'-' * 100}")
        print(f"Date: {event_date} | Expected condensation at hours: {expected_hours}")
        print(f"{'-' * 100}")

        weather = fetch_historical_weather(43.6629, -79.3957, event_date)

        if not weather or "hourly" not in weather:
            print("  [NO DATA] Could not fetch historical weather")
            missed_total += len(expected_hours)
            continue

        hourly = weather["hourly"]
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        rhs = hourly.get("relative_humidity_2m", [])

        print(f"\n  {'Hour':<8} {'Temp':<8} {'RH':<8} {'Surface':<8} {'Margin':<8} {'Form':<8} {'Status':<20}")
        print(f"  {'-' * 100}")

        predicted_hours = []
        for i, time_str in enumerate(times):
            if i >= len(temps):
                break

            temp = temps[i]
            rh = rhs[i]

            # Estimate surface temp
            surface = temp
            if slab_temp is not None:
                surface = estimate_tile_floor_temp(temp, slab_temp)

            # Predict
            forecast = predict(temp, rh, surface)

            # Extract hour
            hour = int(time_str.split("T")[1][:2])

            # Check status
            if forecast.will_condense:
                predicted_hours.append(hour)
                status = "[PREDICTED]"
            else:
                status = ""

            print(f"  {hour:02d}:00   {temp:6.1f}C  {rh:6.1f}%  {surface:6.1f}C  {forecast.margin_c:+6.1f}C  {forecast.form:<8} {status}")

        # Match detection
        detected_in_date = 0
        missed_in_date = 0

        print(f"\n  Detection:")
        for exp_hour in expected_hours:
            if exp_hour in predicted_hours:
                print(f"    [MATCH] Hour {exp_hour:02d}:00 - DETECTED")
                detected_total += 1
                detected_in_date += 1
            else:
                print(f"    [MISS]  Hour {exp_hour:02d}:00 - NOT DETECTED")
                missed_total += 1
                missed_in_date += 1

        print(f"\n  Date summary: {detected_in_date} detected, {missed_in_date} missed")

    # Final summary
    total = detected_total + missed_total
    accuracy = (detected_total / total * 100) if total > 0 else 0

    print("\n" + "=" * 100)
    print("FINAL RESULTS")
    print("=" * 100)
    print(f"Events detected:     {detected_total}/{total} ({accuracy:.1f}%)")
    print(f"Events missed:       {missed_total}")

    if accuracy >= 95:
        print(f"\n[EXCELLENT] {accuracy:.1f}% detection rate - System validated")
    elif accuracy >= 80:
        print(f"\n[GOOD] {accuracy:.1f}% detection rate - Consider minor tuning")
    else:
        print(f"\n[CHECK] {accuracy:.1f}% detection rate - Review thresholds")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 backtest.py <config.json>")
        sys.exit(1)
    
    config_path = sys.argv[1]
    if not Path(config_path).exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    
    backtest_events(config_path)
