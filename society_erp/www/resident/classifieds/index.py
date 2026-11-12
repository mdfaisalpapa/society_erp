import frappe
from frappe import _
from frappe.utils import format_date, today
from society_erp.www.resident.notices.index import get_resident_info


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    res_info = get_resident_info()
    if not res_info:
        context.not_a_resident = True
        return context

    context.not_a_resident = False
    context.resident_info = res_info
    context.flat_number = res_info.get("flat")
    context.today_date = today()
    flat = res_info.get("flat")

    # Fetch active approved classifieds for all residents to browse
    approved_ads = frappe.get_all(
        "Resident Classified",
        filters={"approval_status": "Approved", "status": "Active"},
        fields=[
            "name",
            "title",
            "category",
            "listing_type",
            "price",
            "resident",
            "contact_person",
            "contact_phone",
            "description",
            "image",
            "creation",
        ],
        order_by="creation desc",
        limit_page_length=100,
    )
    for ad in approved_ads:
        ad["formatted_date"] = format_date(ad.creation, "dd-MM-yyyy")

    context.approved_ads = approved_ads

    # Fetch ads posted by current resident (including pending/rejected)
    my_ads = frappe.get_all(
        "Resident Classified",
        filters={"resident": flat},
        fields=[
            "name",
            "title",
            "category",
            "listing_type",
            "price",
            "approval_status",
            "status",
            "committee_remarks",
            "creation",
        ],
        order_by="creation desc",
        limit_page_length=50,
    )
    for ma in my_ads:
        ma["formatted_date"] = format_date(ma.creation, "dd-MM-yyyy")

    context.my_ads = my_ads
    return context


@frappe.whitelist()
def post_classified(title, category, listing_type, price=None, description=None, contact_person=None, contact_phone=None):
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to post a classified."), frappe.PermissionError)

    res_info = get_resident_info()
    if not res_info or not res_info.get("flat"):
        frappe.throw(_("No verified flat linked to your account."), frappe.PermissionError)

    flat = res_info.get("flat")
    title = (title or "").strip()
    if not title:
        frappe.throw(_("Ad Title is required."))
    if not description:
        frappe.throw(_("Description is required."))

    doc = frappe.get_doc({
        "doctype": "Resident Classified",
        "title": title,
        "category": category or "Others",
        "listing_type": listing_type or "Sell Item",
        "price": float(price) if price else 0,
        "resident": flat,
        "contact_person": (contact_person or res_info.get("resident_name") or "").strip(),
        "contact_phone": (contact_phone or res_info.get("mobile_no") or "").strip(),
        "approval_status": "Pending Approval",
        "status": "Active",
        "description": description.strip(),
    })
    doc.insert(ignore_permissions=True)

    return {
        "status": "success",
        "message": _("Classified ad posted successfully! It will be published once approved by the Managing Committee."),
        "ad_id": doc.name,
    }


@frappe.whitelist()
def close_classified(ad_id):
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login."), frappe.PermissionError)

    res_info = get_resident_info()
    if not res_info or not res_info.get("flat"):
        frappe.throw(_("No verified flat linked."), frappe.PermissionError)

    flat = res_info.get("flat")
    if not frappe.db.exists("Resident Classified", ad_id):
        frappe.throw(_("Ad not found."))

    doc = frappe.get_doc("Resident Classified", ad_id)
    if doc.resident != flat:
        frappe.throw(_("Unauthorized."), frappe.PermissionError)

    doc.db_set("status", "Closed")
    return {
        "status": "success",
        "message": _("Classified ad marked as closed."),
    }
