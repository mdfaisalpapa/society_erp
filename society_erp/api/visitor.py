import random
from datetime import datetime, timedelta
import frappe
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api

@frappe.whitelist()
@portal_api
def get_recent_visitors(for_user: str = None) -> dict:
    """Fetch recent visitors for the resident's flat."""
    owners = get_verified_owner_records(user_override=for_user)
    flats = sorted({o.flat for o in owners if o.flat})

    if not flats:
        return {"visitors": [], "count": 0}

    logs = frappe.get_all(
        "Visitor Log",
        filters={"resident": ["in", flats]},
        fields=["name", "visitor_name", "status", "entry_type", "expected_date", "passcode", "creation"],
        order_by="creation desc",
        limit_page_length=10
    )
    return {
        "visitors": logs,
        "count": len(logs)
    }

@frappe.whitelist()
@portal_api
def preapprove_visitor(visitor_name: str, purpose: str = "Guest", days_valid: int = 1, for_user: str = None) -> dict:
    """Generate a pre-approved visitor entry passcode."""
    owners = get_verified_owner_records(user_override=for_user)
    if not owners:
        frappe.throw("No verified flat linked to user.")

    flat = owners[0].flat
    clean_name = (visitor_name or "Guest").strip()
    target_date = datetime.now()
    expected_date = target_date.strftime("%Y-%m-%d")
    end_date = (target_date + timedelta(days=max(1, int(days_valid)) - 1)).strftime("%Y-%m-%d")
    
    passcode = f"{flat.replace(' ', '')}-{random.randint(1000, 9999)}"

    doc = frappe.get_doc({
        "doctype": "Visitor Log",
        "resident": flat,
        "visitor_name": clean_name,
        "status": "Approved",
        "entry_type": "Pre-Approved",
        "expected_date": expected_date,
        "expected_end_date": end_date,
        "purpose_of_visit": purpose or "Guest",
        "passcode": passcode
    }).insert(ignore_permissions=True)

    return {
        "pass_id": doc.name,
        "passcode": passcode,
        "flat": flat,
        "visitor_name": clean_name,
        "valid_until": end_date
    }
