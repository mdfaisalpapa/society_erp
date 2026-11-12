import frappe
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api

@frappe.whitelist()
@portal_api
def get_vehicles(for_user=None):
    """List vehicles associated with the logged-in owner's verified flats with full details."""

    owners = get_verified_owner_records(user_override=for_user)
    owner_names = [o.name for o in owners]
    flats = sorted({o.flat for o in owners if o.flat})

    if not flats:
        return {"vehicles": [], "count": 0, "summary_text": "No registered flats found."}

    vehicles = frappe.get_all(
        "Resident Vehicle",
        filters={
            "flat": ["in", flats],
            "owner_reference": ["in", owner_names],
        },
        fields=[
            "name",
            "flat",
            "vehicle_type",
            "registration_number",
            "registered_owner_name",
            "relationship_to_resident",
            "make",
            "model",
            "color",
            "is_electric",
            "active",
            "approval_status",
            "parking_slot"
        ],
        order_by="creation desc",
        limit_page_length=100,
    )

    lines = []
    for v in vehicles:
        ev = "⚡ EV" if v.is_electric else ""
        slot = f"Slot: {v.parking_slot}" if v.parking_slot else "No Dedicated Slot"
        lines.append(f"• 🚗 *{v.vehicle_type}*: `{v.registration_number}` {ev}\n  {v.make or ''} {v.model or ''} ({v.color or ''})\n  Owner: {v.registered_owner_name} ({v.relationship_to_resident})\n  Status: `{v.approval_status}` | {slot}")

    summary_text = "\n\n".join(lines) if lines else "No registered vehicles on record for your flat."

    return {
        "vehicles": vehicles,
        "count": len(vehicles),
        "summary_text": summary_text
    }
