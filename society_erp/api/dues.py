import frappe
from frappe.utils import format_date, fmt_money, flt
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api

@frappe.whitelist()
@portal_api
def get_flat_dues(for_user: str = None) -> dict:
    """
    Fetch outstanding dues and submitted sales invoices with detailed ledger listing.
    """
    owners = get_verified_owner_records(user_override=for_user)
    flats = sorted({o.flat for o in owners if o.flat})

    if not flats:
        return {
            "flats": [],
            "outstanding_balance": 0.0,
            "currency": frappe.db.get_default("currency") or "INR",
            "invoices": [],
            "summary_text": "No registered flat found."
        }

    currency = frappe.db.get_default("currency") or "INR"

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
        limit_page_length=20,
    )

    total_outstanding = 0.0
    invoice_list = []
    lines = []

    for inv in invoices:
        outstanding = flt(inv.outstanding_amount)
        total_outstanding += outstanding
        p_date = format_date(inv.posting_date, "dd-MM-yyyy") if inv.posting_date else "-"
        d_date = format_date(inv.due_date, "dd-MM-yyyy") if inv.due_date else "-"
        f_total = fmt_money(inv.grand_total, currency=currency)
        f_out = fmt_money(outstanding, currency=currency)

        invoice_list.append({
            "name": inv.name,
            "flat": inv.customer,
            "posting_date": str(inv.posting_date or ""),
            "due_date": str(inv.due_date or ""),
            "grand_total": flt(inv.grand_total),
            "outstanding_amount": outstanding,
            "status": inv.status,
            "formatted_grand_total": f_total,
            "formatted_outstanding": f_out,
            "formatted_posting_date": p_date,
            "formatted_due_date": d_date,
        })
        lines.append(f"• 📄 *{inv.name}* (Due: {d_date})\n  Total: {f_total} | Outstanding: *{f_out}* | Status: `{inv.status}`")

    primary_flat = flats[0] if len(flats) == 1 else None
    f_total_outstanding = fmt_money(total_outstanding, currency=currency)

    summary_text = f"• *Total Outstanding Balance:* *{f_total_outstanding}*\n• *Invoices on Record:* {len(invoice_list)}\n\n"
    summary_text += ("*Recent Invoices:*\n" + "\n\n".join(lines[:6])) if lines else "No maintenance invoices pending."

    return {
        "flat": primary_flat or flats,
        "flats": flats,
        "outstanding_balance": round(total_outstanding, 2),
        "currency": currency,
        "formatted_outstanding_balance": f_total_outstanding,
        "invoice_count": len(invoice_list),
        "invoices": invoice_list,
        "summary_text": summary_text
    }
