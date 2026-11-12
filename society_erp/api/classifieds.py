import frappe
from frappe.utils import format_date, fmt_money
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api


@frappe.whitelist()
@portal_api
def get_classifieds(for_user: str = None, category: str = None) -> dict:
    """
    Fetch approved active classifieds to browse and user's posted listings.
    """
    owners = get_verified_owner_records(user_override=for_user)
    flats = sorted({o.flat for o in owners if o.flat})

    currency = frappe.db.get_default("currency") or "INR"

    filters = {"approval_status": "Approved", "status": "Active"}
    if category:
        filters["category"] = category

    approved_ads = frappe.get_all(
        "Resident Classified",
        filters=filters,
        fields=[
            "name", "title", "category", "listing_type", "price",
            "resident", "contact_person", "contact_phone", "description", "creation"
        ],
        order_by="creation desc",
        limit_page_length=20,
    )

    for ad in approved_ads:
        ad["formatted_date"] = format_date(ad.creation, "dd-MM-yyyy")
        ad["formatted_price"] = f"{currency} {fmt_money(ad.price)}" if ad.price else "Negotiable / Free"

    # My classifieds
    my_ads = []
    if flats:
        my_ads = frappe.get_all(
            "Resident Classified",
            filters={"resident": ["in", flats]},
            fields=[
                "name", "title", "category", "listing_type", "price",
                "approval_status", "status", "creation"
            ],
            order_by="creation desc",
            limit_page_length=10,
        )
        for ma in my_ads:
            ma["formatted_date"] = format_date(ma.creation, "dd-MM-yyyy")

    return {
        "ads": approved_ads,
        "count": len(approved_ads),
        "my_ads": my_ads,
        "my_count": len(my_ads),
        "primary_ad": approved_ads[0] if approved_ads else None
    }
