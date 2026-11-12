import frappe
from frappe.utils import format_date
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api

@frappe.whitelist()
@portal_api
def get_tenants(for_user=None):
    """List tenants associated with the logged-in owner's verified flats with full details."""

    owners = get_verified_owner_records(user_override=for_user)
    flats = sorted({o.flat for o in owners if o.flat})

    if not flats:
        return {"tenants": [], "count": 0, "summary_text": "No registered flats found."}

    tenants = frappe.get_all(
        "Tenants",
        filters={
            "flat": ["in", flats],
        },
        fields=[
            "name",
            "flat",
            "tenant_name",
            "mobile_no",
            "email",
            "start_date",
            "end_date",
            "active",
        ],
        order_by="active desc, start_date desc",
        limit_page_length=100,
    )

    lines = []
    for t in tenants:
        status = "Active" if t.active else "Past / Expired"
        s_date = format_date(t.start_date, "dd-MM-yyyy") if t.start_date else "-"
        e_date = format_date(t.end_date, "dd-MM-yyyy") if t.end_date else "Ongoing"
        lines.append(f"• 🏠 *{t.tenant_name}* (Status: `{status}`)\n  📞 `{t.mobile_no or '-'}` | ✉️ `{t.email or '-'}`\n  Lease Term: {s_date} to {e_date}")

    summary_text = "\n\n".join(lines) if lines else "No tenant leases registered on record."

    return {
        "tenants": tenants,
        "count": len(tenants),
        "summary_text": summary_text
    }
