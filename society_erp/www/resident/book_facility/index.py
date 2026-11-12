import frappe
from frappe import _
from frappe.utils import format_date, today
from society_erp.www.resident.notices.index import get_resident_info


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    res_info = get_resident_info()
    if not res_info:
        context.not_a_resident = True
        return context

    context.not_a_resident = False
    context.resident_info = res_info
    context.flat_number = res_info.get("flat")
    context.today_date = today()

    flat = res_info.get("flat")

    # Available facilities list from DocType Select options or defaults
    facilities = ["Community Hall"]
    meta = frappe.get_meta("Facility Booking")
    facility_field = meta.get_field("facility")
    if facility_field and facility_field.options:
        opts = [opt.strip() for opt in facility_field.options.split("\n") if opt.strip()]
        if opts:
            facilities = opts

    context.facilities = facilities

    # Fetch booking history for this resident flat
    bookings = frappe.get_all(
        "Facility Booking",
        filters={"resident": flat},
        fields=["name", "facility", "resident", "booking_date", "status", "creation"],
        order_by="booking_date desc, creation desc",
        limit_page_length=50,
    )

    for b in bookings:
        b["formatted_booking_date"] = format_date(b.booking_date, "dd-MM-yyyy") if b.booking_date else ""

    context.bookings = bookings

    # Also fetch upcoming confirmed bookings for calendar awareness
    upcoming_bookings = frappe.get_all(
        "Facility Booking",
        filters={"booking_date": [">=", today()], "status": "Confirmed"},
        fields=["facility", "booking_date", "resident"],
        order_by="booking_date asc",
        limit_page_length=20,
    )
    for ub in upcoming_bookings:
        ub["formatted_booking_date"] = format_date(ub.booking_date, "dd-MM-yyyy")

    context.upcoming_bookings = upcoming_bookings
    return context


@frappe.whitelist()
def book_facility(facility, booking_date):
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to book a facility."), frappe.PermissionError)

    res_info = get_resident_info()
    if not res_info or not res_info.get("flat"):
        frappe.throw(_("No verified flat linked to your account."), frappe.PermissionError)

    flat = res_info.get("flat")

    if not facility:
        frappe.throw(_("Facility is required."))
    if not booking_date:
        frappe.throw(_("Booking Date is required."))

    # Check for existing confirmed booking for the same facility on the same date
    existing = frappe.db.exists(
        "Facility Booking",
        {
            "facility": facility,
            "booking_date": booking_date,
            "status": "Confirmed",
        },
    )
    if existing:
        frappe.throw(_("Facility '{0}' is already booked on {1}. Please select another date.").format(facility, format_date(booking_date, "dd-MM-yyyy")))

    doc = frappe.get_doc({
        "doctype": "Facility Booking",
        "facility": facility,
        "resident": flat,
        "booking_date": booking_date,
        "status": "Confirmed",
    })
    doc.insert(ignore_permissions=True)
    doc.submit()

    return {
        "status": "success",
        "message": _("Facility booking confirmed successfully!"),
        "booking_id": doc.name,
    }


@frappe.whitelist()
def cancel_booking(booking_id):
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to cancel a booking."), frappe.PermissionError)

    res_info = get_resident_info()
    if not res_info or not res_info.get("flat"):
        frappe.throw(_("No verified flat linked to your account."), frappe.PermissionError)

    flat = res_info.get("flat")
    if not frappe.db.exists("Facility Booking", booking_id):
        frappe.throw(_("Booking not found."))

    booking = frappe.get_doc("Facility Booking", booking_id)
    if booking.resident != flat:
        frappe.throw(_("You are not authorized to cancel this booking."), frappe.PermissionError)

    booking.db_set("status", "Cancelled")
    return {
        "status": "success",
        "message": _("Booking cancelled successfully."),
    }
