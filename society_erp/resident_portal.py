
import frappe
from frappe import _
import re
from frappe.utils import validate_email_address

VERIFIED_OWNER_STATUSES = (
    "Verified by Bot",
    "Verified Physically",
    "Verified with CGEWHO Data",
)


def get_verified_owner_records():
    """Return verified owner OR active tenant records linked to the current login securely."""
    user = frappe.session.user

    if user == "Guest":
        frappe.throw(_("Please log in to access the resident portal."), frappe.PermissionError)

    user_email = user.strip().lower()
    records = []

    # 1. Check Owners
    owner_list = frappe.get_all(
        "Owners",
        filters={"active": 1},
        fields=[
            "name", "flat", "owner_name", "owner_address", 
            "mobile_no", "email", "start_date", "end_date", "registration_status"
        ],
        order_by="flat asc",
    )
    records = [r for r in owner_list if r.email and r.email.strip().lower() == user_email]
    for r in records:
        r.resident_type = "Owner"
        r.resident_name = r.owner_name
            
    # 2. Check Tenants if not found as Owner
    if not records:
        tenant_list = frappe.get_all(
            "Tenants",
            filters={"active": 1},
            fields=[
                "name", "flat", "tenant_name", 
                "mobile_no", "email", "start_date", "end_date", "registration_status"
            ],
            order_by="flat asc",
        )
        records = [t for t in tenant_list if t.email and t.email.strip().lower() == user_email]
        for r in records:
            r.resident_type = "Tenant"
            r.resident_name = r.tenant_name
            r.owner_name = r.tenant_name          # Fallback for templates expecting owner_name
            r.owner_address = f"Flat {r.flat}"    # Fallback address for tenants

    if not records:
        frappe.throw(
            _("No verified flat is linked to your account. Please contact the association office."),
            frappe.PermissionError,
        )

    return records


@frappe.whitelist()
def get_profile():
    """Return profile information for verified flats linked to this user (Owner or Tenant)."""
    records = get_verified_owner_records()

    return {
        "owners": [
            {
                "flat": rec.flat,
                "owner_name": rec.resident_name,
                "owner_address": getattr(rec, "owner_address", f"Flat {rec.flat}"),
                "mobile_no": rec.mobile_no,
                "email": rec.email,
                "start_date": str(rec.start_date or ""),
                "end_date": str(rec.end_date or ""),
                "registration_status": rec.registration_status,
                "resident_type": getattr(rec, "resident_type", "Owner")
            }
            for rec in records
        ]
    }
@frappe.whitelist()
def get_profile():
    """Return profile information for verified flats linked to this user."""
    owners = get_verified_owner_records()

    return {
        "owners": [
            {
                "flat": owner.flat,
                "owner_name": owner.resident_name, # Uses the unified alias from above
                "owner_address": owner.owner_address,
                "mobile_no": owner.mobile_no,
                "email": owner.email,
                "start_date": str(owner.start_date or ""),
                "end_date": str(owner.end_date or ""),
                "registration_status": owner.registration_status,
                "resident_type": owner.resident_type
            }
            for owner in owners
        ]
    }

@frappe.whitelist()
def get_dashboard():
    """Return only data associated with verified owner flats."""

    owners = get_verified_owner_records()
    flats = sorted({owner.flat for owner in owners if owner.flat})

    if not flats:
        frappe.throw(
            _("No authorised flat is linked to your account."),
            frappe.PermissionError,
        )

    tickets = frappe.get_all(
        "Maintenance Ticket",
        filters={
            "resident": ["in", flats],
        },
        fields=[
            "name",
            "resident",
            "category",
            "description",
            "status",
            "received_on",
        ],
        order_by="received_on desc",
        limit_page_length=10,
    )

    return {
        "owners": owners,
        "tickets": tickets,
    }
