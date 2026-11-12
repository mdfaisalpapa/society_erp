import frappe
from frappe.utils import format_date


def get_resident_info(user=None):
    user = user or frappe.session.user
    user_email = user.strip().lower()

    # Check tenant
    tenant = frappe.db.get_value(
        "Tenants",
        {"active": 1, "email": user_email},
        ["name", "flat", "tenant_name", "mobile_no", "email"],
        as_dict=True,
    )

    owner = None
    if not tenant:
        owners = frappe.get_all(
            "Owners",
            filters={"active": 1},
            fields=["name", "flat", "owner_name", "mobile_no", "email", "linked_user", "is_aoa_member"],
        )
        for o in owners:
            if (o.linked_user and o.linked_user.strip().lower() == user_email) or \
               (o.email and o.email.strip().lower() == user_email) or \
               (o.name == user):
                owner = o
                break

    resident = tenant or owner
    if not resident or not resident.flat:
        return None

    return {
        "doc": resident,
        "is_tenant": bool(tenant),
        "is_owner": bool(owner),
        "is_aoa_member": bool(owner and owner.get("is_aoa_member")),
        "flat": resident.flat,
        "name": resident.tenant_name if tenant else resident.owner_name,
        "type": "Tenant" if tenant else "Owner",
    }


def get_context(context):
    context.is_standalone = bool(frappe.form_dict.get("standalone"))
    if context.is_standalone:
        context.no_header = True
        context.no_sidebar = True

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/resident/notices"
        raise frappe.Redirect

    res = get_resident_info()
    if not res:
        context.not_a_resident = True
        return context

    context.not_a_resident = False
    context.flat_number = res["flat"]
    context.resident_name = res["name"]
    context.resident_type = res["type"]

    notices = frappe.get_all(
        "Society Notice",
        filters={"is_active": 1},
        fields=["name", "title", "content", "date", "posted_by", "creation"],
        order_by="date desc, creation desc",
        limit_page_length=50,
    )
    for n in notices:
        n["formatted_date"] = format_date(n.date) if n.date else "-"

    context.notices = notices
    return context
