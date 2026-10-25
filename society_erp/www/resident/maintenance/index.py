import frappe

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect
        
    user_email = frappe.session.user
    
    # Identify active resident profile
    owner = frappe.db.get_value("Owners", {"email": user_email, "active": 1}, ["name", "flat", "owner_name"], as_dict=True)
    tenant = frappe.db.get_value("Tenants", {"email": user_email, "active": 1}, ["name", "flat", "tenant_name"], as_dict=True)
    
    if not owner and not tenant:
        context.error_message = "Your account is not linked to an active registered flat."
        return context

    active_flat = tenant.flat if tenant else owner.flat
    context.flat_number = active_flat
    context.resident_name = tenant.tenant_name if tenant else owner.owner_name
    
    # Fetch maintenance tickets for this flat
    tickets = frappe.get_all(
        "Maintenance Ticket",
        filters={"resident": active_flat},
        fields=["name", "category", "description", "photo", "status", "creation", "resolution_remarks"],
        order_by="creation desc",
        limit=50
    )
    
    # Format the creation datetime object safely into a string (YYYY-MM-DD)
    for t in tickets:
        if t.get("creation"):
            t["formatted_date"] = str(t.creation)[:10]
        else:
            t["formatted_date"] = ""
            
    context.tickets = tickets
    
    # Fetch category options dynamically from DocType meta
    meta = frappe.get_meta("Maintenance Ticket")
    context.categories = [opt for opt in (meta.get_field("category").options or "").split("\n") if opt]
