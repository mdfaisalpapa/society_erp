import frappe

def get_context(context):
    # 1. Security Check
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    user = frappe.session.user

    # 2. Get the Flat associated with the logged-in user
    owner_record = frappe.db.get_value(
        "Owners", 
        {"linked_user": user, "active": 1}, 
        ["name", "flat"], 
        as_dict=True
    )
    
    if not owner_record:
        context.not_a_resident = True
        return context

    flat = owner_record.flat
    context.flat_number = flat

    # 3. Fetch Ownership History (Sorted newest to oldest)
    # This fetches all records linked to the Flat Customer
    owners_history = frappe.get_all(
        "Owners",
        filters={"flat": flat},
        fields=["name", "owner_name", "mobile_no", "email", "active", "start_date", "end_date", "sale_deed"],
        order_by="start_date desc"
    )

    # 4. Separate Current from Historical
    context.current_owner = None
    context.previous_owners = []

    for owner in owners_history:
        if owner.active == 1:
            context.current_owner = owner
        else:
            context.previous_owners.append(owner)

    return context
