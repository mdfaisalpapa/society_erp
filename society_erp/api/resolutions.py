import frappe
from frappe.utils import format_date
from society_erp.api.utils import portal_api

@frappe.whitelist()
@portal_api
def get_resolutions(limit: int = 10) -> dict:
    """Fetch published Board & AGM Resolutions with full details."""
    resolutions = frappe.get_all(
        "Board Resolution",
        fields=["name", "resolution_title", "status", "passed_date", "description", "category"],
        order_by="passed_date desc, creation desc",
        limit_page_length=int(limit)
    )

    lines = []
    for r in resolutions:
        p_date = format_date(r.passed_date, "dd-MM-yyyy") if r.passed_date else "-"
        lines.append(f"• 📜 *{r.resolution_title}* [Status: `{r.status}`]\n  Passed: {p_date} | Category: {r.category or 'General'}\n  _{r.description or 'No extra resolution text'}_")

    summary_text = "\n\n".join(lines) if lines else "No published Board or AGM Resolutions found."

    return {
        "resolutions": resolutions,
        "count": len(resolutions),
        "summary_text": summary_text
    }
