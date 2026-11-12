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
        frappe.local.flags.redirect_location = "/login?redirect-to=/resident/pets"
        raise frappe.Redirect

    res = get_resident_info()
    if not res:
        context.not_a_resident = True
        return context

    context.not_a_resident = False
    context.flat_number = res["flat"]
    context.resident_name = res["name"]
    context.resident_type = res["type"]

    pets = frappe.get_all(
        "Resident Pets",
        filters={"flat": res["flat"]},
        fields=[
            "name", "pet_name", "license_no", "license_issue_date",
            "license_expiry_date", "vaccination_certificate_no",
            "vaccination_date", "vaccination_due_date", "approval_status",
            "pet_photo", "belongs_to", "creation"
        ],
        order_by="creation desc",
    )
    for p in pets:
        p["formatted_lic_expiry"] = format_date(p.license_expiry_date) if p.license_expiry_date else "-"
        p["formatted_vac_due"] = format_date(p.vaccination_due_date) if p.vaccination_due_date else "-"
        p["formatted_vac_date"] = format_date(p.vaccination_date) if p.vaccination_date else "-"

    context.pets = pets
    return context


@frappe.whitelist()
def register_pet(pet_name, license_no=None, license_expiry_date=None, vaccination_certificate_no=None, vaccination_date=None, vaccination_due_date=None, pet_photo=None):
    res = get_resident_info()
    if not res:
        frappe.throw(_("Access Denied: Only registered residents can register pets."))

    if not pet_name or not pet_name.strip():
        frappe.throw(_("Pet Name is required."))

    doc = frappe.new_doc("Resident Pets")
    doc.flat = res["flat"]
    doc.pet_name = pet_name.strip()
    doc.license_no = license_no.strip() if license_no else ""
    doc.license_expiry_date = license_expiry_date if license_expiry_date else None
    doc.vaccination_certificate_no = vaccination_certificate_no.strip() if vaccination_certificate_no else ""
    doc.vaccination_date = vaccination_date if vaccination_date else None
    doc.vaccination_due_date = vaccination_due_date if vaccination_due_date else None
    doc.pet_photo = pet_photo if pet_photo else None
    doc.belongs_to = res["type"]
    doc.approval_status = "Pending"
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "message": _("Pet registration submitted successfully (ID: {0}).").format(doc.name),
        "name": doc.name,
    }
