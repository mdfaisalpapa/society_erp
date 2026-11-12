import frappe
from frappe.utils import format_date
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api

@frappe.whitelist()
@portal_api
def get_recent_visitors(for_user: str = None) -> dict:
    """
    Fetch recent visitor history and logs with complete details matching `/resident/visitors`.
    """
    owners = get_verified_owner_records(user_override=for_user)
    flats = sorted({o.flat for o in owners if o.flat})

    if not flats:
        return {"visitors": [], "count": 0, "summary_text": "No registered flats found."}

    visitors = frappe.get_all(
        "Visitor Log",
        filters={"resident": ["in", flats]},
        fields=["name", "visitor_name", "entry_type", "purpose", "expected_date", "status", "in_time", "out_time", "passcode"],
        order_by="creation desc",
        limit_page_length=15
    )

    lines = []
    for v in visitors:
        v_date = format_date(v.expected_date, "dd-MM-yyyy") if v.expected_date else "-"
        in_t = str(v.in_time).split(".")[0] if v.in_time else "Not Checked-In"
        out_t = str(v.out_time).split(".")[0] if v.out_time else "-"
        lines.append(f"• 🎫 *{v.visitor_name or 'Guest'}* ({v.entry_type or v.purpose or 'General'})\n  Date: {v_date} | Status: `{v.status}` | Passcode: `{v.passcode or '-'}`\n  In: {in_t} | Out: {out_t}")

    summary_text = "\n\n".join(lines) if lines else "No visitor logs recorded recently."

    return {
        "visitors": visitors,
        "count": len(visitors),
        "primary_visitor": visitors[0] if visitors else None,
        "summary_text": summary_text
    }
