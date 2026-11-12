import frappe
from frappe.utils import format_date
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api


@frappe.whitelist()
@portal_api
def get_facility_bookings(for_user: str = None) -> dict:
    """
    Fetch comprehensive facility booking history with full details matching `/resident/book_facility`.
    """
    owners = get_verified_owner_records(user_override=for_user)
    flats = sorted({o.flat for o in owners if o.flat})

    if not flats:
        return {"bookings": [], "count": 0, "summary_text": "No registered flats found."}

    bookings = frappe.get_all(
        "Facility Booking",
        filters={"resident": ["in", flats]},
        fields=["name", "facility", "shift", "resident", "booking_date", "status", "remarks", "creation"],
        order_by="booking_date desc, creation desc",
        limit_page_length=20,
    )

    lines = []
    for b in bookings:
        b["formatted_booking_date"] = format_date(b.booking_date, "dd-MM-yyyy") if b.booking_date else "-"
        lines.append(f"• *{b.facility}* ({b['formatted_booking_date']})\n  Shift: {b.shift}\n  Status: `{b.status}`\n  Ref: #{b.name}")

    summary_text = "\n\n".join(lines) if lines else "No past or active hall reservations on record."

    return {
        "bookings": bookings,
        "count": len(bookings),
        "primary_booking": bookings[0] if bookings else None,
        "summary_text": summary_text
    }
