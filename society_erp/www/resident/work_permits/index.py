import random
import frappe
from frappe import _
from frappe.utils import format_date, today
from society_erp.www.resident.notices.index import get_resident_info


def get_context(context):
    context.is_standalone = bool(frappe.form_dict.get("standalone"))
    if context.is_standalone:
        context.no_header = True
        context.no_sidebar = True

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
            "start_date", "end_date", "status", "remarks", "creation",
            "deposit_amount", "payment_reference_no", "payment_date",
            "sales_invoice", "payment_entry", "debris_cleared",
            "refund_amount", "refund_reference_no", "refund_date", "refund_payment_entry"
        ],
        order_by="creation desc",
    )
    for p in permits:
        p["formatted_start"] = format_date(p.start_date) if p.start_date else "-"
        p["formatted_end"] = format_date(p.end_date) if p.end_date else "-"
        p["is_paid"] = bool(p.payment_reference_no and p.payment_reference_no.strip())
        # Fetch worker passes linked to this permit
        passes = frappe.get_all(
            "Worker Pass",
            filters={"work_permit": p.name},
            fields=["name", "worker_name", "worker_phone", "passcode", "status"],
            order_by="creation asc",
        )
        p["passes"] = passes

    context.permits = permits

    # Banking and UPI details for Work Permit Deposit (₹5,000)
    settings = frappe.get_single("Society ERP Settings")
    deposit_val = 5000.0
    context.bank_details = {
        "beneficiary": getattr(settings, "bank_account_beneficiary_name", "Apartment Owners Association"),
        "account_no": getattr(settings, "bank_account_number", "4139313654"),
        "ifsc": getattr(settings, "bank_ifsc_code", "CBIN0283135"),
        "bank_name": getattr(settings, "bank_name", "Central Bank of India"),
        "deposit": deposit_val,
        "retained": 1000.0,
        "refundable": 4000.0,
    }
    acc_clean = context.bank_details["account_no"].strip()
    ifsc_clean = context.bank_details["ifsc"].strip()
    # NPCI standard Account + IFSC virtual payment address format
    context.upi_intent_uri = f"upi://pay?pa={acc_clean}@{ifsc_clean}.ifsc.npci&pn=APARTMENT%20OWNERS%20ASSOCIATION&am=5000&cu=INR"
    import urllib.parse
    encoded_uri = urllib.parse.quote(context.upi_intent_uri, safe="")
    context.upi_qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={encoded_uri}"

    return context


@frappe.whitelist()
def apply_work_permit(contractor_name, work_type, start_date, end_date, remarks=None, payment_reference_no=None, payment_date=None):
    res = get_resident_info()
    if not res:
        frappe.throw(_("Access Denied: Only registered residents can apply for work permits."))

    if not contractor_name or not contractor_name.strip():
        frappe.throw(_("Contractor Name is required."))
    if not work_type:
        frappe.throw(_("Work Type is required."))
    if not start_date or not end_date:
        frappe.throw(_("Start Date and End Date are required."))

    clean_utr = (payment_reference_no or "").strip()
    if not clean_utr or len(clean_utr) < 5:
        frappe.throw(_("Please enter at least the last 5 digits of your UPI Transaction ID / UTR."))

    doc = frappe.new_doc("Work Permit")
    doc.flat_number = res["flat"]
    doc.contractor_name = contractor_name.strip()
    doc.work_type = work_type
    doc.start_date = start_date
    doc.end_date = end_date
    doc.status = "Pending"
    doc.remarks = remarks.strip() if remarks else ""
    doc.deposit_amount = 5000.0
    doc.payment_reference_no = clean_utr
    doc.payment_date = payment_date or today()
    doc.refund_amount = 4000.0
    doc.debris_cleared = 0
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "message": _("Work Permit application submitted successfully with deposit details (Permit ID: {0}).").format(doc.name),
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

