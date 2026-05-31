# CLAUDE.md

Guidance for AI assistants (and humans) working in this repository.

## What this project is

A condensation prediction and monitoring tool. It computes the dew point from
air temperature and relative humidity using the Magnus-Tetens approximation,
then decides whether condensation will form on a given surface. It can run as a
one-shot CLI prediction or as a long-running service that polls METAR weather
stations and sends alerts.

Pure Python 3.7+, **standard library only** for all runtime code. The only
third-party dependency is `pytest`, and that is for tests alone. Do not add
runtime dependencies without a strong reason — keeping the install to the
stdlib is a deliberate design choice.

## Layout

| File | Role |
|------|------|
| `condensation.py` | Core science + CLI entry point. Dew point, prediction, tile-surface thermal model, METAR fetch, argument parsing, `main()`. |
| `monitor.py` | Event-driven monitoring: `StationMonitor` (one station), `MonitoringService` (many stations + poll loop), `run_monitor()`. |
| `notifier.py` | Alert delivery backends: console, SMTP email, webhooks. `Notifier` class + `notify_test()` helper. |
| `config.py` | `Config` class for loading/merging/validating config from JSON files or environment variables; also a small CLI (`example`, `validate`, `from-env`). |
| `test_condensation.py` | Pytest unit + integration tests for the core science functions. |
| `hello_world.py` | Unused starter script; not part of the application. |
| `config.example.json` | Template config — copy this, never commit real secrets. |
| `config.json` | Local working config (see the security note below). |

### Dependency direction

`condensation.py` is the foundation and imports nothing local. `monitor.py`
imports from `condensation` and `notifier`. `notifier.py` is self-contained.
`config.py` is standalone. Keep this direction acyclic — core science stays
free of monitoring/notification concerns.

## Core concepts

- **Dew point** (`dew_point_c`): Magnus-Tetens with coefficients `_A = 17.625`,
  `_B = 243.04`, valid roughly -40..50 °C. RH must be in `(0, 100]`.
- **Margin** = `surface_temp - dew_point`. `margin <= 0` means condensation.
- **Form**: `"none"`, `"dew"` (surface > 0 °C), `"frost"` (surface <= 0 °C), or
  `"fog"` (no surface given and air is saturated). Decided in `predict()`.
- **Tile thermal model** (`estimate_tile_floor_temp`): treats a ceramic tile
  over a slab as a 1-D thermal resistor between slab and air. Surface temp is
  always between slab and air temps.
- **CondensationForecast**: frozen dataclass (`dew_point_c`, `will_condense`,
  `margin_c`, `form`) with a human-readable `__str__`.
- **METAR**: live observations via the NOAA Aviation Weather API
  (`https://aviationweather.gov/api/data/metar`). Stations are ICAO codes
  (e.g. `CYYZ` = Toronto Pearson). `fetch_station_observation()` derives RH from
  the reported temp/dewp via `relative_humidity_from_dew_point`.
- **Alert de-duplication**: `StationMonitor` keeps `alert_history` keyed by form
  and suppresses repeats within `MonitorAlert.cooldown_seconds` (default 3600).

## Common commands

```bash
# One-shot prediction (manual inputs)
python3 condensation.py -t 20 -r 60 -s 15      # temp °C / RH % / surface °C

# Live METAR observation, optionally with a slab estimate
python3 condensation.py --station CYYZ
python3 condensation.py --station CYYZ --slab-temp 12.5

# Monitoring service (requires --config)
python3 condensation.py --monitor --config config.json --verbose

# Config helpers
python3 config.py example > config.json        # write a template
python3 config.py validate config.json
python3 config.py from-env

# Test the notifier wiring with a mock alert
python3 notifier.py config.json

# Tests (pytest is NOT installed by default in fresh environments)
python3 -m pip install pytest
python3 -m pytest test_condensation.py -v
python3 -m pytest test_condensation.py::TestDewPoint -v
```

Current test baseline: as of this writing **5 of 38 tests fail** on a clean
checkout (`test_dew_point_low_humidity`, `test_predict_condensation_fog`,
`test_predict_cold_night`, `test_tile_temp_with_custom_params`,
`test_full_prediction_workflow_cold_night`). These appear to be mismatches
between test expectations and the current model/thresholds, not environment
issues. Do not assume a green suite is the starting point — run the tests first
and treat the failures above as the known baseline unless you are explicitly
fixing them.

CLI argument rules enforced in `_parse_args()`:
- `--monitor` requires `--config`.
- Otherwise you must pass either `--station`, or both `--temp` and `--rh`.
- `--surface` (measured) and `--slab-temp` (estimate) are mutually exclusive.

## Configuration

Config is a plain dict, normally loaded from JSON and merged onto
`Config.DEFAULTS` (nested dicts are deep-merged one level). Keys:
`polling_interval_seconds`, `threshold_margin_c`, `slab_temp_c` (nullable),
`stations` (list of `{"code": "ICAO"}`), and `notifier_config`
(`console` bool, `email` dict, `webhooks` list). Environment overrides:
`CONDENSATION_CONFIG`, `CONDENSATION_STATIONS`, `CONDENSATION_INTERVAL`,
`CONDENSATION_THRESHOLD`, `CONDENSATION_SLAB_TEMP`.

Note: `condensation.py --monitor` / `run_monitor()` load JSON directly with
`json.load` and do **not** run `Config.merge_with_defaults` or `Config.validate`.
If you change config handling, decide deliberately whether validation should be
wired into the monitor path.

## Conventions

- Python 3.7+ with `from __future__ import annotations`; use modern type hints
  (`X | None`, `list[...]`, `Optional[...]`) consistently with each file.
- Every module, class, and public function has a docstring. Match that density.
- Core science functions are pure and side-effect free; keep I/O (network,
  SMTP, printing) in `monitor.py`/`notifier.py`, not in `condensation.py`'s math.
- Temperatures are °C, humidity is percent (0-100), margins are signed °C.
- Each module is independently runnable via a `__main__` guard.
- When you touch the science functions, add or update tests in
  `test_condensation.py` (organized as `Test*` classes by concern). When you
  change CLI flags or config keys, update `README.md` to match.

## Security note — do not commit secrets

`config.json` currently contains a personal email address and a live-looking
Gmail SMTP app password. Secrets must never be committed. When working here:
- Treat any credentials in `config.json` as compromised and recommend rotation.
- Add real config to `.gitignore` (currently it only ignores Python bytecode)
  and keep only `config.example.json` with placeholders under version control.
- Never echo secrets into logs, commits, PR descriptions, or external requests.

## Git workflow

- Branch names follow `claude/<topic>` (e.g. the active `claude/...` branch).
- Commit messages are short and imperative, often prefixed (`Add ...`,
  `Update: ...`). Keep that style.
- Do not push to a different branch than the one assigned for the task, and open
  pull requests as drafts.
</content>
</invoke>
