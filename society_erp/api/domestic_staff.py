import frappe
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api

@frappe.whitelist()
@portal_api
def get_my_staff(for_user: str = None) -> dict:
    """Fetch domestic staff (maids, cooks, drivers) linked to resident's flat with full details."""
    owners = get_verified_owner_records(user_override=for_user)
    flats = sorted({o.flat for o in owners if o.flat})

    if not flats:
        return {"staff": [], "count": 0, "summary_text": "No active flats found."}

    links = frappe.get_all(
        "Staff Flat Link",
        filters={"flat": ["in", flats]},
        fields=["parent", "flat"]
    )
    staff_ids = [l.parent for l in links if l.parent]

    staff_list = []
    if staff_ids:
        staff_list = frappe.get_all(
            "Domestic Staff",
            filters={"name": ["in", staff_ids], "status": "Active"},
            fields=["name", "staff_name", "role", "phone", "approval_status"],
            order_by="staff_name asc"
        )

    lines = []
    for s in staff_list:
        lines.append(f"• 🧹 *{s.staff_name}* ({s.role})\n  📞 `{s.phone or '-'}` | Status: `{s.approval_status}` | ID: #{s.name}")

    summary_text = "\n\n".join(lines) if lines else "No domestic staff currently linked to your flat."

    return {
        "staff": staff_list,
        "count": len(staff_list),
        "summary_text": summary_text
    }
