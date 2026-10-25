import frappe
from society_erp.resident_portal import get_verified_owner_records
from society_erp.tenant_portal import get_tenants # <-- Update this import!

def get_context(context):
    # Add inside owner details, tenant management, and work permit page context scripts (.py)
    user_roles = frappe.get_roles(frappe.session.user)
    if "Flat Owner" not in user_roles:
        frappe.throw("Access Denied. This module is restricted to Flat Owners.", frappe.PermissionError)
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    try:
        owners = get_verified_owner_records()
        context.owner = owners[0]
    except frappe.PermissionError:
        context.not_a_resident = True
        return context

    context.flat_number = context.owner.flat
    context.tenants = get_tenants().get("tenants", [])
    
    # Check if a tenant is currently active
    context.is_rented = any(t.active for t in context.tenants)
    
    return context
