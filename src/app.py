from datetime import date
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session,
)

from database import init_db, get_db
from matching_engine import compute_matches

app = Flask(__name__)
app.secret_key = "medrescue-secret-key-2024"

with app.app_context():
    init_db()


# ── Context processor: inject unread notification count into every template ──

@app.context_processor
def inject_notification_count():
    fac_id = session.get("facility_id")
    if not fac_id:
        return {"unread_count": 0, "bell_notifications": []}
    conn = get_db()
    unread_count = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE facility_id=? AND is_read=0",
        (fac_id,),
    ).fetchone()[0]
    bell_notifications = conn.execute(
        """SELECT n.id, n.channel, n.message, n.sent_at, n.is_read,
                  m.medicine_name
           FROM   notifications n
           JOIN   medicines m ON m.id = n.medicine_id
           WHERE  n.facility_id = ?
           ORDER  BY n.id DESC
           LIMIT  8""",
        (fac_id,),
    ).fetchall()
    conn.close()
    return {
        "unread_count":      unread_count,
        "bell_notifications": [dict(r) for r in bell_notifications],
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "facility_id" not in session:
            flash("Please log in to access that page.", "error")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated


# ── Pricing helper ────────────────────────────────────────────────────────────

MEDICINE_TYPES = ["injectable", "tablet", "capsule", "syrup", "other"]


def _transportation_charge(quantity: int) -> float:
    if quantity <= 50:
        return 50.0
    if quantity <= 200:
        return 100.0
    return 200.0


def _pricing(price_per_unit: float, quantity: int) -> dict:
    """Return a price-breakdown dict for a given unit price and quantity."""
    markup       = round(price_per_unit * 0.05, 2)
    markup_price = round(price_per_unit + markup, 2)
    transport    = _transportation_charge(quantity)
    total        = round(markup_price * quantity + transport, 2)
    return {
        "base_price":            round(price_per_unit, 2),
        "markup":                markup,
        "markup_price":          markup_price,
        "transportation_charge": transport,
        "quantity":              quantity,
        "total_amount":          total,
    }


def _days_until(expiry_str: str) -> int:
    try:
        return (date.fromisoformat(expiry_str) - date.today()).days
    except ValueError:
        return 9999


def _expiry_class(days: int, medicine_type: str = "other") -> str:
    """Return CSS class based on days until expiry and medicine type."""
    mtype = (medicine_type or "other").lower()
    if mtype == "injectable":
        if days <= 3:   return "expiry-red"
        if days <= 7:   return "expiry-orange"
        if days <= 15:  return "expiry-yellow"
        return "expiry-green"
    elif mtype in ("tablet", "capsule"):
        if days <= 10:  return "expiry-red"
        if days <= 20:  return "expiry-orange"
        if days <= 30:  return "expiry-yellow"
        return "expiry-green"
    else:  # syrup / other — original thresholds
        if days <= 7:   return "expiry-red"
        if days <= 15:  return "expiry-orange"
        if days <= 30:  return "expiry-yellow"
        return "expiry-green"


def _notify_medicines(conn, fac_id: int, medicines: list) -> None:
    """Simulate SMS/email notifications for urgent medicines.

    Inserts into the notifications table when a medicine is red/orange/yellow.
    Skips if an identical (facility_id, medicine_id, channel) row already exists
    for today to avoid duplicate alerts on every page load.
    """
    today_iso = date.today().isoformat()
    for m in medicines:
        med_id = m.get("id")
        css    = m.get("expiry_class", "expiry-green")
        name   = m.get("medicine_name", "")
        days   = m.get("days_left", 9999)

        if css == "expiry-red":
            channel = "sms"
            message = (
                f"URGENT: {name} expires in {days} day{'s' if days != 1 else ''}."
                f" Please act quickly."
            )
        elif css in ("expiry-orange", "expiry-yellow"):
            channel = "email"
            message = (
                f"REMINDER: {name} expires in {days} days."
                f" Consider redistributing soon."
            )
        else:
            continue  # green — no notification needed

        # Avoid duplicate notifications for the same medicine+channel today
        existing = conn.execute(
            """SELECT id FROM notifications
               WHERE facility_id=? AND medicine_id=? AND channel=?
                 AND sent_at LIKE ?""",
            (fac_id, med_id, channel, today_iso + "%"),
        ).fetchone()
        if existing:
            continue

        conn.execute(
            """INSERT INTO notifications
               (facility_id, medicine_id, channel, message, sent_at, is_read)
               VALUES (?,?,?,?,?,0)""",
            (fac_id, med_id, channel, message,
             date.today().isoformat() + " (simulated)"),
        )
    conn.commit()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def home():
    conn = get_db()

    # ---- Handle login POST ----
    if request.method == "POST":
        role     = request.form.get("role", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not all([role, username, password]):
            flash("Please fill in all login fields.", "error")
            conn.close()
            return render_template("home.html", logged_in=False)

        fac = conn.execute(
            """SELECT id, name FROM facilities
               WHERE type = ? AND username = ? AND password = ?""",
            (role, username, password),
        ).fetchone()

        if not fac:
            flash("Invalid role, username, or password.", "error")
            conn.close()
            return render_template("home.html", logged_in=False)

        session["facility_id"]   = fac["id"]
        session["facility_name"] = fac["name"]
        conn.close()
        return redirect(url_for("home"))

    # ---- Not logged in: show login page ----
    if "facility_id" not in session:
        conn.close()
        return render_template("home.html", logged_in=False)

    # ---- Logged in: build dashboard ----
    fac_id = session["facility_id"]

    own_meds_raw = conn.execute(
        """SELECT * FROM medicines WHERE facility_id = ? ORDER BY expiry_date ASC""",
        (fac_id,),
    ).fetchall()

    own_meds = []
    expiring_count = 0
    for m in own_meds_raw:
        days  = _days_until(m["expiry_date"])
        mtype = m["medicine_type"] if "medicine_type" in m.keys() else "other"
        cls   = _expiry_class(days, mtype)
        if cls != "expiry-green":
            expiring_count += 1
        own_meds.append({
            **dict(m),
            "days_left":    days,
            "expiry_class": cls,
        })

    # Simulate notifications for urgent stock
    _notify_medicines(conn, fac_id, own_meds)

    total_meds = len(own_meds)

    all_matches = compute_matches(conn)
    my_matches = [
        m for m in all_matches
        if m["from_facility_id"] == fac_id or m["to_facility_id"] == fac_id
    ]
    pending_matches = len(my_matches)

    completed_transfers = conn.execute(
        """SELECT COUNT(*) FROM transfers
           WHERE from_facility_id = ? OR to_facility_id = ?""",
        (fac_id, fac_id),
    ).fetchone()[0]

    conn.close()

    return render_template(
        "home.html",
        logged_in=True,
        facility_name=session["facility_name"],
        own_meds=own_meds,
        total_meds=total_meds,
        expiring_count=expiring_count,
        pending_matches=pending_matches,
        completed_transfers=completed_transfers,
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/add-medicine", methods=["GET", "POST"])
@login_required
def add_medicine():
    if request.method == "POST":
        medicine_name = request.form["medicine_name"].strip()
        quantity      = request.form["quantity"]
        mfg_date      = request.form["manufacture_date"]
        exp_date      = request.form["expiry_date"]
        needed_qty    = request.form.get("needed_quantity", "0") or "0"

        if not all([medicine_name, quantity, mfg_date, exp_date]):
            flash("All fields except Needed Quantity are required.", "error")
            return redirect(url_for("add_medicine"))

        medicine_type  = request.form.get("medicine_type", "other")
        price_per_unit = request.form.get("price_per_unit", "0") or "0"

        conn = get_db()
        conn.execute(
            """INSERT INTO medicines
               (facility_id, medicine_name, quantity, manufacture_date,
                expiry_date, needed_quantity, date_added, medicine_type,
                price_per_unit)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                session["facility_id"], medicine_name,
                int(quantity), mfg_date, exp_date, int(needed_qty),
                date.today().isoformat(), medicine_type,
                float(price_per_unit),
            ),
        )
        conn.commit()
        conn.close()
        flash(f"'{medicine_name}' added to your inventory.", "success")
        return redirect(url_for("home"))

    return render_template("add_medicine.html")


@app.route("/search")
@login_required
def search():
    query   = request.args.get("q", "").strip()
    results = []

    if query:
        conn = get_db()
        raw = conn.execute(
            """
            SELECT m.id, m.medicine_name, m.quantity, m.expiry_date,
                   m.date_added, m.medicine_type, m.price_per_unit,
                   m.facility_id AS med_facility_id,
                   f.id   AS facility_id,
                   f.name AS facility_name,
                   f.type AS facility_type,
                   f.location_area,
                   f.contact_number
            FROM   medicines m
            JOIN   facilities f ON f.id = m.facility_id
            WHERE  LOWER(m.medicine_name) LIKE LOWER(?)
              AND  m.quantity > 0
            ORDER  BY m.expiry_date ASC
            """,
            (f"%{query}%",),
        ).fetchall()
        conn.close()

        results = []
        for r in raw:
            days  = _days_until(r["expiry_date"])
            mtype = r["medicine_type"] or "other"
            qty   = r["quantity"]
            price = r["price_per_unit"] or 0.0
            results.append({
                **dict(r),
                "days_left":    days,
                "expiry_class": _expiry_class(days, mtype),
                "pricing":      _pricing(price, qty),
            })

    return render_template("search.html", query=query, results=results)


@app.route("/profile")
@login_required
def profile():
    fac_id = session["facility_id"]
    conn = get_db()

    facility = conn.execute(
        "SELECT * FROM facilities WHERE id = ?", (fac_id,)
    ).fetchone()

    total_medicines = conn.execute(
        "SELECT COUNT(*) FROM medicines WHERE facility_id = ?", (fac_id,)
    ).fetchone()[0]

    total_transfers = conn.execute(
        """SELECT COUNT(*) FROM transfers
           WHERE from_facility_id = ? OR to_facility_id = ?""",
        (fac_id, fac_id),
    ).fetchone()[0]

    notifications = conn.execute(
        """SELECT n.id, n.channel, n.message, n.sent_at, n.is_read,
                  m.medicine_name
           FROM   notifications n
           JOIN   medicines m ON m.id = n.medicine_id
           WHERE  n.facility_id = ?
           ORDER  BY n.id DESC
           LIMIT  20""",
        (fac_id,),
    ).fetchall()

    orders = conn.execute(
        """SELECT o.id, o.quantity, o.unit_price, o.transportation_charge,
                  o.total_amount, o.payment_status, o.created_at,
                  m.medicine_name,
                  sf.name AS source_facility_name
           FROM   orders o
           JOIN   medicines m   ON m.id   = o.medicine_id
           JOIN   facilities sf ON sf.id  = o.source_facility_id
           WHERE  o.requester_facility_id = ?
           ORDER  BY o.id DESC
           LIMIT  30""",
        (fac_id,),
    ).fetchall()

    conn.close()
    return render_template(
        "profile.html",
        facility=facility,
        total_medicines=total_medicines,
        total_transfers=total_transfers,
        notifications=notifications,
        orders=orders,
    )


@app.route("/place-order", methods=["POST"])
@login_required
def place_order():
    medicine_id        = int(request.form["medicine_id"])
    source_facility_id = int(request.form["source_facility_id"])
    quantity           = int(request.form["quantity"])
    requester_id       = session["facility_id"]

    if requester_id == source_facility_id:
        flash("You cannot place an order from your own facility.", "error")
        return redirect(request.referrer or url_for("matches"))

    conn = get_db()
    med = conn.execute(
        "SELECT medicine_name, price_per_unit, quantity FROM medicines WHERE id = ?",
        (medicine_id,),
    ).fetchone()

    if not med:
        flash("Medicine not found.", "error")
        conn.close()
        return redirect(request.referrer or url_for("matches"))

    if med["quantity"] < quantity:
        flash(
            f"Insufficient stock: only {med['quantity']} units available.",
            "error",
        )
        conn.close()
        return redirect(request.referrer or url_for("matches"))

    p = _pricing(med["price_per_unit"] or 0.0, quantity)

    conn.execute(
        """INSERT INTO orders
           (requester_facility_id, source_facility_id, medicine_id,
            quantity, unit_price, transportation_charge, total_amount,
            payment_status, created_at)
           VALUES (?,?,?,?,?,?,?,'pending',?)""",
        (requester_id, source_facility_id, medicine_id,
         quantity, p["markup_price"], p["transportation_charge"],
         p["total_amount"], date.today().isoformat()),
    )
    conn.commit()
    conn.close()
    flash(
        f"Order placed for {quantity} units of '{med['medicine_name']}'. "
        f"Total: ₹{p['total_amount']:.2f}. Go to your Profile to pay.",
        "success",
    )
    return redirect(request.referrer or url_for("matches"))


@app.route("/pay-order/<int:order_id>", methods=["POST"])
@login_required
def pay_order(order_id):
    fac_id = session["facility_id"]
    conn = get_db()

    order = conn.execute(
        """SELECT o.*, m.medicine_name, m.id AS med_id
           FROM orders o
           JOIN medicines m ON m.id = o.medicine_id
           WHERE o.id = ? AND o.requester_facility_id = ?""",
        (order_id, fac_id),
    ).fetchone()

    if not order:
        flash("Order not found or access denied.", "error")
        conn.close()
        return redirect(url_for("profile"))

    if order["payment_status"] == "paid":
        flash("This order has already been paid.", "error")
        conn.close()
        return redirect(url_for("profile"))

    # Simulate payment — mark as paid
    conn.execute(
        "UPDATE orders SET payment_status='paid' WHERE id=?",
        (order_id,),
    )

    # Payment confirmation notifications (both SMS and email simulated)
    msg_sms   = (
        f"Payment confirmed for {order['medicine_name']} - "
        f"Order #{order_id}, total ₹{order['total_amount']:.2f}."
    )
    msg_email = (
        f"Your order #{order_id} for {order['medicine_name']} "
        f"(₹{order['total_amount']:.2f}) has been paid successfully."
    )
    now = date.today().isoformat() + " (simulated)"
    for channel, msg in [("sms", msg_sms), ("email", msg_email)]:
        conn.execute(
            """INSERT INTO notifications
               (facility_id, medicine_id, channel, message, sent_at)
               VALUES (?,?,?,?,?)""",
            (fac_id, order["med_id"], channel, msg, now),
        )

    conn.commit()
    conn.close()
    flash(
        f"Payment confirmed for Order #{order_id}! "
        f"Total ₹{order['total_amount']:.2f} paid.",
        "success",
    )
    return redirect(url_for("profile"))


@app.route("/add-facility", methods=["GET", "POST"])
def add_facility():
    if request.method == "POST":
        name  = request.form["name"].strip()
        ftype = request.form["type"]
        area  = request.form["location_area"].strip()

        if not name or not area:
            flash("All fields are required.", "error")
            return redirect(url_for("add_facility"))

        conn = get_db()
        conn.execute(
            "INSERT INTO facilities (name, type, location_area) VALUES (?,?,?)",
            (name, ftype, area),
        )
        conn.commit()
        conn.close()
        flash(f"Facility '{name}' registered. You can now log in.", "success")
        return redirect(url_for("home"))

    return render_template("add_facility.html")


@app.route("/matches")
@login_required
def matches():
    tab = request.args.get("tab", "mine")
    fac_id = session["facility_id"]

    conn = get_db()
    all_matches_raw = compute_matches(conn)
    conn.close()

    # Attach pricing to each match
    all_matches = []
    for m in all_matches_raw:
        price = m.get("price_per_unit", 0.0) or 0.0
        qty   = m.get("transfer_qty", 1)
        all_matches.append({**m, "pricing": _pricing(price, qty)})

    my_matches = [
        m for m in all_matches
        if m["from_facility_id"] == fac_id or m["to_facility_id"] == fac_id
    ]

    return render_template(
        "matches.html",
        tab=tab,
        my_matches=my_matches,
        all_matches=all_matches,
        facility_id=fac_id,
    )


@app.route("/mark-notifications-read", methods=["POST"])
@login_required
def mark_notifications_read():
    fac_id = session["facility_id"]
    conn = get_db()
    conn.execute(
        "UPDATE notifications SET is_read=1 WHERE facility_id=? AND is_read=0",
        (fac_id,),
    )
    conn.commit()
    conn.close()
    return ("", 204)  # No Content — called via fetch


@app.route("/approve-transfer", methods=["POST"])
@login_required
def approve_transfer():
    medicine_id      = int(request.form["medicine_id"])
    from_facility_id = int(request.form["from_facility_id"])
    to_facility_id   = int(request.form["to_facility_id"])
    transfer_qty     = int(request.form["transfer_qty"])

    conn = get_db()

    donor = conn.execute(
        "SELECT * FROM medicines WHERE id = ? AND facility_id = ?",
        (medicine_id, from_facility_id),
    ).fetchone()

    if not donor:
        flash("Transfer failed: donor record not found.", "error")
        conn.close()
        return redirect(url_for("matches"))

    if donor["quantity"] < transfer_qty:
        flash(
            f"Transfer failed: only {donor['quantity']} units available "
            f"({transfer_qty} requested).",
            "error",
        )
        conn.close()
        return redirect(url_for("matches"))

    # Deduct from donor
    conn.execute(
        "UPDATE medicines SET quantity = quantity - ? WHERE id = ?",
        (transfer_qty, medicine_id),
    )

    # Credit receiver (update existing record or create new one)
    med_name = donor["medicine_name"]
    recv_med = conn.execute(
        """SELECT id FROM medicines
           WHERE facility_id = ? AND LOWER(medicine_name) = LOWER(?)
           LIMIT 1""",
        (to_facility_id, med_name),
    ).fetchone()

    if recv_med:
        conn.execute(
            "UPDATE medicines SET quantity = quantity + ? WHERE id = ?",
            (transfer_qty, recv_med["id"]),
        )
    else:
        conn.execute(
            """INSERT INTO medicines
               (facility_id, medicine_name, quantity, manufacture_date,
                expiry_date, needed_quantity)
               VALUES (?,?,?,?,?,0)""",
            (to_facility_id, med_name, transfer_qty,
             donor["manufacture_date"], donor["expiry_date"]),
        )

    # Log transfer
    conn.execute(
        """INSERT INTO transfers
           (medicine_id, from_facility_id, to_facility_id, quantity, transfer_date)
           VALUES (?,?,?,?,?)""",
        (medicine_id, from_facility_id, to_facility_id,
         transfer_qty, date.today().isoformat()),
    )

    conn.commit()
    conn.close()
    flash(
        f"Transfer of {transfer_qty} units of '{med_name}' approved and logged.",
        "success",
    )
    return redirect(url_for("matches"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
