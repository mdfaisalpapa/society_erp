import frappe
from society_erp.api.utils import portal_api

@frappe.whitelist()
@portal_api
def get_active_notices(limit: int = 5, limit_start: int = 0) -> dict:
    """
    Retrieve active society notices for residents.
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
    for n in notices:
        summary_list.append({
            "id": n.name,
            "title": n.title,
            "date": frappe.utils.format_date(n.date) if n.date else "",
            "content": n.content or "",
            "posted_by": n.posted_by or "Association Office"
        })

    return {
        "count": len(summary_list),
        "notices": summary_list
    }
