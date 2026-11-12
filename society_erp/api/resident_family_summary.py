import frappe
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api

@frappe.whitelist()
@portal_api
def get_family_members(for_user: str = None) -> dict:
    """
    Fetch registered family members for the resident's flat with full details.
    """
    owners = get_verified_owner_records(user_override=for_user)
    flats = sorted({o.flat for o in owners if o.flat})

    if not flats:
        return {"members": [], "count": 0, "summary_text": "No registered flats found."}

    members = frappe.get_all(
        "Family Members",
        filters={"flat": ["in", flats]},
        fields=["name", "member_name", "relationship", "mobile_no", "status", "registration_status"],
        order_by="creation asc"
    )

    lines = []
    for m in members:
        lines.append(f"• 👨‍👩‍👧 *{m.member_name}* ({m.relationship})\n  📞 `{m.mobile_no or '-'}` | Status: `{m.get('registration_status') or m.status}`")

    summary_text = "\n\n".join(lines) if lines else "No family members currently registered."

    return {
        "members": members,
        "count": len(members),
        "summary_text": summary_text
    }
