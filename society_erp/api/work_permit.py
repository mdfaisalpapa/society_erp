import frappe
from frappe.utils import format_date
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api

@frappe.whitelist()
@portal_api
def get_work_permits(for_user: str = None) -> dict:
    """Fetch active work permits and contractor passes with full schedule details."""
    owners = get_verified_owner_records(user_override=for_user)
    flats = sorted({o.flat for o in owners if o.flat})

    if not flats:
        return {"permits": [], "count": 0, "summary_text": "No active flats found."}

    permits = frappe.get_all(
        "Work Permit",
        filters={"flat_number": ["in", flats]},
        fields=["name", "contractor_name", "work_type", "start_date", "end_date", "status"],
        order_by="creation desc",
        limit_page_length=20
    )

    lines = []
    for p in permits:
        s_date = format_date(p.start_date, "dd-MM-yyyy") if p.start_date else "-"
        e_date = format_date(p.end_date, "dd-MM-yyyy") if p.end_date else "-"
        lines.append(f"• *{p.work_type}* (Contractor: {p.contractor_name})\n  Dates: {s_date} to {e_date} | Status: `{p.status}`\n  Permit No: #{p.name}")

    summary_text = "\n\n".join(lines) if lines else "No renovation or work permits currently logged for your flat."

    return {
        "permits": permits,
        "count": len(permits),
        "summary_text": summary_text
    }
