import frappe


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    from society_erp.api.resident_family import _current_resident

    try:
        resident = _current_resident()
    except frappe.PermissionError:
        context.not_a_resident = True
        return context

    context.not_a_resident = False
    context.flat_number = resident["flat"]
    context.resident_name = resident.get("name")
    context.resident_type = resident.get("type")

    # Find active staff-to-flat links for this resident's authorised flat.
    links = frappe.get_all(
        "Staff Flat Link",
        filters={
            "parenttype": "Domestic Staff",
            "parentfield": "linked_flats",
            "flat": resident["flat"],
            "is_active": 1,
        },
        fields=["parent"],
        order_by="parent asc",
        limit_page_length=1000,
    )

    staff_names = sorted({link.parent for link in links if link.parent})

    if not staff_names:
        context.staff_members = []
        return context

    # Only display staff whose own status is Active as well.
    context.staff_members = frappe.get_all(
        "Domestic Staff",
        filters={
            "name": ["in", staff_names],
            "status": "Active",
        },
        fields=["name", "staff_name", "role", "phone", "status"],
        order_by="staff_name asc",
        limit_page_length=1000,
    )

    return context
