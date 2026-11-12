import frappe
from frappe.utils import format_date
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api


@frappe.whitelist()
@portal_api
def get_pets(for_user: str = None) -> dict:
    """
    Fetch registered pets for the verified resident flat(s).
    """
    owners = get_verified_owner_records(user_override=for_user)
    flats = sorted({o.flat for o in owners if o.flat})

    if not flats:
        return {"pets": [], "count": 0}

    pets = frappe.get_all(
        "Resident Pets",
        filters={"flat": ["in", flats]},
        fields=[
            "name", "pet_name", "license_no", "license_expiry_date",
            "vaccination_certificate_no", "vaccination_due_date",
            "approval_status", "belongs_to", "creation"
        ],
        order_by="creation desc",
        limit_page_length=20,
    )

    for p in pets:
        p["formatted_lic_expiry"] = format_date(p.license_expiry_date, "dd-MM-yyyy") if p.license_expiry_date else "-"
        p["formatted_vac_due"] = format_date(p.vaccination_due_date, "dd-MM-yyyy") if p.vaccination_due_date else "-"

    return {
        "pets": pets,
        "count": len(pets),
        "primary_pet": pets[0] if pets else None
    }
