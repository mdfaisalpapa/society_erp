import frappe
from frappe import _
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api


@frappe.whitelist(allow_guest=True)
@portal_api
def resolve_chat_user(channel: str, channel_user_id: str) -> dict:
    """
    Called by universal_chatbot to identify and authenticate incoming messages.

    :param channel: 'Telegram' or 'WhatsApp'
    :param channel_user_id: Telegram chat_id or WhatsApp phone number
    :return: Clean JSON payload with resident profile context or unauthenticated status
    """
    if not channel or not channel_user_id:
        return {
            "authenticated": False,
            "reason": "Missing channel or channel_user_id",
        }

    # Normalize channel name (e.g. 'telegram' -> 'Telegram')
    channel_norm = channel.strip().capitalize()
    user_id_norm = str(channel_user_id).strip()

    # Query Channel Identity
    identity = frappe.db.get_value(
        "Channel Identity",
        {
            "channel": channel_norm,
            "channel_user_id": user_id_norm,
            "verified": 1,
        },
        ["name", "resident_email"],
        as_dict=True,
    )

    if not identity or not identity.resident_email:
        return {
            "authenticated": False,
            "channel": channel_norm,
            "channel_user_id": user_id_norm,
            "reason": "Unlinked or unverified channel account",
        }

    # Fetch verified resident flats using the refactored core logic
    try:
        records = get_verified_owner_records(user_override=identity.resident_email)
    except frappe.PermissionError:
        return {
            "authenticated": False,
            "channel": channel_norm,
            "channel_user_id": user_id_norm,
            "resident_email": identity.resident_email,
            "reason": "No active flat records found for this verified email",
        }

    flats = sorted({r.flat for r in records if r.flat})
    primary = records[0]

    # Check AoA Committee Membership
    committee = frappe.db.get_value(
        "Committee Member",
        {"member_name": identity.resident_email, "status": "Active"},
        ["name", "designation"],
        as_dict=True,
    )

    # Check Guard / Staff Authorized Device
    device = frappe.db.get_value(
        "Authorized Bot Device",
        {"messenger_id": user_id_norm, "is_active": 1},
        ["name", "device_name"],
        as_dict=True,
    )

    return {
        "authenticated": True,
        "channel": channel_norm,
        "channel_user_id": user_id_norm,
        "resident_email": identity.resident_email,
        "resident_name": primary.resident_name,
        "resident_type": primary.resident_type,
        "is_committee": bool(committee),
        "committee_role": committee.designation if committee else None,
        "is_guard": bool(device),
        "guard_device": device.device_name if device else None,
        "flats": flats,
        "primary_flat": flats[0] if flats else None,
        "profiles": [
            {
                "flat": r.flat,
                "resident_type": r.resident_type,
                "name": r.name,
                "registration_status": r.registration_status,
                "mobile_no": r.mobile_no,
            }
            for r in records
        ],
    }


@frappe.whitelist()
@portal_api
def whois_flat(flat_number: str) -> dict:
    """Lookup public directory information for a flat."""
    flat = (flat_number or "").strip().upper()
    if not flat:
        return {"found": False, "message": "Flat number required"}

    owner = frappe.db.get_value("Owners", {"flat": flat, "active": 1}, ["owner_name", "flat"], as_dict=True)
    if owner:
        return {
            "found": True,
            "flat": owner.flat,
            "occupant_name": owner.owner_name,
            "type": "Owner Occupied"
        }

    return {"found": False, "message": f"No active registered resident found for {flat}"}
