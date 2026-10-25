import frappe
from frappe import _


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    from society_erp.api.maintenance_portal import _resident

    try:
        resident = _resident()
    except frappe.PermissionError:
        context.error_message = _("Your account is not linked to an active registered flat.")
        context.tickets = []
        context.categories = []
        return context

    context.flat_number = resident["flat"]
    context.resident_name = resident["name"]
    context.resident_type = resident["type"]
    context.error_message = None

    meta = frappe.get_meta("Maintenance Ticket")
    category_field = meta.get_field("category")
    context.categories = [
        value.strip()
        for value in (category_field.options or "").splitlines()
        if value.strip()
    ]

    # Initial server-rendered list; further pages and actions use secure whitelisted methods.
    statuses = ["Open", "Assigned", "Pending", "In Progress"]
    context.tickets = frappe.get_all(
        "Maintenance Ticket",
        filters={"resident": resident["flat"], "status": ["in", statuses]},
        fields=["name", "category", "description", "photo", "status", "creation", "resolution_remarks"],
        order_by="creation desc",
        limit_page_length=10,
    )
    return context
