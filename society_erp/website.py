import frappe


def get_website_user_home_page(user):
    if frappe.db.get_value("User", user, "user_type") != "Website User":
        return None

    if "Flat Owner" in frappe.get_roles(user):
        return "resident"

    return None
