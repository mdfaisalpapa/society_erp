import frappe
from society_erp.api.utils import portal_api

@frappe.whitelist()
@portal_api
def get_resolutions(limit: int = 5) -> dict:
    """Fetch published Board & AGM Resolutions."""
    resolutions = frappe.get_all(
        "Board Resolution",
        fields=["name", "resolution_title", "status"],
        order_by="creation desc",
        limit_page_length=int(limit)
    )

    return {
        "resolutions": resolutions,
        "count": len(resolutions)
    }
