import frappe
from frappe.utils import format_date
from society_erp.api.utils import portal_api

@frappe.whitelist()
@portal_api
def get_active_notices(limit: int = 5, limit_start: int = 0) -> dict:
    """
    Retrieve active society notices with complete circular content.
    """
    notices = frappe.get_all(
        "Society Notice",
        filters={"is_active": 1},
        fields=["name", "title", "content", "date", "posted_by"],
        order_by="date desc, creation desc",
        limit_page_length=int(limit),
        limit_start=int(limit_start)
    )

    summary_list = []
    lines = []
    for n in notices:
        f_date = format_date(n.date, "dd-MM-yyyy") if n.date else "-"
        summary_list.append({
            "id": n.name,
            "title": n.title,
            "date": f_date,
            "content": n.content or "",
            "posted_by": n.posted_by or "Association Office"
        })
        lines.append(f"• 📋 *{n.title}* ({f_date})\n  By: _{n.posted_by or 'AoA Office'}_\n  {n.content or ''}")

    summary_text = "\n\n".join(lines) if lines else "No active society circulars posted."

    return {
        "count": len(summary_list),
        "notices": summary_list,
        "summary_text": summary_text
    }
