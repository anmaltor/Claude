# CLAUDE.md

## Project Overview

A Python CLI and web application for tracking Airbnb rental property revenue and costs. Uses SQLite for local data storage. The web frontend requires Flask.

## Repository Structure

```
.
├── hello_world.py                  # Simple hello world script
└── airbnb_tracker/                 # Main application package
    ├── __init__.py
    ├── __main__.py                 # Entry point for `python -m airbnb_tracker`
    ├── db.py                       # SQLite connection and schema initialization
    ├── models.py                   # Data access layer (CRUD + reports)
    ├── cli.py                      # argparse CLI and command handlers
    └── web.py                      # Flask web frontend
```

## Development Environment

- **Language**: Python 3
- **Runtime**: Python 3.11+
- **Database**: SQLite (via standard library `sqlite3`)
- **Web dependency**: Flask (`pip install flask`)

## Running the Application

```sh
# Show help
python3 -m airbnb_tracker --help

# Use a custom database file (default: ~/.airbnb_tracker.db)
python3 -m airbnb_tracker --db mydata.db <command>
```

### Key Commands

```sh
# Properties
python3 -m airbnb_tracker add-property "Beach House" --address "123 Ocean Ave"
python3 -m airbnb_tracker list-properties
python3 -m airbnb_tracker delete-property <id>

# Bookings
python3 -m airbnb_tracker add-booking <property_id> "Guest Name" 2026-01-10 2026-01-15 200 --fee 50
python3 -m airbnb_tracker list-bookings [--property-id <id>]
python3 -m airbnb_tracker delete-booking <id>

# Expenses (categories: cleaning, maintenance, supplies, utilities, insurance,
#           mortgage, property_tax, furnishing, marketing, other)
python3 -m airbnb_tracker add-expense <property_id> cleaning 120 2026-01-15 --description "Deep clean"
python3 -m airbnb_tracker list-expenses [--property-id <id>]
python3 -m airbnb_tracker delete-expense <id>

# Reports
python3 -m airbnb_tracker summary [--property-id <id>] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

### Web Frontend

```sh
# Install Flask
pip install flask

# Start the web server (accessible from any device on your network)
python3 -m airbnb_tracker.web --port 5000

# Use a custom database
python3 -m airbnb_tracker.web --db mydata.db
```

Then open `http://<your-ip>:5000` in a browser (including on your phone).

## Architecture

- **db.py** — Manages SQLite connections and initializes the schema (properties, bookings, expenses tables). Foreign keys are enforced.
- **models.py** — Pure data-access functions. Each function takes a `conn` as the first argument. Includes reporting queries (`property_summary`, `overall_summary`).
- **cli.py** — Thin CLI layer using `argparse`. Each subcommand maps to a handler function. Formatting helpers (`_fmt_money`, `_table`) live here.
- **__main__.py** — Allows `python -m airbnb_tracker` invocation.
- **web.py** — Flask web frontend. Mobile-friendly UI with dashboard, CRUD for properties/bookings/expenses. Run with `python -m airbnb_tracker.web`.

## Code Conventions

- Include module-level docstrings in every `.py` file
- Use a `main()` function with an `if __name__ == "__main__"` guard for scripts
- Follow PEP 8 style guidelines
- All dates use `YYYY-MM-DD` format
- Currency values stored as `REAL` in SQLite, displayed with `$X,XXX.XX` formatting
- Data access functions accept a `conn` parameter (no global state)

## Git Workflow

- **Default branch**: `master`
- Write clear, imperative commit messages (e.g., "Add feature X", not "Added feature X")
