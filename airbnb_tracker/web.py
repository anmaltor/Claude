"""Flask web frontend for the Airbnb tracker."""

import os
from flask import Flask, request, redirect, url_for, render_template_string

from . import db, models

app = Flask(__name__)

DB_PATH = os.environ.get("AIRBNB_TRACKER_DB", None)


def _get_conn():
    """Get a database connection."""
    conn = db.get_connection(DB_PATH)
    db.init_db(conn)
    return conn


def _fmt_money(amount):
    """Format a number as currency."""
    return f"${amount:,.2f}"


# ---------------------------------------------------------------------------
# Base template
# ---------------------------------------------------------------------------

BASE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Airbnb Tracker</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         background: #f5f5f5; color: #333; line-height: 1.5; }
  .container { max-width: 800px; margin: 0 auto; padding: 16px; }
  nav { background: #ff5a5f; padding: 12px 0; margin-bottom: 24px; }
  nav .container { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
  nav a { color: #fff; text-decoration: none; font-weight: 500; font-size: 0.95rem; }
  nav a:hover { text-decoration: underline; }
  nav .brand { font-size: 1.2rem; font-weight: 700; margin-right: auto; }
  h1 { margin-bottom: 16px; font-size: 1.5rem; }
  .card { background: #fff; border-radius: 8px; padding: 16px; margin-bottom: 16px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  th, td { text-align: left; padding: 8px; border-bottom: 1px solid #eee; }
  th { font-weight: 600; color: #666; }
  .money { font-variant-numeric: tabular-nums; }
  .profit-pos { color: #2e7d32; font-weight: 600; }
  .profit-neg { color: #c62828; font-weight: 600; }
  form { display: flex; flex-direction: column; gap: 12px; }
  label { font-weight: 500; font-size: 0.9rem; }
  input, select { padding: 8px; border: 1px solid #ccc; border-radius: 4px; font-size: 1rem; }
  input:focus, select:focus { outline: none; border-color: #ff5a5f; }
  button, .btn { padding: 10px 16px; border: none; border-radius: 4px; font-size: 0.95rem;
                 cursor: pointer; text-decoration: none; display: inline-block; text-align: center; }
  .btn-primary { background: #ff5a5f; color: #fff; }
  .btn-primary:hover { background: #e04e52; }
  .btn-danger { background: #c62828; color: #fff; font-size: 0.8rem; padding: 4px 10px; }
  .btn-danger:hover { background: #a01c1c; }
  .btn-sm { font-size: 0.8rem; padding: 4px 10px; }
  .actions { display: flex; gap: 8px; margin-bottom: 16px; }
  .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }
  .stat { text-align: center; }
  .stat .value { font-size: 1.4rem; font-weight: 700; }
  .stat .label { font-size: 0.8rem; color: #666; }
  .empty { color: #999; font-style: italic; padding: 16px 0; }
  .flash { background: #e8f5e9; color: #2e7d32; padding: 10px 16px; border-radius: 4px;
           margin-bottom: 16px; }
  .flash-error { background: #ffebee; color: #c62828; }
  @media (max-width: 600px) {
    table { font-size: 0.8rem; }
    th, td { padding: 6px 4px; }
    .summary-grid { grid-template-columns: repeat(2, 1fr); }
  }
</style>
</head>
<body>
<nav>
  <div class="container">
    <a href="/" class="brand">Airbnb Tracker</a>
    <a href="/">Dashboard</a>
    <a href="/properties">Properties</a>
    <a href="/bookings">Bookings</a>
    <a href="/expenses">Expenses</a>
  </div>
</nav>
<div class="container">
  {% if flash_msg %}<div class="flash">{{ flash_msg }}</div>{% endif %}
  {% if flash_error %}<div class="flash flash-error">{{ flash_error }}</div>{% endif %}
  CONTENT_PLACEHOLDER
</div>
</body>
</html>"""


def _render(content, flash_msg="", flash_error=""):
    html = BASE_HTML.replace("CONTENT_PLACEHOLDER", content)
    return render_template_string(html, flash_msg=flash_msg, flash_error=flash_error)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    conn = _get_conn()
    try:
        rows, totals = models.overall_summary(conn)
        properties = models.list_properties(conn)

        prop_cards = ""
        for r in rows:
            profit_cls = "profit-pos" if r["net_profit"] >= 0 else "profit-neg"
            prop_cards += f"""
            <div class="card">
              <h3>{r['property']}</h3>
              <div class="summary-grid" style="margin-top:8px">
                <div class="stat"><div class="value">{_fmt_money(r['total_revenue'])}</div><div class="label">Revenue</div></div>
                <div class="stat"><div class="value">{_fmt_money(r['total_expenses'])}</div><div class="label">Expenses</div></div>
                <div class="stat"><div class="value {profit_cls}">{_fmt_money(r['net_profit'])}</div><div class="label">Profit</div></div>
                <div class="stat"><div class="value">{r['num_bookings']}</div><div class="label">Bookings</div></div>
              </div>
            </div>"""

        if not properties:
            prop_cards = '<p class="empty">No properties yet. <a href="/properties/add">Add your first property</a>.</p>'

        profit_cls = "profit-pos" if totals["profit"] >= 0 else "profit-neg"
        content = f"""
        <h1>Dashboard</h1>
        <div class="card">
          <h3>Overall Summary</h3>
          <div class="summary-grid" style="margin-top:8px">
            <div class="stat"><div class="value">{_fmt_money(totals['revenue'])}</div><div class="label">Revenue</div></div>
            <div class="stat"><div class="value">{_fmt_money(totals['expenses'])}</div><div class="label">Expenses</div></div>
            <div class="stat"><div class="value {profit_cls}">{_fmt_money(totals['profit'])}</div><div class="label">Profit</div></div>
            <div class="stat"><div class="value">{totals['nights']}</div><div class="label">Nights</div></div>
            <div class="stat"><div class="value">{totals['bookings']}</div><div class="label">Bookings</div></div>
          </div>
        </div>
        {prop_cards}
        """
        return _render(content)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

@app.route("/properties")
def properties_list():
    conn = _get_conn()
    try:
        props = models.list_properties(conn)
        if not props:
            rows_html = '<p class="empty">No properties yet.</p>'
        else:
            rows_html = "<table><tr><th>ID</th><th>Name</th><th>Address</th><th></th></tr>"
            for p in props:
                rows_html += f"""<tr>
                    <td>{p['id']}</td><td>{p['name']}</td><td>{p['address'] or ''}</td>
                    <td><form method="post" action="/properties/{p['id']}/delete"
                         onsubmit="return confirm('Delete this property and all its data?')">
                         <button class="btn-danger btn-sm">Delete</button></form></td>
                </tr>"""
            rows_html += "</table>"

        content = f"""
        <h1>Properties</h1>
        <div class="actions"><a href="/properties/add" class="btn btn-primary btn-sm">+ Add Property</a></div>
        <div class="card">{rows_html}</div>
        """
        return _render(content)
    finally:
        conn.close()


@app.route("/properties/add", methods=["GET", "POST"])
def properties_add():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        address = request.form.get("address", "").strip()
        if not name:
            return _render("""
            <h1>Add Property</h1>
            <div class="card"><form method="post">
              <label>Name *</label><input name="name" required>
              <label>Address</label><input name="address">
              <button class="btn btn-primary">Add Property</button>
            </form></div>""", flash_error="Name is required.")
        conn = _get_conn()
        try:
            models.add_property(conn, name, address)
        finally:
            conn.close()
        return redirect(url_for("properties_list"))

    content = """
    <h1>Add Property</h1>
    <div class="card"><form method="post">
      <label>Name *</label><input name="name" required>
      <label>Address</label><input name="address">
      <button class="btn btn-primary">Add Property</button>
    </form></div>"""
    return _render(content)


@app.route("/properties/<int:pid>/delete", methods=["POST"])
def properties_delete(pid):
    conn = _get_conn()
    try:
        models.delete_property(conn, pid)
    finally:
        conn.close()
    return redirect(url_for("properties_list"))


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------

@app.route("/bookings")
def bookings_list():
    conn = _get_conn()
    try:
        prop_filter = request.args.get("property_id", type=int)
        bookings = models.list_bookings(conn, prop_filter)
        properties = models.list_properties(conn)

        filter_opts = '<option value="">All Properties</option>'
        for p in properties:
            sel = "selected" if prop_filter == p["id"] else ""
            filter_opts += f'<option value="{p["id"]}" {sel}>{p["name"]}</option>'

        if not bookings:
            rows_html = '<p class="empty">No bookings yet.</p>'
        else:
            rows_html = """<table><tr><th>ID</th><th>Property</th><th>Guest</th>
                <th>Check-in</th><th>Check-out</th><th>Nights</th><th>Revenue</th><th></th></tr>"""
            prop_map = {p["id"]: p["name"] for p in properties}
            for b in bookings:
                rows_html += f"""<tr>
                    <td>{b['id']}</td><td>{prop_map.get(b['property_id'], b['property_id'])}</td>
                    <td>{b['guest_name'] or ''}</td><td>{b['check_in']}</td><td>{b['check_out']}</td>
                    <td>{b['nights']}</td><td class="money">{_fmt_money(b['total_revenue'])}</td>
                    <td><form method="post" action="/bookings/{b['id']}/delete"
                         onsubmit="return confirm('Delete this booking?')">
                         <button class="btn-danger btn-sm">Delete</button></form></td>
                </tr>"""
            rows_html += "</table>"

        content = f"""
        <h1>Bookings</h1>
        <div class="actions">
          <a href="/bookings/add" class="btn btn-primary btn-sm">+ Add Booking</a>
          <form method="get" style="flex-direction:row;display:flex;gap:8px;align-items:center">
            <select name="property_id" onchange="this.form.submit()">{filter_opts}</select>
          </form>
        </div>
        <div class="card">{rows_html}</div>
        """
        return _render(content)
    finally:
        conn.close()


@app.route("/bookings/add", methods=["GET", "POST"])
def bookings_add():
    conn = _get_conn()
    try:
        properties = models.list_properties(conn)
        if request.method == "POST":
            try:
                models.add_booking(
                    conn,
                    int(request.form["property_id"]),
                    request.form.get("guest_name", "").strip(),
                    request.form["check_in"],
                    request.form["check_out"],
                    float(request.form["nightly_rate"]),
                    float(request.form.get("platform_fee") or 0),
                )
            except (ValueError, KeyError) as e:
                return _render(_booking_form(properties), flash_error=str(e))
            return redirect(url_for("bookings_list"))

        return _render(_booking_form(properties))
    finally:
        conn.close()


def _booking_form(properties):
    opts = "".join(f'<option value="{p["id"]}">{p["name"]}</option>' for p in properties)
    return f"""
    <h1>Add Booking</h1>
    <div class="card"><form method="post">
      <label>Property *</label><select name="property_id" required>{opts}</select>
      <label>Guest Name</label><input name="guest_name">
      <label>Check-in *</label><input name="check_in" type="date" required>
      <label>Check-out *</label><input name="check_out" type="date" required>
      <label>Nightly Rate ($) *</label><input name="nightly_rate" type="number" step="0.01" required>
      <label>Platform Fee ($)</label><input name="platform_fee" type="number" step="0.01" value="0">
      <button class="btn btn-primary">Add Booking</button>
    </form></div>"""


@app.route("/bookings/<int:bid>/delete", methods=["POST"])
def bookings_delete(bid):
    conn = _get_conn()
    try:
        models.delete_booking(conn, bid)
    finally:
        conn.close()
    return redirect(url_for("bookings_list"))


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------

@app.route("/expenses")
def expenses_list():
    conn = _get_conn()
    try:
        prop_filter = request.args.get("property_id", type=int)
        expenses = models.list_expenses(conn, prop_filter)
        properties = models.list_properties(conn)

        filter_opts = '<option value="">All Properties</option>'
        for p in properties:
            sel = "selected" if prop_filter == p["id"] else ""
            filter_opts += f'<option value="{p["id"]}" {sel}>{p["name"]}</option>'

        if not expenses:
            rows_html = '<p class="empty">No expenses yet.</p>'
        else:
            rows_html = """<table><tr><th>ID</th><th>Property</th><th>Category</th>
                <th>Description</th><th>Amount</th><th>Date</th><th></th></tr>"""
            prop_map = {p["id"]: p["name"] for p in properties}
            for e in expenses:
                rows_html += f"""<tr>
                    <td>{e['id']}</td><td>{prop_map.get(e['property_id'], e['property_id'])}</td>
                    <td>{e['category']}</td><td>{e['description'] or ''}</td>
                    <td class="money">{_fmt_money(e['amount'])}</td><td>{e['date']}</td>
                    <td><form method="post" action="/expenses/{e['id']}/delete"
                         onsubmit="return confirm('Delete this expense?')">
                         <button class="btn-danger btn-sm">Delete</button></form></td>
                </tr>"""
            rows_html += "</table>"

        content = f"""
        <h1>Expenses</h1>
        <div class="actions">
          <a href="/expenses/add" class="btn btn-primary btn-sm">+ Add Expense</a>
          <form method="get" style="flex-direction:row;display:flex;gap:8px;align-items:center">
            <select name="property_id" onchange="this.form.submit()">{filter_opts}</select>
          </form>
        </div>
        <div class="card">{rows_html}</div>
        """
        return _render(content)
    finally:
        conn.close()


@app.route("/expenses/add", methods=["GET", "POST"])
def expenses_add():
    conn = _get_conn()
    try:
        properties = models.list_properties(conn)
        if request.method == "POST":
            try:
                category = request.form["category"]
                if category not in models.EXPENSE_CATEGORIES:
                    raise ValueError(f"Invalid category: {category}")
                models.add_expense(
                    conn,
                    int(request.form["property_id"]),
                    category,
                    float(request.form["amount"]),
                    request.form["date"],
                    request.form.get("description", "").strip(),
                )
            except (ValueError, KeyError) as e:
                return _render(_expense_form(properties), flash_error=str(e))
            return redirect(url_for("expenses_list"))

        return _render(_expense_form(properties))
    finally:
        conn.close()


def _expense_form(properties):
    prop_opts = "".join(f'<option value="{p["id"]}">{p["name"]}</option>' for p in properties)
    cat_opts = "".join(f'<option value="{c}">{c.replace("_", " ").title()}</option>'
                       for c in models.EXPENSE_CATEGORIES)
    return f"""
    <h1>Add Expense</h1>
    <div class="card"><form method="post">
      <label>Property *</label><select name="property_id" required>{prop_opts}</select>
      <label>Category *</label><select name="category" required>{cat_opts}</select>
      <label>Amount ($) *</label><input name="amount" type="number" step="0.01" required>
      <label>Date *</label><input name="date" type="date" required>
      <label>Description</label><input name="description">
      <button class="btn btn-primary">Add Expense</button>
    </form></div>"""


@app.route("/expenses/<int:eid>/delete", methods=["POST"])
def expenses_delete(eid):
    conn = _get_conn()
    try:
        models.delete_expense(conn, eid)
    finally:
        conn.close()
    return redirect(url_for("expenses_list"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Run the web server."""
    import argparse
    parser = argparse.ArgumentParser(description="Airbnb Tracker Web UI")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to (default: 5000)")
    parser.add_argument("--db", help="Path to SQLite database file")
    args = parser.parse_args()

    global DB_PATH
    if args.db:
        DB_PATH = args.db

    print(f"Starting Airbnb Tracker at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=True)


if __name__ == "__main__":
    main()
