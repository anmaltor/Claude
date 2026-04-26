#!/usr/bin/env python3
"""Predict when condensation will form from weather conditions.

Uses the Magnus-Tetens approximation to compute the dew point from air
temperature and relative humidity. Condensation forms on a surface when the
surface temperature is at or below the dew point of the surrounding air.
"""

from __future__ import annotations

import argparse
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
    p.add_argument("-t", "--temp", type=float, required=True, help="air temperature (C)")
    p.add_argument("-r", "--rh", type=float, required=True, help="relative humidity (%%)")
    p.add_argument("-s", "--surface", type=float, default=None, help="surface temperature (C)")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    print(predict(args.temp, args.rh, args.surface))


if __name__ == "__main__":
    main()
