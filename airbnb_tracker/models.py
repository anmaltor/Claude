"""Data access functions for properties, bookings, and expenses."""

from datetime import datetime


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

def add_property(conn, name, address=""):
    """Insert a new property and return its id."""
    cur = conn.execute(
        "INSERT INTO properties (name, address) VALUES (?, ?)",
        (name, address),
    )
    conn.commit()
    return cur.lastrowid


def list_properties(conn):
    """Return all properties."""
    return conn.execute("SELECT * FROM properties ORDER BY id").fetchall()


def get_property(conn, property_id):
    """Return a single property by id."""
    return conn.execute(
        "SELECT * FROM properties WHERE id = ?", (property_id,)
    ).fetchone()


def delete_property(conn, property_id):
    """Delete a property and its associated bookings and expenses."""
    conn.execute("DELETE FROM bookings WHERE property_id = ?", (property_id,))
    conn.execute("DELETE FROM expenses WHERE property_id = ?", (property_id,))
    conn.execute("DELETE FROM properties WHERE id = ?", (property_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------

def add_booking(conn, property_id, guest_name, check_in, check_out,
                nightly_rate, platform_fee=0):
    """Insert a booking. Calculates nights and total_revenue automatically."""
    ci = datetime.strptime(check_in, "%Y-%m-%d")
    co = datetime.strptime(check_out, "%Y-%m-%d")
    nights = (co - ci).days
    if nights <= 0:
        raise ValueError("check_out must be after check_in")
    total_revenue = nightly_rate * nights - platform_fee
    cur = conn.execute(
        """INSERT INTO bookings
           (property_id, guest_name, check_in, check_out,
            nightly_rate, nights, total_revenue, platform_fee)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (property_id, guest_name, check_in, check_out,
         nightly_rate, nights, total_revenue, platform_fee),
    )
    conn.commit()
    return cur.lastrowid


def list_bookings(conn, property_id=None):
    """Return bookings, optionally filtered by property."""
    if property_id:
        return conn.execute(
            "SELECT * FROM bookings WHERE property_id = ? ORDER BY check_in",
            (property_id,),
        ).fetchall()
    return conn.execute("SELECT * FROM bookings ORDER BY check_in").fetchall()


def delete_booking(conn, booking_id):
    """Delete a booking by id."""
    conn.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------

EXPENSE_CATEGORIES = [
    "cleaning",
    "maintenance",
    "supplies",
    "utilities",
    "insurance",
    "mortgage",
    "property_tax",
    "furnishing",
    "marketing",
    "other",
]


def add_expense(conn, property_id, category, amount, date, description=""):
    """Insert an expense."""
    cur = conn.execute(
        """INSERT INTO expenses
           (property_id, category, description, amount, date)
           VALUES (?, ?, ?, ?, ?)""",
        (property_id, category, description, amount, date),
    )
    conn.commit()
    return cur.lastrowid


def list_expenses(conn, property_id=None):
    """Return expenses, optionally filtered by property."""
    if property_id:
        return conn.execute(
            "SELECT * FROM expenses WHERE property_id = ? ORDER BY date",
            (property_id,),
        ).fetchall()
    return conn.execute("SELECT * FROM expenses ORDER BY date").fetchall()


def delete_expense(conn, expense_id):
    """Delete an expense by id."""
    conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def property_summary(conn, property_id, start_date=None, end_date=None):
    """Return a financial summary for a property within an optional date range."""
    params_booking = [property_id]
    params_expense = [property_id]
    booking_filter = ""
    expense_filter = ""

    if start_date:
        booking_filter += " AND check_in >= ?"
        expense_filter += " AND date >= ?"
        params_booking.append(start_date)
        params_expense.append(start_date)
    if end_date:
        booking_filter += " AND check_out <= ?"
        expense_filter += " AND date <= ?"
        params_booking.append(end_date)
        params_expense.append(end_date)

    rev = conn.execute(
        f"""SELECT COALESCE(SUM(total_revenue), 0) as total_revenue,
                   COALESCE(SUM(nights), 0) as total_nights,
                   COUNT(*) as num_bookings
            FROM bookings
            WHERE property_id = ?{booking_filter}""",
        params_booking,
    ).fetchone()

    exp = conn.execute(
        f"""SELECT COALESCE(SUM(amount), 0) as total_expenses
            FROM expenses
            WHERE property_id = ?{expense_filter}""",
        params_expense,
    ).fetchone()

    exp_by_cat = conn.execute(
        f"""SELECT category, SUM(amount) as total
            FROM expenses
            WHERE property_id = ?{expense_filter}
            GROUP BY category ORDER BY total DESC""",
        params_expense,
    ).fetchall()

    return {
        "total_revenue": rev["total_revenue"],
        "total_nights": rev["total_nights"],
        "num_bookings": rev["num_bookings"],
        "total_expenses": exp["total_expenses"],
        "net_profit": rev["total_revenue"] - exp["total_expenses"],
        "expenses_by_category": [(r["category"], r["total"]) for r in exp_by_cat],
    }


def overall_summary(conn, start_date=None, end_date=None):
    """Return a summary across all properties."""
    properties = list_properties(conn)
    rows = []
    totals = {"revenue": 0, "expenses": 0, "profit": 0, "nights": 0, "bookings": 0}
    for prop in properties:
        s = property_summary(conn, prop["id"], start_date, end_date)
        rows.append({"property": prop["name"], **s})
        totals["revenue"] += s["total_revenue"]
        totals["expenses"] += s["total_expenses"]
        totals["profit"] += s["net_profit"]
        totals["nights"] += s["total_nights"]
        totals["bookings"] += s["num_bookings"]
    return rows, totals
