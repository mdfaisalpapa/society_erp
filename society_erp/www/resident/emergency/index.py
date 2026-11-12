import frappe
from society_erp.www.resident.notices.index import get_resident_info


def get_context(context):
    context.is_standalone = bool(frappe.form_dict.get("standalone"))
    if context.is_standalone:
        context.no_header = True
        context.no_sidebar = True

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    # Check if Emergency SOS feature is enabled for residents
    is_enabled = frappe.db.get_single_value("Society ERP Settings", "enable_emergency_sos")
    if is_enabled is None:
        is_enabled = 1
    context.feature_enabled = bool(int(is_enabled))

    # Query emergency contacts from DocType
    all_contacts = frappe.get_all(
        "Emergency Contact",
        filters={"enabled": 1},
        fields=["name", "title", "category", "phone", "operating_hours", "icon", "description", "sort_order"],
        order_by="sort_order asc, title asc"
    )

    internal_categories = ["Society Security", "Estate Office", "Maintenance & Utilities"]
    internal_contacts = []
    public_emergencies = []

    for c in all_contacts:
        contact_dict = {
            "title": c.title,
            "phone": c.phone,
            "badge": c.operating_hours or "24x7",
            "icon": c.icon or "📞",
            "desc": c.description or "",
            "category": c.category
        }
        if c.category in internal_categories:
            internal_contacts.append(contact_dict)
        else:
            public_emergencies.append(contact_dict)

    context.internal_contacts = internal_contacts
    context.public_emergencies = public_emergencies

    res_info = get_resident_info()
    if not res_info:
        context.not_a_resident = False
        return context

    context.not_a_resident = False
    context.resident_info = res_info
    context.flat_number = res_info.get("flat")
    return context
