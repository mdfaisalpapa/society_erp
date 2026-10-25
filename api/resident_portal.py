import frappe
from frappe import _
from frappe.utils import today

ALLOWED_ROLES = {"Flat Owner", "Flat Tenant"}


def get_resident_context():
    user = frappe.session.user

    if user == "Guest":
        frappe.throw(
            _("Please log in first."),
            frappe.PermissionError,
        )

    if not ALLOWED_ROLES.intersection(frappe.get_roles(user)):
        frappe.throw(
            _("Resident portal access is not permitted."),
            frappe.PermissionError,
        )

    owners = frappe.get_all(
        "Owners",
        filters={
            "linked_user": user,
            "active": 1,
        },
        fields=["name", "flat", "owner_name"],
    )

    tenants = frappe.get_all(
        "Tenants",
        filters={
            "linked_user": user,
            "active": 1,
        },
        fields=["name", "flat", "tenant_name"],
    )

    # Only verified, explicitly linked resident records are accepted.
    # Adjust the allowed statuses to match your association's approval policy.
    owners = [
        x for x in owners
        if x.flat
    ]

    tenants = [
        x for x in tenants
        if x.flat
        and frappe.db.get_value(
            "Tenants", x.name, "registration_status"
        ) in ("Verified by Bot", "Verified Physically")
    ]

    flats = sorted({
        x.flat for x in owners + tenants if x.flat
    })

    if not flats:
        frappe.throw(
            _("No active, authorised flat is linked to your account. "
              "Please contact the association office."),
            frappe.PermissionError,
        )

    return {
        "user": user,
        "owners": owners,
        "tenants": tenants,
        "flats": flats,
    }


@frappe.whitelist()
def get_dashboard():
    ctx = get_resident_context()

    tickets = frappe.get_all(
        "Maintenance Ticket",
        filters={
            "resident": ["in", ctx["flats"]],
        },
        fields=[
            "name",
            "resident",
            "category",
            "status",
            "received_on",
        ],
        order_by="received_on desc",
        limit_page_length=10,
    )

    return {
        "flats": ctx["flats"],
        "tickets": tickets,
    }




@frappe.whitelist()
def reallocate_parking(slot_id, new_type, occupant, old_alloc="NONE", start_date=None, end_date=None):
    """Securely closes the old parking allocation and opens a new one."""
    
    # 1. Security Check: Ensure the logged-in user actually owns this slot!
    user = frappe.session.user
    owner_flat = frappe.db.get_value("Owners", {"linked_user": user, "active": 1}, "flat")
    
    if not owner_flat:
        frappe.throw("Resident profile not found.")
        
    slot_owner = frappe.db.get_value("Parking Slot", slot_id, "owned_by")
    if owner_flat != slot_owner:
        frappe.throw("⛔ Access Denied. You do not own this parking slot.")

    if not start_date:
        start_date = today()

    # 2. Close Old Allocation
    if old_alloc and old_alloc != "NONE":
        # Using set_value for a quick, direct database update
        frappe.db.set_value("Parking Allocation", old_alloc, {
            "end_date": start_date,
            "status": "Expired"
        })

    # 3. Create New Allocation
    new_alloc = frappe.get_doc({
        "doctype": "Parking Allocation",
        "parking_slot": slot_id,
        "occupied_by": occupant.strip().upper(),
        "allocation_type": new_type,
        "start_date": start_date,
        "end_date": end_date or None,
        "status": "Active"
    })
    
    # ignore_permissions=True allows the web portal user to create the record 
    # even without backend Desk access (since we already did our manual security check above)
    new_alloc.insert(ignore_permissions=True)
    
    return True
