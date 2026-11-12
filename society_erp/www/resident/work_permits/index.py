import random
import frappe
from frappe import _
from frappe.utils import format_date, today
from society_erp.www.resident.notices.index import get_resident_info


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/resident/work_permits"
        raise frappe.Redirect

    res = get_resident_info()
    if not res:
        context.not_a_resident = True
        return context

    context.not_a_resident = False
    context.flat_number = res["flat"]
    context.resident_name = res["name"]
    context.resident_type = res["type"]
    context.is_owner = res["is_owner"]

    permits = frappe.get_all(
        "Work Permit",
        filters={"flat_number": res["flat"]},
        fields=[
            "name", "flat_number", "contractor_name", "work_type",
            "start_date", "end_date", "status", "remarks", "creation"
        ],
        order_by="creation desc",
    )
    for p in permits:
        p["formatted_start"] = format_date(p.start_date) if p.start_date else "-"
        p["formatted_end"] = format_date(p.end_date) if p.end_date else "-"
        # Fetch worker passes linked to this permit
        passes = frappe.get_all(
            "Worker Pass",
            filters={"work_permit": p.name},
            fields=["name", "worker_name", "worker_phone", "passcode", "status"],
            order_by="creation asc",
        )
        p["passes"] = passes

    context.permits = permits
    return context


@frappe.whitelist()
def apply_work_permit(contractor_name, work_type, start_date, end_date, remarks=None):
    res = get_resident_info()
    if not res:
        frappe.throw(_("Access Denied: Only registered residents can apply for work permits."))

    if not contractor_name or not contractor_name.strip():
        frappe.throw(_("Contractor Name is required."))
    if not work_type:
        frappe.throw(_("Work Type is required."))
    if not start_date or not end_date:
        frappe.throw(_("Start Date and End Date are required."))

    doc = frappe.new_doc("Work Permit")
    doc.flat_number = res["flat"]
    doc.contractor_name = contractor_name.strip()
    doc.work_type = work_type
    doc.start_date = start_date
    doc.end_date = end_date
    doc.status = "Pending"
    doc.remarks = remarks.strip() if remarks else ""
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "message": _("Work Permit application submitted successfully (Permit ID: {0}).").format(doc.name),
        "name": doc.name,
    }


@frappe.whitelist()
def add_worker_pass(work_permit, worker_name, worker_phone=None):
    res = get_resident_info()
    if not res:
        frappe.throw(_("Access Denied."))

    permit = frappe.get_doc("Work Permit", work_permit)
    if permit.flat_number != res["flat"]:
        frappe.throw(_("Unauthorized for this permit."), frappe.PermissionError)

    w_name = (worker_name or "").strip()
    if not w_name:
        frappe.throw(_("Worker Name is required."))

    # Generate 6-digit gate passcode e.g. WP-4821
    passcode = f"WP-{random.randint(1000, 9999)}"

    doc = frappe.get_doc({
        "doctype": "Worker Pass",
        "work_permit": work_permit,
        "worker_name": w_name,
        "worker_phone": (worker_phone or "").strip(),
        "passcode": passcode,
        "status": "Active",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "message": _("Worker pass generated successfully! Passcode: {0}").format(passcode),
        "passcode": passcode,
        "name": doc.name,
    }

