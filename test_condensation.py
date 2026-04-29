#!/usr/bin/env python3
"""Unit tests for condensation prediction module."""

import pytest
from condensation import (
    dew_point_c,
    relative_humidity_from_dew_point,
    predict,
    estimate_tile_floor_temp,
    CondensationForecast,
)


class TestDewPoint:
    """Tests for Magnus-Tetens dew point calculation."""

    def test_dew_point_basic(self):
        """Test basic dew point calculation with typical values."""
        # At 20°C and 60% RH, dew point should be ~11.9°C
        dp = dew_point_c(20.0, 60.0)
        assert 11.5 < dp < 12.5

    def test_dew_point_high_humidity(self):
        """Dew point approaches air temperature at high humidity."""
        # At 25°C and 95% RH, dew point should be very close to 25°C
        dp = dew_point_c(25.0, 95.0)
        assert 24.0 < dp < 25.0

    def test_dew_point_low_humidity(self):
        """Dew point is well below air temperature at low humidity."""
        # At 20°C and 20% RH, dew point should be ~-8°C
        dp = dew_point_c(20.0, 20.0)
        assert -10.0 < dp < -5.0

    def test_dew_point_freezing_air_temp(self):
        """Test dew point at freezing temperatures."""
        # At -5°C and 80% RH
        dp = dew_point_c(-5.0, 80.0)
        assert dp < -5.0  # Dew point always <= air temp

    def test_dew_point_saturation(self):
        """At 100% RH, dew point equals air temperature."""
        # Note: formula doesn't technically reach 100%, but gets very close
        # We test at 99% which should be extremely close
        dp = dew_point_c(15.0, 99.99)
        assert abs(dp - 15.0) < 0.01

    def test_dew_point_invalid_humidity_zero(self):
        """RH = 0 is invalid."""
        with pytest.raises(ValueError):
            dew_point_c(20.0, 0.0)

    def test_dew_point_invalid_humidity_over_100(self):
        """RH > 100 is invalid."""
        with pytest.raises(ValueError):
            dew_point_c(20.0, 100.1)

    def test_dew_point_invalid_humidity_negative(self):
        """RH < 0 is invalid."""
        with pytest.raises(ValueError):
            dew_point_c(20.0, -10.0)

    def test_dew_point_extreme_cold(self):
        """Test at lower end of Magnus-Tetens validity range (-40°C)."""
        dp = dew_point_c(-40.0, 50.0)
        assert dp < -40.0

    def test_dew_point_extreme_heat(self):
        """Test at upper end of Magnus-Tetens validity range (50°C)."""
        dp = dew_point_c(50.0, 50.0)
        assert dp < 50.0


class TestRelativeHumidity:
    """Tests for relative humidity calculation (inverse of dew point)."""

    def test_rh_from_dew_point_basic(self):
        """Test basic RH derivation from temperature and dew point."""
        # If temp=20°C and dew_point=10°C, RH should be ~52%
        rh = relative_humidity_from_dew_point(20.0, 10.0)
        assert 50.0 < rh < 55.0

    def test_rh_from_dew_point_saturation(self):
        """When dew point equals air temp, RH should be ~100%."""
        rh = relative_humidity_from_dew_point(20.0, 20.0)
        assert 99.0 < rh <= 100.0

    def test_rh_from_dew_point_low(self):
        """Low RH when dew point is far below air temp."""
        rh = relative_humidity_from_dew_point(20.0, 0.0)
        assert 0 < rh < 50.0

    def test_rh_dew_point_roundtrip(self):
        """RH calculation should be inverse of dew_point_c."""
        air_temp = 22.5
        rh_original = 65.0

        # Forward: air_temp + RH -> dew_point
        dp = dew_point_c(air_temp, rh_original)

        # Backward: air_temp + dew_point -> RH
        rh_recovered = relative_humidity_from_dew_point(air_temp, dp)

        # Should recover original RH within 0.5%
        assert abs(rh_recovered - rh_original) < 0.5

    def test_rh_from_dew_point_freezing(self):
        """Test RH at freezing temperatures."""
        # -10°C air, -15°C dew point
        rh = relative_humidity_from_dew_point(-10.0, -15.0)
        assert 0 < rh < 100


class TestCondensationPredict:
    """Tests for condensation prediction logic."""

    def test_predict_no_condensation_clear_margin(self):
        """Clear margin above dew point - no condensation."""
        # 20°C air, 30% RH, 18°C surface temp
        # Dew point ~-4°C, margin = 18 - (-4) = +22°C
        forecast = predict(20.0, 30.0, 18.0)
        assert not forecast.will_condense
        assert forecast.form == "none"
        assert forecast.margin_c > 0

    def test_predict_condensation_dew(self):
        """Surface below dew point - dew forms."""
        # 20°C air, 80% RH, 5°C surface
        # Dew point ~16°C, margin = 5 - 16 = -11°C
        forecast = predict(20.0, 80.0, 5.0)
        assert forecast.will_condense
        assert forecast.form == "dew"
        assert forecast.margin_c <= 0

    def test_predict_condensation_frost(self):
        """Surface below freezing - frost forms."""
        forecast = predict(0.0, 80.0, -5.0)
        assert forecast.will_condense
        assert forecast.form == "frost"

    def test_predict_condensation_fog(self):
        """No surface specified - fog forms when air saturated."""
        # 10°C air, 100% RH, no surface
        forecast = predict(10.0, 100.0, surface_temp_c=None)
        assert forecast.will_condense
        assert forecast.form == "fog"

    def test_predict_no_fog(self):
        """No fog when air is not saturated."""
        forecast = predict(10.0, 50.0, surface_temp_c=None)
        assert not forecast.will_condense
        assert forecast.form == "none"

    def test_predict_boundary_no_condensation(self):
        """Surface exactly at dew point - boundary case."""
        # 20°C air, 50% RH -> dew point ~9.3°C
        dp = dew_point_c(20.0, 50.0)
        forecast = predict(20.0, 50.0, dp)
        assert forecast.will_condense  # <= 0 means condensation
        assert forecast.margin_c <= 0.01

    def test_predict_cold_night(self):
        """Realistic cold night scenario."""
        # Clear night: 5°C air, 85% RH, clear sky cools surface to 0°C
        forecast = predict(5.0, 85.0, 0.0)
        assert forecast.will_condense
        assert forecast.form == "dew"

    def test_predict_warm_humid_day(self):
        """Warm humid day - no condensation risk."""
        forecast = predict(28.0, 60.0, 25.0)
        assert not forecast.will_condense
        assert forecast.form == "none"


class TestTileSurfaceTemp:
    """Tests for ceramic tile floor temperature estimation."""

    def test_tile_temp_equals_slab_at_extreme(self):
        """When slab is much colder than air, surface approaches slab temp."""
        # Very cold slab, warm air
        tile_temp = estimate_tile_floor_temp(20.0, -10.0)
        assert -10.0 < tile_temp < 0.0  # Closer to slab than air

    def test_tile_temp_equals_air_at_equilibrium(self):
        """When slab equals air temp, surface should be at air temp."""
        tile_temp = estimate_tile_floor_temp(20.0, 20.0)
        assert abs(tile_temp - 20.0) < 0.01

    def test_tile_temp_between_slab_and_air(self):
        """Surface temp is always between slab and air temps."""
        tile_temp = estimate_tile_floor_temp(20.0, 5.0)
        assert 5.0 < tile_temp < 20.0

    def test_tile_temp_warm_slab(self):
        """Warm slab, cooler air."""
        tile_temp = estimate_tile_floor_temp(15.0, 25.0)
        assert 15.0 < tile_temp < 25.0

    def test_tile_temp_with_custom_params(self):
        """Test with non-default thermal parameters."""
        # Thinner tile (higher surface temp effect)
        thin_tile = estimate_tile_floor_temp(
            20.0, 10.0, tile_thickness_m=0.005
        )
        # Thicker tile (lower surface temp effect)
        thick_tile = estimate_tile_floor_temp(
            20.0, 10.0, tile_thickness_m=0.020
        )
        # Thinner tile should be warmer (closer to air temp)
        assert thin_tile > thick_tile

    def test_tile_temp_high_conductivity(self):
        """High conductivity tile conducts more heat from slab."""
        low_cond = estimate_tile_floor_temp(
            20.0, 10.0, tile_conductivity_w_mk=1.0
        )
        high_cond = estimate_tile_floor_temp(
            20.0, 10.0, tile_conductivity_w_mk=2.0
        )
        # High conductivity = more slab effect = cooler surface
        assert high_cond < low_cond

    def test_tile_temp_high_convection(self):
        """High air-film coefficient increases air influence."""
        low_conv = estimate_tile_floor_temp(
            20.0, 10.0, air_film_coefficient_w_m2k=5.0
        )
        high_conv = estimate_tile_floor_temp(
            20.0, 10.0, air_film_coefficient_w_m2k=15.0
        )
        # High convection = more air influence = warmer surface
        assert high_conv > low_conv


class TestCondensationForecast:
    """Tests for CondensationForecast dataclass."""

    def test_forecast_dataclass_creation(self):
        """Create a forecast with all fields."""
        forecast = CondensationForecast(
            dew_point_c=10.5, will_condense=True, margin_c=-2.3, form="dew"
        )
        assert forecast.dew_point_c == 10.5
        assert forecast.will_condense is True
        assert forecast.margin_c == -2.3
        assert forecast.form == "dew"

    def test_forecast_frozen(self):
        """CondensationForecast is immutable."""
        forecast = CondensationForecast(
            dew_point_c=10.0, will_condense=False, margin_c=5.0, form="none"
        )
        with pytest.raises(AttributeError):
            forecast.dew_point_c = 20.0

    def test_forecast_str_representation(self):
        """String representation is readable."""
        forecast = CondensationForecast(
            dew_point_c=10.5, will_condense=True, margin_c=-2.3, form="dew"
        )
        s = str(forecast)
        assert "10.5" in s
        assert "dew point:" in s
        assert "margin:" in s
        assert "condenses:" in s

    def test_forecast_with_fog(self):
        """Forecast for fog formation."""
        forecast = CondensationForecast(
            dew_point_c=5.0, will_condense=True, margin_c=0.0, form="fog"
        )
        assert "fog" in str(forecast)

    def test_forecast_with_frost(self):
        """Forecast for frost formation."""
        forecast = CondensationForecast(
            dew_point_c=-3.0, will_condense=True, margin_c=-1.5, form="frost"
        )
        assert "frost" in str(forecast)


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_full_prediction_workflow_cold_night(self):
        """Complete workflow: fetch-like conditions -> tile temp -> predict."""
        # Simulated METAR: 8°C, 85% RH
        air_temp = 8.0
        air_rh = 85.0
        slab_temp = 12.0  # Slab is still warm from day

        # Estimate surface temp
        surface_temp = estimate_tile_floor_temp(air_temp, slab_temp)

        # Predict condensation
        forecast = predict(air_temp, air_rh, surface_temp)

        assert forecast.will_condense
        assert forecast.form in ["dew", "frost"]

    def test_full_prediction_workflow_warm_day(self):
        """Complete workflow for warm daytime conditions."""
        air_temp = 25.0
        air_rh = 45.0
        slab_temp = 22.0

        surface_temp = estimate_tile_floor_temp(air_temp, slab_temp)
        forecast = predict(air_temp, air_rh, surface_temp)

        assert not forecast.will_condense
        assert forecast.form == "none"

    def test_rh_consistency_across_temps(self):
        """Relative humidity derived from dew point is consistent."""
        for air_temp in [-10, 0, 10, 20, 30]:
            for rh_input in [20, 50, 80, 95]:
                dp = dew_point_c(air_temp, rh_input)
                rh_output = relative_humidity_from_dew_point(air_temp, dp)
                assert abs(rh_output - rh_input) < 0.5
