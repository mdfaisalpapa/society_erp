import frappe
from frappe.utils import format_date
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api


@frappe.whitelist()
@portal_api
def get_facility_bookings(for_user: str = None) -> dict:
    """
    Fetch facility bookings for the verified flat(s).
    """
    owners = get_verified_owner_records(user_override=for_user)
    flats = sorted({o.flat for o in owners if o.flat})

    if not flats:
        return {"bookings": [], "count": 0}

    bookings = frappe.get_all(
        "Facility Booking",
        filters={"resident": ["in", flats]},
        fields=["name", "facility", "shift", "resident", "booking_date", "status", "remarks", "creation"],
        order_by="booking_date desc, creation desc",
        limit_page_length=20,
    )

    for b in bookings:
        b["formatted_booking_date"] = format_date(b.booking_date, "dd-MM-yyyy") if b.booking_date else ""

    return {
        "bookings": bookings,
        "count": len(bookings),
        "primary_booking": bookings[0] if bookings else None
    }
