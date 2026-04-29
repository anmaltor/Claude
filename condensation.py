#!/usr/bin/env python3
"""Predict when condensation will form from weather conditions.

Uses the Magnus-Tetens approximation to compute the dew point from air
temperature and relative humidity. Condensation forms on a surface when the
surface temperature is at or below the dew point of the surrounding air.

Live observations can be pulled from any METAR-reporting station via the
NOAA Aviation Weather API (e.g. CYYZ for Toronto Pearson).
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from dataclasses import dataclass

# Magnus-Tetens coefficients (Alduchov & Eskridge, 1996); valid for -40..50 C.
_A = 17.625
_B = 243.04


def dew_point_c(temp_c: float, relative_humidity_pct: float) -> float:
    """Return the dew point in degrees Celsius."""
    if not 0 < relative_humidity_pct <= 100:
        raise ValueError("relative humidity must be in (0, 100]")
    from math import log

    rh = relative_humidity_pct / 100.0
    gamma = log(rh) + (_A * temp_c) / (_B + temp_c)
    return (_B * gamma) / (_A - gamma)


@dataclass(frozen=True)
class CondensationForecast:
    dew_point_c: float
    will_condense: bool
    margin_c: float  # surface_temp - dew_point; <=0 means condensation
    form: str  # "none", "dew", "frost", or "fog"

    def __str__(self) -> str:
        return (
            f"dew point: {self.dew_point_c:.1f} C\n"
            f"margin:    {self.margin_c:+.1f} C\n"
            f"condenses: {self.will_condense} ({self.form})"
        )


def relative_humidity_from_dew_point(temp_c: float, dew_point_c: float) -> float:
    """Inverse of `dew_point_c`: derive RH (%) from temperature and dew point."""
    from math import exp

    e_t = exp((_A * temp_c) / (_B + temp_c))
    e_td = exp((_A * dew_point_c) / (_B + dew_point_c))
    return 100.0 * e_td / e_t


_METAR_URL = "https://aviationweather.gov/api/data/metar?ids={station}&format=json&hours=1"


def fetch_station_observation(station: str, timeout: float = 10.0) -> dict:
    """Fetch the most recent METAR observation for `station` (ICAO code).

    Returns a dict with at least `temp_c`, `dew_point_c`, `relative_humidity_pct`,
    `observation_time`, and `raw` (the raw METAR string).
    """
    url = _METAR_URL.format(station=station.upper())
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            payload = json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(f"could not reach aviation weather API: {e}") from e

    if not payload:
        raise RuntimeError(f"no recent METAR for station {station!r}")

    obs = payload[0]
    if obs.get("temp") is None or obs.get("dewp") is None:
        raise RuntimeError(f"METAR for {station!r} is missing temp/dewp fields")

    t = float(obs["temp"])
    td = float(obs["dewp"])
    return {
        "temp_c": t,
        "dew_point_c": td,
        "relative_humidity_pct": relative_humidity_from_dew_point(t, td),
        "observation_time": obs.get("reportTime") or obs.get("obsTime"),
        "raw": obs.get("rawOb", ""),
    }


def predict(
    air_temp_c: float,
    relative_humidity_pct: float,
    surface_temp_c: float | None = None,
) -> CondensationForecast:
    """Predict condensation given air temperature, RH, and a surface temperature.

    If `surface_temp_c` is omitted, the air temperature is used (i.e. fog/cloud
    formation when the air itself is saturated).
    """
    td = dew_point_c(air_temp_c, relative_humidity_pct)
    target = air_temp_c if surface_temp_c is None else surface_temp_c
    margin = target - td
    will = margin <= 0

    if not will:
        form = "none"
    elif surface_temp_c is None:
        form = "fog"
    elif target <= 0:
        form = "frost"
    else:
        form = "dew"

    return CondensationForecast(td, will, margin, form)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("-t", "--temp", type=float, help="air temperature (C)")
    p.add_argument("-r", "--rh", type=float, help="relative humidity (%%)")
    p.add_argument("-s", "--surface", type=float, default=None, help="surface temperature (C)")
    p.add_argument(
        "--station",
        help="ICAO station code to fetch live observations from (e.g. CYYZ)",
    )
    args = p.parse_args()
    if args.station is None and (args.temp is None or args.rh is None):
        p.error("either --station, or both --temp and --rh, must be provided")
    return args


def main() -> None:
    args = _parse_args()
    if args.station is not None:
        obs = fetch_station_observation(args.station)
        print(f"station:   {args.station.upper()} @ {obs['observation_time']}")
        print(f"observed:  {obs['temp_c']:.1f} C / {obs['relative_humidity_pct']:.0f}% RH")
        if obs["raw"]:
            print(f"raw METAR: {obs['raw']}")
        temp = obs["temp_c"]
        rh = obs["relative_humidity_pct"]
    else:
        temp = args.temp
        rh = args.rh
    print(predict(temp, rh, args.surface))


if __name__ == "__main__":
    main()
