# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A condensation prediction and monitoring tool. It computes dew point from air temperature and relative humidity (Magnus-Tetens approximation), decides whether condensation will form on a surface, and can run as an event-driven service that polls live METAR weather stations and dispatches alerts. Pure Python standard library only — no runtime dependencies; `pytest` is needed only for the test suite.

## Commands

```bash
# Run all tests
python3 -m pytest test_condensation.py -v

# Run a single test class or test
python3 -m pytest test_condensation.py::TestDewPoint -v
python3 -m pytest test_condensation.py::TestDewPoint::test_dew_point_basic -v

# Manual prediction (air temp / RH / optional surface temp)
python3 condensation.py -t 20 -r 60 -s 15

# Live observation from a METAR station (hits the network)
python3 condensation.py --station CYYZ

# Generate / validate config; inspect env-derived config
python3 config.py example > config.json
python3 config.py validate config.json
python3 config.py from-env

# Run monitoring loop (long-running; polls the network)
python3 condensation.py --monitor --config config.json --verbose

# Smoke-test notifier channels with a mock alert
python3 notifier.py config.json
```

## Architecture

The codebase is a small set of single-purpose modules with a clear dependency direction. `condensation.py` is the foundation and imports nothing from the others; everything else depends on it.

- **`condensation.py`** — Core model + CLI entry point. Pure functions: `dew_point_c`, `relative_humidity_from_dew_point` (its inverse), `estimate_tile_floor_temp` (1-D thermal-resistance model for ceramic tile over a slab), and `predict` which returns a frozen `CondensationForecast` dataclass. `predict` classifies the result as `none`/`dew`/`frost`/`fog` based on the margin (surface_temp − dew_point) and whether a surface temp was supplied. Also holds `fetch_station_observation`, the only network call into the NOAA Aviation Weather METAR API. `main()` dispatches between manual prediction and `--monitor` mode (the latter lazily imports `monitor.run_monitor`).

- **`monitor.py`** — Event-driven orchestration. `StationMonitor` polls one station, runs `predict`, and applies per-form alert de-duplication via a cooldown (`MonitorAlert`, default 3600s) so the same condition doesn't re-fire each poll. `MonitoringService` builds one monitor per configured station and runs `run_loop` (blocking `time.sleep` between polls). Depends on `condensation` and `notifier`.

- **`notifier.py`** — `Notifier` fan-outs a single alert dict to all enabled channels: console (default on), SMTP email, and webhooks (generic JSON POST, Slack-compatible). Channel failures are caught and logged, never raised — one broken channel must not stop the others.

- **`config.py`** — `Config` static-method helpers: load from JSON file or env vars (`CONDENSATION_*`), `merge_with_defaults` (deep-merges nested dicts like `notifier_config`), and `validate`. Note: the monitoring loader in `monitor.run_monitor` reads the JSON directly with `json.load` and does **not** route through `Config.merge_with_defaults`/`validate` — defaults there come from `.get(..., default)` calls at use sites.

### The alert dict contract

`StationMonitor.poll` produces a dict with a fixed shape — `station`, `observation_time`, `air_temp_c`, `relative_humidity_pct`, `surface_temp_c`, and a nested `forecast` (`dew_point_c`, `margin_c`, `form`). Every notifier formatter and `notifier.notify_test`'s mock depend on this exact shape. Changing it means updating all consumers in lockstep.

## Conventions

- Standard library only for core/runtime code; keep it that way unless a dependency is clearly justified.
- `from __future__ import annotations` at the top of every module; modern type hints (`X | None`, `list[...]`).
- Surface temperature semantics: passing `surface_temp_c=None` to `predict` means "use air temp" → fog detection. `--surface` (measured) and `--slab-temp` (estimated via `estimate_tile_floor_temp`) are mutually exclusive on the CLI.
- `config.json` is committed and may contain real settings — never commit secrets into it; `config.example.json` is the shareable template.
