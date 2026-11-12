import frappe
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api

@frappe.whitelist()
@portal_api
def get_my_parking_slots(for_user: str = None) -> dict:
    """
    Fetch parking slots owned or occupied by the resident.
    """
    owners = get_verified_owner_records(user_override=for_user)
    flats = sorted({o.flat for o in owners if o.flat})

    if not flats:
        return {"slots": []}

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

    return {
        "slots": slots,
        "count": len(slots),
        "primary_slot": slots[0]["slot_number"] if slots else "None Allotted"
    }
