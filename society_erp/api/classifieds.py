import frappe
from frappe.utils import format_date, fmt_money
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api


@frappe.whitelist()
@portal_api
def get_classifieds(for_user: str = None, category: str = None) -> dict:
    """
    Fetch approved active classifieds to browse and user's posted listings with complete details.
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

    ad_lines = []
    for ad in approved_ads:
        ad["formatted_date"] = format_date(ad.creation, "dd-MM-yyyy")
        ad["formatted_price"] = f"{currency} {fmt_money(ad.price)}" if ad.price else "Negotiable / Free"
        contact_info = f"Flat: {ad.resident}" + (f" | 📞 {ad.contact_phone}" if ad.contact_phone else "")
        ad_lines.append(f"• *{ad.title}* [{ad.listing_type} - {ad.category}]\n  Price: *{ad['formatted_price']}*\n  {contact_info}\n  _{ad.description or 'No extra details'}_")

    # My classifieds
    my_ads = []
    my_lines = []
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
            my_lines.append(f"• *{ma.title}*: Status `{ma.approval_status}` / `{ma.status}`")

    ads_summary = "\n\n".join(ad_lines) if ad_lines else "No active marketplace listings currently."
    my_summary = "\n".join(my_lines) if my_lines else "You have not posted any classified listings yet."

    return {
        "ads": approved_ads,
        "count": len(approved_ads),
        "my_ads": my_ads,
        "my_count": len(my_ads),
        "ads_summary": ads_summary,
        "my_summary": my_summary
    }
