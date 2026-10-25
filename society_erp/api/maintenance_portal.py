import base64
import re

import frappe
from frappe import _
from frappe.utils.file_manager import save_file


ACTIVE_STATUSES = {"Open", "Assigned", "Pending", "In Progress"}
RESOLVED_STATUSES = {"Resolved", "Closed"}
MAX_DESCRIPTION = 5000
MAX_COMMENT = 3000
MAX_FILE_BYTES = 5 * 1024 * 1024


def _resident():
    """Resolve the current login to one active owner or tenant record."""
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Please log in to access maintenance tickets."), frappe.PermissionError)

    email = user.strip().lower()

    # Email is used by the resident portal's existing profile flow.
    tenants = frappe.get_all(
        "Tenants",
        filters={"active": 1},
        fields=["name", "flat", "tenant_name", "email"],
        limit_page_length=0,
    )
    tenant = next((r for r in tenants if r.email and r.email.strip().lower() == email), None)
    if tenant and tenant.flat:
        return {"flat": tenant.flat, "name": tenant.tenant_name or user, "type": "Tenant"}

    owners = frappe.get_all(
        "Owners",
        filters={"active": 1},
        fields=["name", "flat", "owner_name", "email", "linked_user"],
        limit_page_length=0,
    )
    owner = next(
        (
            r for r in owners
            if r.flat and (
                (r.email and r.email.strip().lower() == email)
                or r.linked_user == user
                or r.name == user
            )
        ),
        None,
    )
    if owner:
        return {"flat": owner.flat, "name": owner.owner_name or user, "type": "Owner"}

    frappe.throw(_("Your account is not linked to an active registered flat."), frappe.PermissionError)


def _ticket_for_resident(ticket_name):
    if not ticket_name or not isinstance(ticket_name, str):
        frappe.throw(_("A valid ticket ID is required."), frappe.ValidationError)
    resident = _resident()
    if not frappe.db.exists("Maintenance Ticket", ticket_name):
        frappe.throw(_("Maintenance ticket not found."), frappe.DoesNotExistError)
    ticket = frappe.get_doc("Maintenance Ticket", ticket_name)
    if ticket.resident != resident["flat"]:
        frappe.throw(_("You are not authorised to access this ticket."), frappe.PermissionError)
    return resident, ticket


def _ticket_dict(doc):
    return {
        "name": doc.name,
        "resident": doc.resident,
        "category": doc.get("category"),
        "description": doc.get("description"),
        "status": doc.get("status"),
        "creation": str(doc.get("creation") or ""),
        "modified": str(doc.get("modified") or ""),
        "photo": doc.get("photo"),
        "resolution_remarks": doc.get("resolution_remarks"),
        "attachments": [
            {"name": f.name, "file_name": f.file_name, "file_url": f.file_url}
            for f in frappe.get_all(
                "File",
                filters={"attached_to_doctype": "Maintenance Ticket", "attached_to_name": doc.name},
                fields=["name", "file_name", "file_url"],
                order_by="creation asc",
                limit_page_length=100,
            )
        ],
    }


@frappe.whitelist()
def get_tickets(status="Active", start=0, page_length=10):
    resident = _resident()
    try:
        start = max(0, int(start))
        page_length = min(50, max(1, int(page_length)))
    except (TypeError, ValueError):
        frappe.throw(_("Invalid pagination values."))

    status = (status or "Active").strip()
    if status == "Active":
        statuses = sorted(ACTIVE_STATUSES)
    elif status == "Resolved":
        statuses = sorted(RESOLVED_STATUSES)
    elif status == "All":
        statuses = sorted(ACTIVE_STATUSES | RESOLVED_STATUSES)
    else:
        frappe.throw(_("Invalid ticket status filter."))

    names = frappe.get_all(
        "Maintenance Ticket",
        filters={"resident": resident["flat"], "status": ["in", statuses]},
        fields=["name"],
        order_by="creation desc",
        start=start,
        page_length=page_length,
    )
    tickets = []
    for row in names:
        doc = frappe.get_doc("Maintenance Ticket", row.name)
        tickets.append(_ticket_dict(doc))

    total = frappe.db.count(
        "Maintenance Ticket",
        filters={"resident": resident["flat"], "status": ["in", statuses]},
    )
    return {"tickets": tickets, "total": total, "start": start, "page_length": page_length}


@frappe.whitelist()
def create_ticket(category, description, photo_data=None, photo_name=None):
    resident = _resident()
    category = (category or "").strip()
    description = (description or "").strip()
    if not category:
        frappe.throw(_("Please select a category."))
    if not description or len(description) > MAX_DESCRIPTION:
        frappe.throw(_("Description is required and must be at most 5000 characters."))

    meta = frappe.get_meta("Maintenance Ticket")
    category_field = meta.get_field("category")
    allowed = [v.strip() for v in (category_field.options or "").splitlines() if v.strip()]
    if allowed and category not in allowed:
        frappe.throw(_("Invalid maintenance category."))

    doc = frappe.get_doc({
        "doctype": "Maintenance Ticket",
        "resident": resident["flat"],
        "category": category,
        "description": description,
        "status": "Open",
    })
    doc.insert(ignore_permissions=True)

    if photo_data:
        _save_image(doc, photo_data, photo_name or "maintenance-photo.jpg")

    return {"ticket": _ticket_dict(doc), "message": _("Maintenance ticket created.")}


def _save_image(doc, encoded_data, filename):
    if not isinstance(encoded_data, str):
        frappe.throw(_("Invalid image upload."))
    # Accept either raw base64 or a data URL.
    if "," in encoded_data and encoded_data.lstrip().startswith("data:"):
        header, encoded_data = encoded_data.split(",", 1)
        if "image/" not in header.lower():
            frappe.throw(_("Only image files are allowed."))
    try:
        content = base64.b64decode(encoded_data, validate=True)
    except Exception:
        frappe.throw(_("The uploaded image is invalid."))
    if not content or len(content) > MAX_FILE_BYTES:
        frappe.throw(_("Image must be smaller than 5 MB."))
    # Verify common image signatures rather than trusting the browser filename.
    if not (
        content.startswith(b"\xff\xd8\xff")
        or content.startswith(b"\x89PNG\r\n\x1a\n")
        or content.startswith((b"GIF87a", b"GIF89a"))
        or (content.startswith(b"RIFF") and content[8:12] == b"WEBP")
    ):
        frappe.throw(_("Please upload a valid JPG, PNG, GIF or WEBP image."))
    filename = re.sub(r"[^A-Za-z0-9._-]", "_", (filename or "photo.jpg"))[:120]
    save_file(filename, content, "Maintenance Ticket", doc.name, is_private=1)


@frappe.whitelist()
def get_ticket_details(ticket_name):
    resident, doc = _ticket_for_resident(ticket_name)
    comments = frappe.get_all(
        "Comment",
        filters={
            "reference_doctype": "Maintenance Ticket",
            "reference_name": doc.name,
            "comment_type": ["in", ["Comment", "Info"]],
        },
        fields=["name", "content", "comment_by", "creation"],
        order_by="creation asc",
        limit_page_length=200,
    )
    result = _ticket_dict(doc)
    result["comments"] = [
        {
            "name": c.name,
            "content": c.content,
            "comment_by": c.comment_by,
            "creation": str(c.creation or ""),
        }
        for c in comments
    ]
    return result


@frappe.whitelist()
def add_comment(ticket_name, comment):
    resident, doc = _ticket_for_resident(ticket_name)
    comment = (comment or "").strip()
    if not comment or len(comment) > MAX_COMMENT:
        frappe.throw(_("Comment is required and must be at most 3000 characters."))
    doc.add_comment("Comment", text=f"Resident ({resident['flat']}): {comment}")
    return {"message": _("Comment added."), "ticket": _ticket_dict(doc)}


@frappe.whitelist()
def close_ticket(ticket_name):
    resident, doc = _ticket_for_resident(ticket_name)
    if doc.status not in ACTIVE_STATUSES:
        frappe.throw(_("Only active tickets can be marked resolved."))
    doc.status = "Resolved"
    doc.save(ignore_permissions=True)
    doc.add_comment("Comment", text=f"Resident ({resident['flat']}) marked this ticket as resolved.")
    return {"message": _("Ticket marked as resolved."), "ticket": _ticket_dict(doc)}


@frappe.whitelist()
def reopen_ticket(ticket_name, reason):
    resident, doc = _ticket_for_resident(ticket_name)
    reason = (reason or "").strip()
    if not reason or len(reason) > MAX_COMMENT:
        frappe.throw(_("A reopening reason is required (maximum 3000 characters)."))
    if doc.status not in RESOLVED_STATUSES:
        frappe.throw(_("Only resolved or closed tickets can be reopened."))
    doc.status = "Open"
    doc.save(ignore_permissions=True)
    doc.add_comment("Comment", text=f"Resident ({resident['flat']}) reopened this ticket. Reason: {reason}")
    return {"message": _("Ticket reopened."), "ticket": _ticket_dict(doc)}


@frappe.whitelist()
def add_photo(ticket_name, photo_data, photo_name=None):
    resident, doc = _ticket_for_resident(ticket_name)
    if doc.status not in ACTIVE_STATUSES:
        frappe.throw(_("Photos can only be added to active tickets."))
    _save_image(doc, photo_data, photo_name or "maintenance-photo.jpg")
    return {"message": _("Photo attached."), "ticket": _ticket_dict(doc)}
