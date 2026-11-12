import random
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

    # Fetch visitor logs for this resident
    flat = res_info.get("flat")
    logs = frappe.get_all(
        "Visitor Log",
        filters={"resident": flat},
        fields=[
            "name",
            "visitor_name",
            "entry_type",
            "purpose",
            "passcode",
            "expected_date",
            "expected_end_date",
            "status",
            "in_time",
            "out_time",
            "vehicle_number",
            "creation",
        ],
        order_by="creation desc",
        limit_page_length=50,
    )

    for log in logs:
        log["formatted_expected_date"] = format_date(log.expected_date, "dd-MM-yyyy") if log.expected_date else ""
        log["formatted_end_date"] = format_date(log.expected_end_date, "dd-MM-yyyy") if log.expected_end_date else ""
        log["formatted_in_time"] = frappe.utils.format_datetime(log.in_time, "dd-MM-yyyy HH:mm") if log.in_time else "-"
        log["formatted_out_time"] = frappe.utils.format_datetime(log.out_time, "dd-MM-yyyy HH:mm") if log.out_time else "-"

    context.visitor_logs = logs
    return context


@frappe.whitelist()
def generate_visitor_pass(visitor_name, entry_type="Walk-in", purpose="Guest", expected_date=None, expected_end_date=None, vehicle_number=None):
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to create a visitor pass."), frappe.PermissionError)

    res_info = get_resident_info()
    if not res_info or not res_info.get("flat"):
        frappe.throw(_("No verified flat linked to your account."), frappe.PermissionError)

    flat = res_info.get("flat")
    clean_name = (visitor_name or "").strip()
    if not clean_name:
        frappe.throw(_("Visitor Name is required."))

    if not expected_date:
        expected_date = today()
    if not expected_end_date:
        expected_end_date = expected_date

    # Passcode generation: Flat without spaces + 4 random digits e.g. TA1-1001-4921
    passcode = f"{flat.replace(' ', '')}-{random.randint(1000, 9999)}"

    doc = frappe.get_doc({
        "doctype": "Visitor Log",
        "resident": flat,
        "entry_type": entry_type or "Pre-Approved",
        "visitor_name": clean_name,
        "passcode": passcode,
        "expected_date": expected_date,
        "expected_end_date": expected_end_date,
        "status": "Approved" if entry_type == "Pre-Approved" else "Pending",
        "purpose": purpose or "Guest",
        "vehicle_number": (vehicle_number or "").strip().upper() if vehicle_number else None,
    })
    doc.insert(ignore_permissions=True)

    return {
        "status": "success",
        "message": _("Visitor pass generated successfully!"),
        "passcode": passcode,
        "pass_id": doc.name,
    }
