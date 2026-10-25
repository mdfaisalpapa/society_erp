import frappe
from frappe.core.doctype.user import user as user_module

@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_password(
    new_password,
    logout_all_sessions=0,
    key=None,
    old_password=None,
):
    # Use Frappe's original implementation for password validation,
    # reset-key verification, password update and login.
    redirect = user_module.update_password(
        new_password=new_password,
        logout_all_sessions=logout_all_sessions,
        key=key,
        old_password=old_password,
    )

    # After a successful reset, Frappe logs in the reset user.
    if isinstance(redirect, str) and frappe.session.user != "Guest":
        user_type = frappe.db.get_value(
            "User", frappe.session.user, "user_type"
        )

        if user_type == "Website User" and redirect == "/desk":
            return "/resident"

    return redirect
