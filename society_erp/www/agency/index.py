import frappe
from frappe import _
from frappe.utils import nowdate


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/agency"
        raise frappe.Redirect

    user = frappe.session.user
    roles = frappe.get_roles(user)

    # Agency lookup
    agency = None
    if "System Manager" in roles or user == "Administrator":
        agency = frappe.db.get_value("Facility Agency", {"contract_status": "Active"}, "agency_name")
    else:
        agency = frappe.db.get_value("Facility Agency", {"portal_user": user}, "agency_name")

    if not agency and "System Manager" not in roles and user != "Administrator":
        context.access_denied = True
        return context

    agency_doc = frappe.get_doc("Facility Agency", agency) if agency else None

    context.agency_name = agency
    context.agency_doc = agency_doc
    context.today_date = nowdate()

    # Standalone support
    context.is_standalone = bool(frappe.form_dict.get("standalone"))
    if context.is_standalone:
        context.no_header = True
        context.no_sidebar = True

    return context


@frappe.whitelist()
def get_agency_dashboard_data():
    user = frappe.session.user
    roles = frappe.get_roles(user)

    agency = None
    if "System Manager" in roles or user == "Administrator":
        agency = frappe.db.get_value("Facility Agency", {"contract_status": "Active"}, "agency_name")
    else:
        agency = frappe.db.get_value("Facility Agency", {"portal_user": user}, "agency_name")

    if not agency and "System Manager" not in roles and user != "Administrator":
        frappe.throw(_("Unauthorized: No Facility Agency linked to your account."))

    from society_erp.api.facility_staff import get_daily_roster
    roster_data = get_daily_roster(agency=agency)

    shifts = frappe.get_all("Facility Shift", filters={"enabled": 1}, fields=["name", "start_time", "end_time", "duration_hours"])
    posts = frappe.get_all("Facility Duty Post", filters={"is_active": 1}, fields=["name", "post_name", "category", "zone_type", "cost_center"], order_by="zone_type asc, post_name asc")

    today_musters = frappe.get_all(
        "Facility Shift Muster",
        filters={"agency": agency, "shift_date": nowdate()},
        fields=["name", "shift", "category", "muster_photo", "reported_count", "creation"],
        order_by="creation desc"
    )

    return {
        "agency": agency,
        "roster": roster_data.get("roster", []),
        "total_active_staff": roster_data.get("total_active_staff", 0),
        "on_duty_count": roster_data.get("on_duty_count", 0),
        "pending_approval_count": roster_data.get("pending_approval_count", 0),
        "shifts": shifts,
        "duty_posts": posts,
        "today_musters": today_musters
    }
