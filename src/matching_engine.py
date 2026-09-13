"""
Matching engine for MedRescue AI.

Finds redistribution matches for medicines expiring within 30 days.
A match exists when another facility has a needed_quantity > 0 for the
same medicine_name (case-insensitive) AND is a different facility.

Ranking criteria (higher = better):
  1. Same location_area as the source facility  (+20 pts)
  2. need_gap (needed_quantity - current_quantity at receiver) — larger
     gap → higher priority, normalised to 0-10 pts
  3. Days until expiry — fewer days = more urgent (+0-10 pts)
"""

from datetime import date, timedelta

EXPIRY_WINDOW_DAYS = 30


def compute_matches(conn, facility_id=None):
    """
    Return a list of match dicts, sorted by score descending.

    If facility_id is given, returns only matches where that facility
    is either the source or the recipient.
    Pass facility_id=None to get ALL matches.
    """
    today = date.today()
    cutoff = (today + timedelta(days=EXPIRY_WINDOW_DAYS)).isoformat()
    today_iso = today.isoformat()

    # Medicines expiring within 30 days with stock remaining
    donors = conn.execute(
        """
        SELECT m.id, m.medicine_name, m.quantity, m.expiry_date, m.date_added,
               m.medicine_type, m.price_per_unit,
               m.facility_id,
               f.name AS facility_name, f.type AS facility_type,
               f.location_area, f.contact_number
        FROM   medicines m
        JOIN   facilities f ON f.id = m.facility_id
        WHERE  m.expiry_date <= ?
          AND  m.expiry_date >= ?
          AND  m.quantity > 0
        ORDER  BY m.expiry_date ASC
        """,
        (cutoff, today_iso),
    ).fetchall()

    # Facilities that have registered needed_quantity > 0
    receivers = conn.execute(
        """
        SELECT m.id, m.medicine_name, m.quantity, m.needed_quantity, m.date_added,
               m.facility_id,
               f.name AS facility_name, f.type AS facility_type,
               f.location_area, f.contact_number
        FROM   medicines m
        JOIN   facilities f ON f.id = m.facility_id
        WHERE  m.needed_quantity > 0
        """
    ).fetchall()

    # Build lookup: {(facility_id, medicine_name_lower): [receiver_rows]}
    recv_lookup: dict[tuple, list] = {}
    for r in receivers:
        key = (r["facility_id"], r["medicine_name"].lower())
        recv_lookup.setdefault(key, []).append(r)

    matches = []
    seen = set()  # deduplicate (donor_med_id, receiver_facility_id)

    for donor in donors:
        days_left = (date.fromisoformat(donor["expiry_date"]) - today).days
        med_lower = donor["medicine_name"].lower()

        # Find every facility that needs this medicine
        for (recv_fac_id, recv_med_lower), recv_rows in recv_lookup.items():
            if recv_med_lower != med_lower:
                continue
            if recv_fac_id == donor["facility_id"]:
                continue

            key = (donor["id"], recv_fac_id)
            if key in seen:
                continue
            seen.add(key)

            recv = recv_rows[0]  # first matching row for that facility
            need_gap = max(0, recv["needed_quantity"] - recv["quantity"])

            # ----- Scoring -----
            score = 0

            # Same area bonus
            same_area = (
                donor["location_area"].lower() == recv["location_area"].lower()
            )
            if same_area:
                score += 20

            # Need gap (0–10 pts, capped at gap=100)
            score += min(need_gap, 100) / 10

            # Urgency (fewer days = more points, 0–10 pts)
            score += max(0, (EXPIRY_WINDOW_DAYS - days_left)) / 3

            # How many units to suggest
            transfer_qty = min(donor["quantity"], max(need_gap, 1))

            # Plain-language reason
            reasons = []
            if days_left <= 7:
                reasons.append(
                    f"<strong>Critical:</strong> expires in {days_left} day{'s' if days_left != 1 else ''}"
                )
            else:
                reasons.append(f"Expires in {days_left} days")

            if same_area:
                reasons.append(
                    f"{recv['facility_name']} is in the <strong>same area</strong> ({recv['location_area']})"
                )
            else:
                reasons.append(
                    f"{recv['facility_name']} is in {recv['location_area']}"
                )

            if need_gap > 0:
                reasons.append(
                    f"needs {recv['needed_quantity']} units, has {recv['quantity']}"
                )

            reasons.append(
                f"Suggested transfer: <strong>{transfer_qty} units</strong>"
            )

            matches.append(
                {
                    "medicine_id":           donor["id"],
                    "medicine_name":         donor["medicine_name"],
                    "medicine_type":         donor["medicine_type"] if "medicine_type" in donor.keys() else "other",
                    "price_per_unit":        donor["price_per_unit"] if "price_per_unit" in donor.keys() else 0.0,
                    "expiry_date":           donor["expiry_date"],
                    "days_left":             days_left,
                    "from_facility_id":      donor["facility_id"],
                    "from_facility_name":    donor["facility_name"],
                    "from_location":         donor["location_area"],
                    "from_contact":          donor["contact_number"],
                    "from_date_added":       donor["date_added"],
                    "to_facility_id":        recv_fac_id,
                    "to_facility_name":      recv["facility_name"],
                    "to_location":           recv["location_area"],
                    "to_contact":            recv["contact_number"],
                    "to_date_added":         recv["date_added"],
                    "donor_qty":             donor["quantity"],
                    "transfer_qty":          transfer_qty,
                    "need_gap":              need_gap,
                    "score":                 round(score, 2),
                    "reason":                " · ".join(reasons),
                    "urgency_label":         _urgency_label(days_left),
                    "same_area":             same_area,
                }
            )

    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches


def _urgency_label(days_left: int) -> str:
    if days_left <= 7:
        return "critical"
    if days_left <= 15:
        return "high"
    if days_left <= 30:
        return "medium"
    return "low"
