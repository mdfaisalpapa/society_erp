import frappe
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api

@frappe.whitelist()
@portal_api
def get_work_permits(for_user: str = None) -> dict:
    """Fetch active work permits and contractor passes."""
    owners = get_verified_owner_records(user_override=for_user)
    flats = sorted({o.flat for o in owners if o.flat})

    if not flats:
        return {"permits": [], "count": 0}

    permits = frappe.get_all(
        "Work Permit",
        filters={"flat_number": ["in", flats]},
        fields=["name", "contractor_name", "work_type", "start_date", "end_date", "status"],
        order_by="creation desc",
        limit_page_length=20
    )

    return {
        "permits": permits,
        "count": len(permits)
    }
