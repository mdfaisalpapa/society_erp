import frappe
from society_erp.api.utils import portal_api

@frappe.whitelist()
@portal_api
def check_guard_status(messenger_id: str, platform: str = "Telegram") -> dict:
    """Check if device is an authorized security guard."""
    device = frappe.get_all(
        "Authorized Bot Device",
        filters={
            "messenger_id": str(messenger_id),
            "platform": platform.capitalize(),
            "is_active": 1
        },
        fields=["name", "device_name", "is_active"]
    )
    return {
        "is_guard": len(device) > 0,
        "device_name": device[0].device_name if device else None
    }

@frappe.whitelist()
@portal_api
def verify_entry_code(passcode: str) -> dict:
    """Security guard passcode verification for visitors and staff."""
    code = (passcode or "").strip()
    if not code:
        return {"valid": False, "message": "Passcode required"}

    # Check Visitor Log
    visitor = frappe.get_all(
        "Visitor Log",
        filters={"passcode": code},
        fields=["name", "resident", "visitor_name", "status", "expected_date", "expected_end_date"],
        limit=1
    )
    if visitor:
        v = visitor[0]
        return {
            "valid": True,
            "type": "Visitor",
            "flat": v.resident,
            "name": v.visitor_name,
            "status": v.status,
            "date": str(v.expected_date)
        }

    return {"valid": False, "message": "Invalid or expired passcode"}
