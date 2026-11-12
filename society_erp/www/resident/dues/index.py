import frappe
from frappe import _
from frappe.utils import flt, fmt_money, format_date


def get_context(context):
    context.is_standalone = bool(frappe.form_dict.get("standalone"))
    if context.is_standalone:
        context.no_header = True
        context.no_sidebar = True

    """
    Backend context handler for the 'My Dues' resident portal page.
    - Secures against guest access.
    - Identifies the resident's active flat (Customer) via Owners/Tenants logic.
    - Queries submitted Sales Invoices linked to the flat.
    - Computes total outstanding dues and formats amounts for display.
    """
    # 1. Require authentication - secure against guest access
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    user = frappe.session.user
    user_email = (user or "").strip().lower()

    # 2. Identify the logged-in resident's active flat
    resident = None
    resident_type = None

    # Check active Tenants first
    tenant_records = frappe.get_all(
        "Tenants",
        filters={"active": 1},
        fields=[
            "name",
            "flat",
            "tenant_name",
            "email",
            "mobile_no",
        ],
        order_by="flat asc",
    )
    for record in tenant_records:
        if record.email and record.email.strip().lower() == user_email:
            resident = record
            resident_type = "Tenant"
            resident.resident_name = record.tenant_name
            break

    # If not found as Tenant, check active Owners
    if not resident:
        owner_records = frappe.get_all(
            "Owners",
            filters={"active": 1},
            fields=[
                "name",
                "flat",
                "owner_name",
                "email",
                "mobile_no",
            ],
            order_by="flat asc",
        )
        for record in owner_records:
            if (
                record.email and record.email.strip().lower() == user_email
            ) or record.name == user:
                resident = record
                resident_type = "Owner"
                resident.resident_name = record.owner_name
                break

    # Fallback to resident_portal helper if available
    if not resident:
        try:
            from society_erp.resident_portal import get_verified_owner_records

            records = get_verified_owner_records()
            if records:
                resident = records[0]
                resident_type = getattr(resident, "resident_type", "Owner")
                resident.resident_name = getattr(
                    resident, "resident_name", getattr(resident, "owner_name", "")
                )
        except Exception:
            pass

    # If user is not linked to any active flat, flag for template
    if not resident or not resident.flat:
        context.not_a_resident = True
        return context

    flat_id = resident.flat
    context.not_a_resident = False
    context.flat_number = flat_id
    context.resident_name = getattr(resident, "resident_name", "")
    context.resident_type = resident_type
    context.title = _("My Dues — Flat {0}").format(flat_id)

    # 3. Retrieve system currency
    currency = frappe.db.get_default("currency") or "INR"
    context.currency = currency

    # 4. Query Sales Invoices raised against the resident's Flat (Customer)
    # Submitted invoices (docstatus=1) represent actual posted financial obligations
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={
            "customer": flat_id,
            "docstatus": 1,
        },
        fields=[
            "name",
            "posting_date",
            "due_date",
            "grand_total",
            "outstanding_amount",
            "status",
        ],
        order_by="posting_date desc, creation desc",
    )

    # 5. Calculate total outstanding balance and format invoice records
    total_outstanding = 0.0
    for inv in invoices:
        outstanding = flt(inv.outstanding_amount)
        total_outstanding += outstanding

        # Helper formatted fields for clean Jinja rendering
        inv.formatted_grand_total = fmt_money(inv.grand_total, currency=currency)
        inv.formatted_outstanding = fmt_money(outstanding, currency=currency)
        inv.formatted_posting_date = (
            format_date(inv.posting_date) if inv.posting_date else "-"
        )
        inv.formatted_due_date = (
            format_date(inv.due_date) if inv.due_date else "-"
        )

    context.invoices = invoices
    context.total_outstanding = total_outstanding
    context.formatted_total_outstanding = fmt_money(
        total_outstanding, currency=currency
    )

    return context
