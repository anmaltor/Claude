#!/usr/bin/env python3
"""Weather forecast and condensation prediction for upcoming days."""

import json
import urllib.request
from datetime import datetime, timedelta
from condensation import predict, estimate_tile_floor_temp


def fetch_forecast(lat: float, lon: float, days: int = 7) -> dict:
    """Fetch weather forecast using Open-Meteo API (free, no key needed).
    
    Args:
        lat, lon: Coordinates (Toronto: 43.6629, -79.3957)
        days: Number of days to forecast
    
    Returns:
        Forecast data with hourly predictions
    """
    end_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    start_date = datetime.now().strftime("%Y-%m-%d")
    
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&start_date={start_date}&end_date={end_date}&hourly=temperature_2m,relative_humidity_2m,dew_point_2m&timezone=America/Toronto"
    
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"Error fetching forecast: {e}")
        return {}


def analyze_forecast(config: dict, days: int = 7) -> dict:
    """Analyze condensation risk in forecast.
    
    Returns:
        Dict with daily summaries and risk indicators
    """
    forecast_data = fetch_forecast(43.6629, -79.3957, days)
    
    if not forecast_data or "hourly" not in forecast_data:
        return {"error": "Could not fetch forecast"}
    
    slab_temp = config.get("slab_temp_c")
    hourly = forecast_data["hourly"]
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    rhs = hourly.get("relative_humidity_2m", [])
    
    # Group by day
    daily_summary = {}
    
    for i, time_str in enumerate(times):
        if i >= len(temps):
            break
        
        date = time_str.split("T")[0]
        hour = int(time_str.split("T")[1].split(":")[0])
        
        temp = temps[i]
        rh = rhs[i]
        
        surface = temp
        if slab_temp is not None:
            surface = estimate_tile_floor_temp(temp, slab_temp)
        
        forecast = predict(temp, rh, surface)
        
        if date not in daily_summary:
            daily_summary[date] = {
                "date": date,
                "hours_at_risk": 0,
                "peak_margin": float('inf'),
                "risk_hours": [],
                "min_temp": temp,
                "max_temp": temp,
                "avg_rh": rh,
                "count": 0
            }
        
        daily_summary[date]["count"] += 1
        daily_summary[date]["avg_rh"] = (daily_summary[date]["avg_rh"] + rh) / 2
        daily_summary[date]["min_temp"] = min(daily_summary[date]["min_temp"], temp)
        daily_summary[date]["max_temp"] = max(daily_summary[date]["max_temp"], temp)
        
        if forecast.will_condense:
            daily_summary[date]["hours_at_risk"] += 1
            daily_summary[date]["risk_hours"].append(hour)
            daily_summary[date]["peak_margin"] = min(daily_summary[date]["peak_margin"], forecast.margin_c)
    
    return daily_summary


def format_forecast_report(config: dict) -> str:
    """Format forecast as readable report."""
    forecast = analyze_forecast(config, days=7)
    
    if "error" in forecast:
        return f"Forecast unavailable: {forecast['error']}\n"
    
    report = "\n7-DAY CONDENSATION FORECAST\n"
    report += "=" * 60 + "\n\n"
    
    sorted_days = sorted(forecast.keys())
    for date in sorted_days[:7]:
        day_data = forecast[date]
        day_of_week = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
        
        if day_data["hours_at_risk"] == 0:
            risk_level = "GREEN - LOW RISK"
        elif day_data["hours_at_risk"] <= 6:
            risk_level = "YELLOW - MODERATE RISK"
        else:
            risk_level = "RED - HIGH RISK"
        
        report += f"{day_of_week} ({date})\n"
        report += f"  Temperature: {day_data['min_temp']:5.1f}C - {day_data['max_temp']:5.1f}C\n"
        report += f"  Humidity: {day_data['avg_rh']:5.1f}%\n"
        report += f"  Condensation risk: {day_data['hours_at_risk']} hours\n"
        report += f"  Risk level: {risk_level}\n"
        
        if day_data["hours_at_risk"] > 0:
            report += f"  At-risk hours: {', '.join(f'{h:02d}:00' for h in sorted(set(day_data['risk_hours'])))}\n"
        
        report += "\n"
    
    return report


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python3 forecast.py <config.json>")
        sys.exit(1)
    
    with open(sys.argv[1]) as f:
        config = json.load(f)
    
    print(format_forecast_report(config))
