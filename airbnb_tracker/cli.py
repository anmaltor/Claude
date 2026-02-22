"""Command-line interface for the Airbnb tracker."""

import argparse
import sys

from . import db, models


def _fmt_money(amount):
    """Format a number as currency."""
    return f"${amount:,.2f}"


def _table(headers, rows):
    """Print a simple text table."""
    if not rows:
        print("  (no data)")
        return
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val)))
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*("-" * w for w in widths)))
    for row in rows:
        print(fmt.format(*row))


# ---------------------------------------------------------------------------
# Property commands
# ---------------------------------------------------------------------------

def cmd_add_property(args, conn):
    pid = models.add_property(conn, args.name, args.address or "")
    print(f"Property added (id={pid}): {args.name}")


def cmd_list_properties(args, conn):
    props = models.list_properties(conn)
    rows = [(p["id"], p["name"], p["address"] or "") for p in props]
    _table(["ID", "Name", "Address"], rows)


def cmd_delete_property(args, conn):
    prop = models.get_property(conn, args.id)
    if not prop:
        print(f"Property {args.id} not found.")
        return
    models.delete_property(conn, args.id)
    print(f"Deleted property {args.id} ({prop['name']}) and all its bookings/expenses.")


# ---------------------------------------------------------------------------
# Booking commands
# ---------------------------------------------------------------------------

def cmd_add_booking(args, conn):
    prop = models.get_property(conn, args.property_id)
    if not prop:
        print(f"Property {args.property_id} not found.")
        return
    try:
        bid = models.add_booking(
            conn, args.property_id, args.guest, args.check_in,
            args.check_out, args.rate, args.fee or 0,
        )
    except ValueError as e:
        print(f"Error: {e}")
        return
    print(f"Booking added (id={bid}) for {prop['name']}")


def cmd_list_bookings(args, conn):
    bookings = models.list_bookings(conn, getattr(args, "property_id", None))
    rows = [
        (b["id"], b["property_id"], b["guest_name"] or "",
         b["check_in"], b["check_out"], b["nights"],
         _fmt_money(b["nightly_rate"]), _fmt_money(b["platform_fee"]),
         _fmt_money(b["total_revenue"]))
        for b in bookings
    ]
    _table(["ID", "Prop", "Guest", "Check-in", "Check-out",
            "Nights", "Rate", "Fee", "Revenue"], rows)


def cmd_delete_booking(args, conn):
    models.delete_booking(conn, args.id)
    print(f"Deleted booking {args.id}.")


# ---------------------------------------------------------------------------
# Expense commands
# ---------------------------------------------------------------------------

def cmd_add_expense(args, conn):
    prop = models.get_property(conn, args.property_id)
    if not prop:
        print(f"Property {args.property_id} not found.")
        return
    eid = models.add_expense(
        conn, args.property_id, args.category, args.amount,
        args.date, args.description or "",
    )
    print(f"Expense added (id={eid}) for {prop['name']}: "
          f"{args.category} {_fmt_money(args.amount)}")


def cmd_list_expenses(args, conn):
    expenses = models.list_expenses(conn, getattr(args, "property_id", None))
    rows = [
        (e["id"], e["property_id"], e["category"],
         e["description"] or "", _fmt_money(e["amount"]), e["date"])
        for e in expenses
    ]
    _table(["ID", "Prop", "Category", "Description", "Amount", "Date"], rows)


def cmd_delete_expense(args, conn):
    models.delete_expense(conn, args.id)
    print(f"Deleted expense {args.id}.")


# ---------------------------------------------------------------------------
# Report commands
# ---------------------------------------------------------------------------

def cmd_summary(args, conn):
    prop_id = getattr(args, "property_id", None)
    start = getattr(args, "start", None)
    end = getattr(args, "end", None)

    if prop_id:
        prop = models.get_property(conn, prop_id)
        if not prop:
            print(f"Property {prop_id} not found.")
            return
        s = models.property_summary(conn, prop_id, start, end)
        print(f"\n=== {prop['name']} ===")
        _print_summary(s)
    else:
        rows, totals = models.overall_summary(conn, start, end)
        for r in rows:
            print(f"\n=== {r['property']} ===")
            _print_summary(r)
        print("\n=== TOTALS ===")
        print(f"  Revenue:  {_fmt_money(totals['revenue'])}")
        print(f"  Expenses: {_fmt_money(totals['expenses'])}")
        print(f"  Profit:   {_fmt_money(totals['profit'])}")
        print(f"  Nights:   {totals['nights']}")
        print(f"  Bookings: {totals['bookings']}")


def _print_summary(s):
    print(f"  Revenue:  {_fmt_money(s['total_revenue'])}  "
          f"({s['num_bookings']} bookings, {s['total_nights']} nights)")
    print(f"  Expenses: {_fmt_money(s['total_expenses'])}")
    print(f"  Profit:   {_fmt_money(s['net_profit'])}")
    if s.get("expenses_by_category"):
        print("  Expense breakdown:")
        for cat, total in s["expenses_by_category"]:
            print(f"    {cat:<15} {_fmt_money(total)}")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="airbnb-tracker",
        description="Track Airbnb revenue and costs",
    )
    parser.add_argument("--db", help="Path to SQLite database file")
    sub = parser.add_subparsers(dest="command")

    # -- property -----------------------------------------------------------
    p_add = sub.add_parser("add-property", help="Add a property")
    p_add.add_argument("name", help="Property name")
    p_add.add_argument("--address", help="Property address")

    sub.add_parser("list-properties", help="List all properties")

    p_del = sub.add_parser("delete-property", help="Delete a property")
    p_del.add_argument("id", type=int, help="Property ID")

    # -- booking ------------------------------------------------------------
    b_add = sub.add_parser("add-booking", help="Add a booking")
    b_add.add_argument("property_id", type=int, help="Property ID")
    b_add.add_argument("guest", help="Guest name")
    b_add.add_argument("check_in", help="Check-in date (YYYY-MM-DD)")
    b_add.add_argument("check_out", help="Check-out date (YYYY-MM-DD)")
    b_add.add_argument("rate", type=float, help="Nightly rate")
    b_add.add_argument("--fee", type=float, default=0, help="Platform fee")

    b_list = sub.add_parser("list-bookings", help="List bookings")
    b_list.add_argument("--property-id", type=int, help="Filter by property")

    b_del = sub.add_parser("delete-booking", help="Delete a booking")
    b_del.add_argument("id", type=int, help="Booking ID")

    # -- expense ------------------------------------------------------------
    e_add = sub.add_parser("add-expense", help="Add an expense")
    e_add.add_argument("property_id", type=int, help="Property ID")
    e_add.add_argument("category", choices=models.EXPENSE_CATEGORIES,
                       help="Expense category")
    e_add.add_argument("amount", type=float, help="Amount")
    e_add.add_argument("date", help="Date (YYYY-MM-DD)")
    e_add.add_argument("--description", help="Description")

    e_list = sub.add_parser("list-expenses", help="List expenses")
    e_list.add_argument("--property-id", type=int, help="Filter by property")

    e_del = sub.add_parser("delete-expense", help="Delete an expense")
    e_del.add_argument("id", type=int, help="Expense ID")

    # -- report -------------------------------------------------------------
    r = sub.add_parser("summary", help="Financial summary")
    r.add_argument("--property-id", type=int, help="Single property (omit for all)")
    r.add_argument("--start", help="Start date filter (YYYY-MM-DD)")
    r.add_argument("--end", help="End date filter (YYYY-MM-DD)")

    return parser


COMMAND_MAP = {
    "add-property": cmd_add_property,
    "list-properties": cmd_list_properties,
    "delete-property": cmd_delete_property,
    "add-booking": cmd_add_booking,
    "list-bookings": cmd_list_bookings,
    "delete-booking": cmd_delete_booking,
    "add-expense": cmd_add_expense,
    "list-expenses": cmd_list_expenses,
    "delete-expense": cmd_delete_expense,
    "summary": cmd_summary,
}


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    conn = db.get_connection(args.db)
    db.init_db(conn)

    try:
        COMMAND_MAP[args.command](args, conn)
    finally:
        conn.close()
