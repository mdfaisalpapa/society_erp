import frappe
from frappe import _
from frappe.utils import format_date, today, getdate, add_months
from society_erp.www.resident.notices.index import get_resident_info


def get_context(context):
    context.is_standalone = bool(frappe.form_dict.get("standalone"))
    if context.is_standalone:
        context.no_header = True
        context.no_sidebar = True

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    # Always provide options even if session user has no flat
    meta = frappe.get_meta("Facility Booking")
    facility_field = meta.get_field("facility")
    facilities = ["Community Hall - Main", "Community Hall - Mini", "Clubhouse Hall", "Party Lawn / Terrace"]
    if facility_field and facility_field.options:
        opts = [opt.strip() for opt in facility_field.options.split("\n") if opt.strip()]
        if opts:
            facilities = opts
    context.facilities = facilities

    shift_field = meta.get_field("shift")
    shifts = [
        "Morning (9:00 AM - 1:00 PM)",
        "Afternoon (1:00 PM - 5:00 PM)",
        "Evening / Night (5:00 PM - 10:00 PM)",
        "Full Day (9:00 AM - 10:00 PM)",
    ]
    if shift_field and shift_field.options:
        s_opts = [opt.strip() for opt in shift_field.options.split("\n") if opt.strip()]
        if s_opts:
            shifts = s_opts
    context.shifts = shifts

    res_info = get_resident_info()
    if not res_info:
        context.not_a_resident = True
        return context

    context.not_a_resident = False
    context.resident_info = res_info
    context.flat_number = res_info.get("flat")
    context.today_date = today()
    flat = res_info.get("flat")

    context.shifts = shifts

    # Fetch booking history for this resident flat
    bookings = frappe.get_all(
        "Facility Booking",
        filters={"resident": flat},
        fields=["name", "facility", "shift", "resident", "booking_date", "status", "remarks", "creation"],
        order_by="booking_date desc, creation desc",
        limit_page_length=50,
    )

    for b in bookings:
        b["formatted_booking_date"] = format_date(b.booking_date, "dd-MM-yyyy") if b.booking_date else ""

    context.bookings = bookings
    return context


@frappe.whitelist()
def get_availability(facility, month_year=None):
    """
    Returns booked and available slots for a given facility and month/year.
    Status 'Confirmed' or 'Approved' locks the slot.
    """
    if not facility:
        frappe.throw(_("Facility is required."))

    # Default to current month if not passed
    start_date = today()
    if month_year:
        # e.g., '2026-11'
        start_date = f"{month_year}-01"

    current = getdate(start_date)
    first_of_month = current.replace(day=1)
    # Next 60 days of schedule
    end_date = str(add_months(first_of_month, 2))

    booked_records = frappe.get_all(
        "Facility Booking",
        filters={
            "facility": facility,
            "booking_date": ["between", [str(first_of_month), end_date]],
            "status": ["in", ["Confirmed", "Approved"]],
        },
        fields=["booking_date", "shift", "resident"],
    )

    # Map by date string
    schedule = {}
    for rec in booked_records:
        d_str = str(rec.booking_date)
        if d_str not in schedule:
            schedule[d_str] = []
        schedule[d_str].append({
            "shift": rec.shift or "Full Day (9:00 AM - 10:00 PM)",
            "resident": rec.resident,
        })

    return {
        "facility": facility,
        "booked_schedule": schedule,
    }


def is_shift_conflicting(existing_shift, requested_shift):
    if not existing_shift or not requested_shift:
        return True
    if "Full Day" in existing_shift or "Full Day" in requested_shift:
        return True
    return existing_shift == requested_shift


@frappe.whitelist()
def book_facility(facility, booking_date, shift="Full Day (9:00 AM - 10:00 PM)"):
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
    if not shift:
        shift = "Full Day (9:00 AM - 10:00 PM)"

    # Check for existing confirmed booking for the same facility, date, and shift
    existing_bookings = frappe.get_all(
        "Facility Booking",
        filters={
            "facility": facility,
            "booking_date": booking_date,
            "status": ["in", ["Confirmed", "Approved"]],
        },
        fields=["name", "shift", "resident"],
    )

    for eb in existing_bookings:
        if is_shift_conflicting(eb.shift, shift):
            frappe.throw(
                _("Facility '{0}' is already booked on {1} for {2}. Please select another shift or date.").format(
                    facility, format_date(booking_date, "dd-MM-yyyy"), eb.shift or "Full Day"
                )
            )

    # Check if this resident already has a pending request for the same slot
    pending_bookings = frappe.get_all(
        "Facility Booking",
        filters={
            "facility": facility,
            "resident": flat,
            "booking_date": booking_date,
            "status": "Pending Approval",
        },
        fields=["name", "shift"],
    )
    for pb in pending_bookings:
        if is_shift_conflicting(pb.shift, shift):
            frappe.throw(
                _("You already have a pending booking request for {0} ({1}) on {2}.").format(
                    facility, shift, format_date(booking_date, "dd-MM-yyyy")
                )
            )

    doc = frappe.get_doc({
        "doctype": "Facility Booking",
        "facility": facility,
        "shift": shift,
        "resident": flat,
        "booking_date": booking_date,
        "status": "Pending Approval",
    })
    doc.insert(ignore_permissions=True)

    return {
        "status": "success",
        "message": _("Facility booking request for {0} ({1}) on {2} submitted! It will be reviewed by the Managing Committee.").format(
            facility, shift, format_date(booking_date, "dd-MM-yyyy")
        ),
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
