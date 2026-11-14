import random
from datetime import datetime, timedelta
import frappe
from frappe.utils import format_date
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api

@frappe.whitelist()
@portal_api
def get_recent_visitors(for_user: str = None) -> dict:
    """Fetch recent visitors for the resident's flat with complete details and summary text."""
    owners = get_verified_owner_records(user_override=for_user)
    flats = sorted({o.flat for o in owners if o.flat})

    if not flats:
        return {"visitors": [], "count": 0, "summary_text": "No registered flats found."}

    logs = frappe.get_all(
        "Visitor Log",
        filters={"resident": ["in", flats]},
        fields=["name", "visitor_name", "status", "entry_type", "purpose", "expected_date", "in_time", "out_time", "passcode", "creation"],
        order_by="creation desc",
        limit_page_length=15
    )

    lines = []
    for v in logs:
        v_date = format_date(v.expected_date, "dd-MM-yyyy") if v.expected_date else "-"
        in_t = str(v.in_time).split(".")[0] if v.in_time else "Not Checked-In"
        out_t = str(v.out_time).split(".")[0] if v.out_time else "-"
        lines.append(
            f"• 🎫 *{v.visitor_name or 'Guest'}* ({v.entry_type or v.purpose or 'General'})\n"
            f"  Date: {v_date} | Status: `{v.status}` | Passcode: `{v.passcode or '-'}`\n"
            f"  In: {in_t} | Out: {out_t}"
        )

    summary_text = "\n\n".join(lines) if lines else "No visitor logs recorded recently."

    return {
        "visitors": logs,
        "count": len(logs),
        "primary_visitor": logs[0] if logs else None,
        "summary_text": summary_text
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


def find_flat_resident_users(flat: str) -> list:
    """Returns all active user emails associated with a flat (owners, linked users, and tenants)."""
    if not flat:
        return []
    flat = str(flat).strip()
    users = set()

    # 1. Check Owners
    owners = frappe.get_all(
        "Owners",
        filters={"flat": flat, "active": 1},
        fields=["email", "linked_user"]
    )
    for o in owners:
        if o.linked_user:
            users.add(o.linked_user.strip().lower())
        elif o.email:
            users.add(o.email.strip().lower())

    # 2. Check Tenants
    tenants = frappe.get_all(
        "Tenants",
        filters={"flat": flat, "active": 1},
        fields=["email", "linked_user"]
    )
    for t in tenants:
        if t.get("linked_user"):
            users.add(t.linked_user.strip().lower())
        elif t.email:
            users.add(t.email.strip().lower())

    return list(users)


def notify_resident_of_visitor_entry(doc, method=None):
    """
    Hooked to Visitor Log after_insert or on creation.
    Dispatches instant Web Push notification with Approve / Deny interactive actions
    to the resident when a visitor arrives at the gate (Walk-in or Delivery).
    """
    if not doc.resident:
        return

    # Only send action approval push for pending arrivals or walk-in entries
    if doc.status not in ("Pending", "Walk-in") and doc.entry_type == "Pre-Approved":
        return

    resident_users = find_flat_resident_users(doc.resident)
    if not resident_users:
        return

    visitor_label = doc.visitor_name or "A visitor"
    purpose_label = f" ({doc.purpose})" if getattr(doc, "purpose", None) else ""
    vehicle_label = f" | Vehicle: {doc.vehicle_number}" if getattr(doc, "vehicle_number", None) else ""

    push_title = f"🚪 Gate Entry Request: {visitor_label}"
    push_body = f"{visitor_label}{purpose_label} is at the security gate for Flat {doc.resident}.{vehicle_label} Tap to Approve or Deny."

    push_payload = {
        "visitor_log_id": doc.name,
        "flat": doc.resident,
        "actions": [
            {"action": "approve", "title": "✅ Allow Entry"},
            {"action": "deny", "title": "❌ Deny"}
        ]
    }

    try:
        from society_erp.push_notifications.api import send_push_notification
        for u in resident_users:
            send_push_notification(
                user=u,
                title=push_title,
                body=push_body,
                url="/resident/visitors",
                data=push_payload,
                async_send=True
            )
    except Exception as e:
        frappe.log_error(f"Failed to send visitor gate push notification: {e}", "Visitor Push Error")


@frappe.whitelist(methods=["POST"])
def respond_visitor_entry(visitor_log_id: str, action: str) -> dict:
    """
    Handles Approve or Deny action on a Visitor Log by the resident or security guard.
    Action can be 'approve' or 'deny'.
    """
    if not visitor_log_id or not action:
        frappe.throw("visitor_log_id and action are required.")

    action_norm = action.strip().lower()
    if action_norm not in ("approve", "deny"):
        frappe.throw("Invalid action. Must be 'approve' or 'deny'.")

    if not frappe.db.exists("Visitor Log", visitor_log_id):
        frappe.throw(f"Visitor record {visitor_log_id} not found.")

    vlog = frappe.get_doc("Visitor Log", visitor_log_id)
    new_status = "Approved" if action_norm == "approve" else "Denied"
    vlog.status = new_status
    vlog.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "visitor_log_id": vlog.name,
        "new_status": new_status,
        "message": f"Visitor entry has been {new_status.lower()}."
    }
