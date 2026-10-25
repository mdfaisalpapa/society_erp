import frappe

def flag_desk_users(login_manager):
    """
    Evaluates the logged-in user and safely passes a boolean flag 
    to the frontend login script.
    """
    user = frappe.session.user
    user_type = frappe.db.get_value("User", user, "user_type")
    
    # Check if they are an administrative System User
    if user_type == "System User":
        frappe.local.response["is_desk_user"] = True
    else:
        frappe.local.response["is_desk_user"] = False
