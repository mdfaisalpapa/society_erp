import frappe
from society_erp.api.utils import portal_api


@frappe.whitelist()
@portal_api
def get_emergency_contacts() -> dict:
    """
    Fetch active emergency contacts categorized into internal society contacts and public emergencies.
    """
    all_contacts = frappe.get_all(
        "Emergency Contact",
        filters={"enabled": 1},
        fields=["name", "title", "category", "phone", "operating_hours", "icon", "description", "sort_order"],
        order_by="sort_order asc, title asc"
    )

    internal_categories = ["Society Security", "Estate Office", "Maintenance & Utilities"]
    internal = []
    public = []

    for c in all_contacts:
        item = {
            "title": c.title,
            "phone": c.phone,
            "hours": c.operating_hours or "24x7",
            "icon": c.icon or "📞",
            "description": c.description or "",
            "category": c.category
        }
        if c.category in internal_categories:
            internal.append(item)
        else:
            public.append(item)

    return {
        "contacts": all_contacts,
        "internal": internal,
        "public": public,
        "count": len(all_contacts)
    }
