import frappe
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api

@frappe.whitelist()
@portal_api
def get_my_parking_slots(for_user: str = None) -> dict:
    """
    Fetch parking slots owned or occupied by the resident with complete summary.
    """
    owners = get_verified_owner_records(user_override=for_user)
    flats = sorted({o.flat for o in owners if o.flat})

    if not flats:
        return {"slots": [], "count": 0, "summary_text": "No registered flats found."}

    slots = frappe.get_all(
        "Parking Slot",
        filters={
            "owned_by": ["in", flats]
        },
        fields=[
            "name",
            "slot_number",
            "slot_type",
            "ownership_status",
            "current_status",
            "owned_by",
            "currently_occupied_by"
        ],
        order_by="slot_number asc"
    )

    lines = []
    for s in slots:
        lines.append(
            f"• 🅿️ *Slot `{s.slot_number}`* ({s.slot_type})\n"
            f"  Status: `{s.current_status}` | Allocation: `{s.ownership_status}`\n"
            f"  Occupant: {s.currently_occupied_by or s.owned_by}"
        )

    summary_text = "\n\n".join(lines) if lines else "No designated parking slots allotted to your flat."

    return {
        "slots": slots,
        "count": len(slots),
        "primary_slot": slots[0]["slot_number"] if slots else "None Allotted",
        "summary_text": summary_text
    }


# Backwards compatibility alias
get_parking_summary = get_my_parking_slots
