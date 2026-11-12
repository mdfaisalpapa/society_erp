import frappe
from frappe.utils import flt, fmt_money
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api


@frappe.whitelist()
@portal_api
def get_flat_profile(for_user: str = None) -> dict:
    """
    Fetch comprehensive flat details, property tax, EB, UDS, and financial balances
    matching the Resident Portal Profile page (`/resident/profile`).
    """
    owners = get_verified_owner_records(user_override=for_user)
    if not owners:
        return {"found": False, "message": "No verified flat found"}

    primary = owners[0]
    flat_id = primary.flat

    # Customer specs
    flat_doc = frappe.get_doc("Customer", flat_id) if frappe.db.exists("Customer", flat_id) else None

    # Corpus fund ledger
    corpus_entries = frappe.get_all(
        "GL Entry",
        filters={
            "party_type": "Customer",
            "party": flat_id,
            "account": ["like", "Corpus Fund%"],
            "is_cancelled": 0,
        },
        fields=["debit", "credit"],
    )
    corpus_contribution = sum(flt(e.credit) - flt(e.debit) for e in corpus_entries)

    # Outstanding dues
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={"customer": flat_id, "docstatus": 1},
        fields=["outstanding_amount"],
    )
    outstanding_dues = sum(flt(inv.outstanding_amount) for inv in invoices)

    currency = frappe.db.get_default("currency") or "INR"

    return {
        "found": True,
        "flat": flat_id,
        "resident_name": primary.resident_name,
        "resident_type": primary.resident_type,
        "email": primary.email or for_user,
        "mobile_no": primary.mobile_no or "-",
        "block": flat_doc.get("custom_block") if flat_doc else "-",
        "uds": str(flat_doc.get("custom_uds")) if flat_doc and flat_doc.get("custom_uds") else "-",
        "eb_service_no": (flat_doc.get("eb_service_no") or flat_doc.get("custom_eb_service_no") or "-") if flat_doc else "-",
        "property_tax_no": (flat_doc.get("property_tax_no") or flat_doc.get("custom_property_tax_no") or "-") if flat_doc else "-",
        "corpus_contribution": corpus_contribution,
        "formatted_corpus": fmt_money(corpus_contribution, currency=currency),
        "outstanding_dues": outstanding_dues,
        "formatted_dues": fmt_money(outstanding_dues, currency=currency),
        "currency": currency
    }


@frappe.whitelist()
@portal_api
def get_ownership_history(for_user: str = None) -> dict:
    """
    Fetch current and historical ownership records matching `/resident/owners`.
    """
    owners = get_verified_owner_records(user_override=for_user)
    if not owners:
        return {"current_owner": None, "history": [], "count": 0}

    flat_id = owners[0].flat

    all_owners = frappe.get_all(
        "Owners",
        filters={"flat": flat_id},
        fields=["name", "owner_name", "mobile_no", "email", "active", "start_date", "end_date", "sale_deed"],
        order_by="start_date desc, creation desc"
    )

    current = None
    previous = []
    for o in all_owners:
        item = {
            "name": o.owner_name,
            "mobile": o.mobile_no or "-",
            "email": o.email or "-",
            "active": bool(o.active),
            "start_date": str(o.start_date) if o.start_date else "-",
            "end_date": str(o.end_date) if o.end_date else "-"
        }
        if o.active == 1 and not current:
            current = item
        else:
            previous.append(item)

    return {
        "flat": flat_id,
        "current_owner": current,
        "previous_owners": previous,
        "total_records": len(all_owners)
    }
