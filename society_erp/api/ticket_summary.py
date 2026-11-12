import frappe
from frappe.utils import format_date
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api

@frappe.whitelist()
@portal_api
def get_resident_tickets_summary(for_user: str = None) -> dict:
    """Fetch complete ticket records and status tracking for the resident's flat."""
    owners = get_verified_owner_records(user_override=for_user)
    flats = sorted({o.flat for o in owners if o.flat})

    if not flats:
        return {"tickets": [], "count": 0, "summary_text": "No registered flats found."}

    tickets = frappe.get_all(
        "Maintenance Ticket",
        filters={"resident": ["in", flats]},
        fields=["name", "category", "priority_level", "status", "creation", "description", "resolution_remarks"],
        order_by="creation desc",
        limit_page_length=20
    )

    lines = []
    for t in tickets:
        c_date = format_date(t.creation, "dd-MM-yyyy") if t.creation else "-"
        p_desc = (t.description[:80] + "...") if t.description and len(t.description) > 80 else (t.description or "No description")
        res_note = f"\n  Resolution: _{t.resolution_remarks}_" if t.resolution_remarks else ""
        lines.append(f"• 🛠️ *#{t.name}* [{t.category or 'General'}]\n  Priority: `{t.priority_level or 'Normal'}` | Status: `{t.status}` | Logged: {c_date}\n  _{p_desc}_{res_note}")

    summary_text = "\n\n".join(lines) if lines else "No maintenance complaints or service tickets on record."

    return {
        "tickets": tickets,
        "count": len(tickets),
        "summary_text": summary_text
    }
