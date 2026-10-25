import frappe


def redirect_after_login(login_manager):
    """Mark Website Users for homepage redirection."""

    user = login_manager.user

    if not user or user == "Guest":
        return

    user_type = frappe.db.get_value("User", user, "user_type")

    frappe.local.response["is_desk_user"] = (
        user_type == "System User"
    )
