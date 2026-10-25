import frappe

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect
        
    user_email = frappe.session.user.strip().lower()
    
    # 1. Check if the logged-in user is an active Tenant
    tenant = frappe.db.get_value(
        "Tenants", 
        {"email": ["like", user_email], "active": 1}, 
        ["name", "flat", "tenant_name", "email"], 
        as_dict=True
    )
    
    # 2. If not a tenant, check if they are an active Owner
    owner = None
    if not tenant:
        owner = frappe.db.get_value(
            "Owners", 
            {"email": ["like", user_email], "active": 1}, 
            ["name", "flat", "owner_name", "email"], 
            as_dict=True
        )
    
    # 3. If neither exists, trigger the "not a resident" error banner
    if not tenant and not owner:
        context.not_a_resident = True
        return context

    # Populate context variables for the template
    active_flat = tenant.flat if tenant else owner.flat
    context.flat_number = active_flat
    context.resident_name = tenant.tenant_name if tenant else owner.owner_name
    context.belongs_to = "Tenant" if tenant else "Owner"
    context.is_owner = bool(owner)
    
    # Dashboard badges & summary counts
    context.open_tickets_count = frappe.db.count("Maintenance Ticket", {"resident": active_flat, "status": ["in", ["Open", "Assigned", "Pending"]]})
    context.vehicles_count = frappe.db.count("Resident Vehicle", {"flat": active_flat, "active": 1})
    context.permits_count = frappe.db.count("Work Permit", {"flat_number": active_flat})
    
    # Fetch recent active notices
    context.notices = frappe.get_all(
        "Society Notice",
        filters={"is_active": 1},
        fields=["title", "date"],
        order_by="date desc",
        limit=3
    )
    
    return context
