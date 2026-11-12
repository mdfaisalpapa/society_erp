import frappe
from frappe import _
from frappe.utils import flt, fmt_money, format_date
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api


@frappe.whitelist()
@portal_api
def get_flat_dues(for_user: str = None) -> dict:
    """
    Fetch outstanding dues and submitted sales invoices for the verified flat(s).

    :param for_user: Optional email override for headless bot impersonation
    :return: dict with flat, outstanding_balance, currency, and invoice list
    """
    owners = get_verified_owner_records(user_override=for_user)
    flats = sorted({o.flat for o in owners if o.flat})

    if not flats:
        return {
            "flats": [],
            "outstanding_balance": 0.0,
            "currency": frappe.db.get_default("currency") or "INR",
            "invoices": [],
        }

    currency = frappe.db.get_default("currency") or "INR"

    # Query submitted Sales Invoices (docstatus=1) for all flats linked to this user
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={
            "customer": ["in", flats],
            "docstatus": 1,
        },
        fields=[
            "name",
            "customer",
            "posting_date",
            "due_date",
            "grand_total",
            "outstanding_amount",
            "status",
        ],
        order_by="posting_date desc, creation desc",
        limit_page_length=100,
    )

    total_outstanding = 0.0
    invoice_list = []

    for inv in invoices:
        outstanding = flt(inv.outstanding_amount)
        total_outstanding += outstanding

        invoice_list.append({
            "name": inv.name,
            "flat": inv.customer,
            "posting_date": str(inv.posting_date or ""),
            "due_date": str(inv.due_date or ""),
            "grand_total": flt(inv.grand_total),
            "outstanding_amount": outstanding,
            "status": inv.status,
            "formatted_grand_total": fmt_money(inv.grand_total, currency=currency),
            "formatted_outstanding": fmt_money(outstanding, currency=currency),
            "formatted_posting_date": format_date(inv.posting_date) if inv.posting_date else "-",
            "formatted_due_date": format_date(inv.due_date) if inv.due_date else "-",
        })

    primary_flat = flats[0] if len(flats) == 1 else None

    return {
        "flat": primary_flat or flats,
        "flats": flats,
        "outstanding_balance": round(total_outstanding, 2),
        "currency": currency,
        "formatted_outstanding_balance": fmt_money(total_outstanding, currency=currency),
        "invoice_count": len(invoice_list),
        "invoices": invoice_list,
    }
