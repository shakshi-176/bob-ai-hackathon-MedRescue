import sqlite3
import os
from datetime import date, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "medrescue.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS facilities (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT NOT NULL,
            type           TEXT NOT NULL CHECK(type IN ('pharmacy','hospital')),
            location_area  TEXT NOT NULL,
            contact_number TEXT NOT NULL DEFAULT '',
            username       TEXT NOT NULL DEFAULT '',
            password       TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS medicines (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            facility_id      INTEGER NOT NULL REFERENCES facilities(id),
            medicine_name    TEXT NOT NULL,
            quantity         INTEGER NOT NULL DEFAULT 0,
            manufacture_date TEXT NOT NULL,
            expiry_date      TEXT NOT NULL,
            needed_quantity  INTEGER NOT NULL DEFAULT 0,
            date_added       TEXT NOT NULL DEFAULT '',
            medicine_type    TEXT NOT NULL DEFAULT 'other',
            price_per_unit   REAL NOT NULL DEFAULT 0.0
        );

        CREATE TABLE IF NOT EXISTS transfers (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_id      INTEGER NOT NULL REFERENCES medicines(id),
            from_facility_id INTEGER NOT NULL REFERENCES facilities(id),
            to_facility_id   INTEGER NOT NULL REFERENCES facilities(id),
            quantity         INTEGER NOT NULL,
            transfer_date    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            facility_id INTEGER NOT NULL REFERENCES facilities(id),
            medicine_id INTEGER NOT NULL REFERENCES medicines(id),
            channel     TEXT NOT NULL CHECK(channel IN ('sms','email')),
            message     TEXT NOT NULL,
            sent_at     TEXT NOT NULL,
            is_read     INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS orders (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_facility_id INTEGER NOT NULL REFERENCES facilities(id),
            source_facility_id    INTEGER NOT NULL REFERENCES facilities(id),
            medicine_id           INTEGER NOT NULL REFERENCES medicines(id),
            quantity              INTEGER NOT NULL,
            unit_price            REAL NOT NULL,
            transportation_charge REAL NOT NULL,
            total_amount          REAL NOT NULL,
            payment_status        TEXT NOT NULL DEFAULT 'pending'
                                      CHECK(payment_status IN ('pending','paid')),
            created_at            TEXT NOT NULL
        );
    """)
    conn.commit()

    # Add new columns to existing DBs (safe to run on every start)
    _migrate(cur)
    conn.commit()

    row = cur.execute("SELECT COUNT(*) FROM facilities").fetchone()
    if row[0] == 0:
        _seed(cur)
        conn.commit()

    conn.close()


def _migrate(cur):
    """Add columns introduced after the initial schema (idempotent)."""
    existing_fac = {r[1] for r in cur.execute("PRAGMA table_info(facilities)").fetchall()}
    if "contact_number" not in existing_fac:
        cur.execute("ALTER TABLE facilities ADD COLUMN contact_number TEXT NOT NULL DEFAULT ''")
    if "username" not in existing_fac:
        cur.execute("ALTER TABLE facilities ADD COLUMN username TEXT NOT NULL DEFAULT ''")
    if "password" not in existing_fac:
        cur.execute("ALTER TABLE facilities ADD COLUMN password TEXT NOT NULL DEFAULT ''")

    existing_med = {r[1] for r in cur.execute("PRAGMA table_info(medicines)").fetchall()}
    if "date_added" not in existing_med:
        cur.execute("ALTER TABLE medicines ADD COLUMN date_added TEXT NOT NULL DEFAULT ''")
    if "medicine_type" not in existing_med:
        cur.execute("ALTER TABLE medicines ADD COLUMN medicine_type TEXT NOT NULL DEFAULT 'other'")
    if "price_per_unit" not in existing_med:
        cur.execute("ALTER TABLE medicines ADD COLUMN price_per_unit REAL NOT NULL DEFAULT 0.0")

    existing_notif = {r[1] for r in cur.execute("PRAGMA table_info(notifications)").fetchall()}
    if "is_read" not in existing_notif:
        cur.execute("ALTER TABLE notifications ADD COLUMN is_read INTEGER NOT NULL DEFAULT 0")

    existing_tables = {r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    if "notifications" not in existing_tables:
        cur.execute("""
            CREATE TABLE notifications (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                facility_id INTEGER NOT NULL REFERENCES facilities(id),
                medicine_id INTEGER NOT NULL REFERENCES medicines(id),
                channel     TEXT NOT NULL CHECK(channel IN ('sms','email')),
                message     TEXT NOT NULL,
                sent_at     TEXT NOT NULL
            )
        """)
    if "orders" not in existing_tables:
        cur.execute("""
            CREATE TABLE orders (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                requester_facility_id INTEGER NOT NULL REFERENCES facilities(id),
                source_facility_id    INTEGER NOT NULL REFERENCES facilities(id),
                medicine_id           INTEGER NOT NULL REFERENCES medicines(id),
                quantity              INTEGER NOT NULL,
                unit_price            REAL NOT NULL,
                transportation_charge REAL NOT NULL,
                total_amount          REAL NOT NULL,
                payment_status        TEXT NOT NULL DEFAULT 'pending'
                                          CHECK(payment_status IN ('pending','paid')),
                created_at            TEXT NOT NULL
            )
        """)


def _seed(cur):
    # 6 facilities across 3 areas
    # (name, type, location_area, contact_number, username, password)
    facilities = [
        ("City General Hospital",  "hospital",  "Downtown",  "9876543210", "citygeneral",  "pass123"),
        ("Westside Pharmacy",      "pharmacy",  "West End",  "9876543211", "westsidepharm","pass123"),
        ("Northbrook Clinic",      "hospital",  "North",     "9876543212", "northbrook",   "pass123"),
        ("Central Care Pharmacy",  "pharmacy",  "Downtown",  "9876543213", "centralcare",  "pass123"),
        ("Eastside Medical Center","hospital",  "East Side", "9876543214", "eastsidemed",  "pass123"),
        ("Harbor Health Pharmacy", "pharmacy",  "East Side", "9876543215", "harborhealth", "pass123"),
    ]
    cur.executemany(
        """INSERT INTO facilities
           (name, type, location_area, contact_number, username, password)
           VALUES (?,?,?,?,?,?)""",
        facilities,
    )

    today = date.today()

    def d(offset):
        return (today + timedelta(days=offset)).isoformat()

    today_iso = today.isoformat()

    # (facility_id, name, qty, mfg_date, expiry_date, needed_qty, medicine_type, price)
    medicines = [
        # ── Critical (≤7 days) ──────────────────────────────
        (1, "Amoxicillin 500mg",      80,  d(-180), d(3),   0, "capsule",    12.50),
        (2, "Ibuprofen 400mg",        120, d(-200), d(5),   0, "tablet",      8.00),
        (3, "Paracetamol 500mg",      90,  d(-90),  d(6),   0, "tablet",      5.00),
        (5, "Ceftriaxone 1g",         40,  d(-60),  d(4),   0, "injectable", 85.00),

        # ── High urgency (8-15 days) ────────────────────────
        (4, "Metformin 500mg",        200, d(-150), d(10),  0, "tablet",     10.00),
        (1, "Ciprofloxacin 250mg",    90,  d(-100), d(12),  0, "tablet",     18.00),
        (6, "Ondansetron 4mg",        60,  d(-50),  d(14),  0, "injectable", 45.00),
        (2, "Salbutamol Inhaler",     35,  d(-45),  d(11),  0, "other",     120.00),

        # ── Medium urgency (16-30 days) ─────────────────────
        (5, "Atorvastatin 10mg",      150, d(-120), d(20),  0, "tablet",     22.00),
        (6, "Omeprazole 20mg",        75,  d(-80),  d(22),  0, "capsule",    15.00),
        (3, "Amlodipine 5mg",         110, d(-70),  d(25),  0, "tablet",     14.00),
        (1, "Losartan 50mg",          130, d(-65),  d(27),  0, "tablet",     20.00),
        (4, "Aspirin 75mg",           400, d(-60),  d(29),  0, "tablet",      4.00),
        (2, "Diclofenac 50mg",        85,  d(-55),  d(18),  0, "tablet",      9.00),

        # ── Safe stock (31-90 days) ──────────────────────────
        (5, "Lisinopril 10mg",        250, d(-30),  d(45),  0, "tablet",     16.00),
        (3, "Azithromycin 250mg",     180, d(-20),  d(60),  0, "tablet",     35.00),
        (6, "Pantoprazole 40mg",      120, d(-15),  d(75),  0, "tablet",     18.00),
        (2, "Cetirizine 10mg",        200, d(-10),  d(80),  0, "tablet",      7.00),

        # ── Long-dated stock (>90 days) ──────────────────────
        (4, "Metoprolol 50mg",        320, d(-10),  d(180), 0, "tablet",     12.00),
        (1, "Doxycycline 100mg",      140, d(-5),   d(200), 0, "capsule",    28.00),
        (3, "Gabapentin 300mg",       95,  d(-8),   d(150), 0, "capsule",    30.00),
        (5, "Sertraline 50mg",        75,  d(-12),  d(210), 0, "tablet",     25.00),
    ]
    cur.executemany(
        """INSERT INTO medicines
           (facility_id, medicine_name, quantity, manufacture_date,
            expiry_date, needed_quantity, date_added, medicine_type, price_per_unit)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        [(fid, nm, qty, mfg, exp, nq, today_iso, mtype, price)
         for fid, nm, qty, mfg, exp, nq, mtype, price in medicines],
    )

    # Needed-quantity rows — each at a DIFFERENT facility from the donor.
    # (facility_id, name, qty_on_hand, mfg, expiry, needed_qty, medicine_type, price)
    needed = [
        (2, "Amoxicillin 500mg",    10, d(-1), d(365), 60,  "capsule",     12.50),
        (4, "Amoxicillin 500mg",    5,  d(-1), d(365), 80,  "capsule",     12.50),
        (5, "Ibuprofen 400mg",      15, d(-1), d(365), 90,  "tablet",       8.00),
        (6, "Paracetamol 500mg",    20, d(-1), d(365), 70,  "tablet",       5.00),
        (1, "Ceftriaxone 1g",       2,  d(-1), d(365), 30,  "injectable",  85.00),
        (3, "Ceftriaxone 1g",       0,  d(-1), d(365), 25,  "injectable",  85.00),
        (3, "Metformin 500mg",      10, d(-1), d(365), 100, "tablet",      10.00),
        (6, "Metformin 500mg",      8,  d(-1), d(365), 60,  "tablet",      10.00),
        (2, "Ciprofloxacin 250mg",  5,  d(-1), d(365), 50,  "tablet",      18.00),
        (5, "Ciprofloxacin 250mg",  0,  d(-1), d(365), 40,  "tablet",      18.00),
        (1, "Ondansetron 4mg",      5,  d(-1), d(365), 35,  "injectable",  45.00),
        (5, "Salbutamol Inhaler",   2,  d(-1), d(365), 20,  "other",      120.00),
        (4, "Atorvastatin 10mg",    10, d(-1), d(365), 80,  "tablet",      22.00),
        (6, "Aspirin 75mg",         30, d(-1), d(365), 100, "tablet",       4.00),
        (3, "Omeprazole 20mg",      5,  d(-1), d(365), 40,  "capsule",     15.00),
    ]
    cur.executemany(
        """INSERT INTO medicines
           (facility_id, medicine_name, quantity, manufacture_date,
            expiry_date, needed_quantity, date_added, medicine_type, price_per_unit)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        [(fid, nm, qty, mfg, exp, nq, today_iso, mtype, price)
         for fid, nm, qty, mfg, exp, nq, mtype, price in needed],
    )
