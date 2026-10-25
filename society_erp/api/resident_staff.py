import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from society_erp.api.resident_family import _current_resident


APPROVAL_ROLE = "Estate Office Maintenance"


def _get_resident():
    """Resolve the authenticated resident and their authorised flat."""
    return _current_resident()


def _require_estate_office():
    """Only Estate Office Maintenance users may approve or reject staff."""
    user = frappe.session.user
    roles = frappe.get_roles(user)

    if user != "Administrator" and APPROVAL_ROLE not in roles:
        frappe.throw(
            _("Only users with the {0} role can approve or reject domestic staff.")
            .format(APPROVAL_ROLE),
            frappe.PermissionError,
        )


def _get_staff_doc(staff_id, require_approved=True):
    if not staff_id:
        frappe.throw(_("Please select a staff member."))

    doc = frappe.get_doc("Domestic Staff", staff_id)

    if doc.status != "Active":
        frappe.throw(_("Only active staff can be linked to a flat."))

    if require_approved and doc.approval_status != "Approved":
        frappe.throw(
            _("Only staff approved by the Estate Office can be linked to a flat.")
        )

    return doc


def _find_link(doc, flat):
    return next(
        (row for row in doc.linked_flats if row.flat == flat),
        None,
    )


@frappe.whitelist()
def get_linkable_staff():
    """List approved, active staff not already linked to this flat."""
    resident = _get_resident()
    flat = resident["flat"]

    staff_records = frappe.get_all(
        "Domestic Staff",
        filters={
            "status": "Active",
            "approval_status": "Approved",
        },
        fields=["name", "staff_name", "role", "phone"],
        order_by="staff_name asc",
        limit_page_length=1000,
    )

    result = []

    for staff in staff_records:
        link = frappe.db.get_value(
            "Staff Flat Link",
            {
                "parent": staff.name,
                "parenttype": "Domestic Staff",
                "parentfield": "linked_flats",
                "flat": flat,
                "is_active": 1,
            },
            "name",
        )

        if not link:
            result.append(staff)

    return result


@frappe.whitelist(methods=["POST"])
def link_existing_staff(staff_id):
    """Link approved staff to the authenticated resident's own flat."""
    resident = _get_resident()
    flat = resident["flat"]

    doc = _get_staff_doc(staff_id, require_approved=True)

    existing = _find_link(doc, flat)

    if existing:
        if cint(existing.is_active):
            frappe.throw(_("This staff member is already linked to your flat."))
        existing.is_active = 1
    else:
        doc.append("linked_flats", {
            "flat": flat,
            "is_active": 1,
        })

    # Flat identity is resolved from the authenticated resident, never
    # accepted from a client-supplied flat parameter.
    doc.save(ignore_permissions=True)

    return {"message": _("Staff linked to your flat successfully.")}


@frappe.whitelist(methods=["POST"])
def unlink_staff(staff_id):
    """Deactivate only the link to the authenticated resident's own flat."""
    resident = _get_resident()
    flat = resident["flat"]

    if not staff_id:
        frappe.throw(_("Please select a staff member."))

    doc = frappe.get_doc("Domestic Staff", staff_id)
    link = _find_link(doc, flat)

    if not link or not cint(link.is_active):
        frappe.throw(
            _("This staff member does not have an active link to your flat."),
            frappe.PermissionError,
        )

    link.is_active = 0
    doc.save(ignore_permissions=True)

    return {"message": _("Staff unlinked from your flat successfully.")}


@frappe.whitelist(methods=["POST"])
def approve_staff(staff_id, remarks=None):
    """Approve a staff registration. Estate Office role required."""
    _require_estate_office()

    if not staff_id:
        frappe.throw(_("Please select a staff member."))

    doc = frappe.get_doc("Domestic Staff", staff_id)

    if doc.approval_status == "Approved":
        frappe.throw(_("This staff member is already approved."))

    if doc.status != "Active":
        frappe.throw(_("Only active staff can be approved."))

    doc.approval_status = "Approved"
    doc.approved_by = frappe.session.user
    doc.approval_date = now_datetime()

    if remarks is not None:
        doc.approval_remarks = remarks

    doc.save(ignore_permissions=True)

    return {"message": _("Domestic staff registration approved.")}


@frappe.whitelist(methods=["POST"])
def reject_staff(staff_id, remarks=None):
    """Reject a staff registration. Estate Office role required."""
    _require_estate_office()

    if not staff_id:
        frappe.throw(_("Please select a staff member."))

    doc = frappe.get_doc("Domestic Staff", staff_id)

    if doc.approval_status == "Approved":
        frappe.throw(
            _("This staff member is already approved. Contact the administrator if a status change is needed.")
        )

    doc.approval_status = "Rejected"
    doc.approved_by = None
    doc.approval_date = now_datetime()

    if remarks is not None:
        doc.approval_remarks = remarks

    doc.save(ignore_permissions=True)

    return {"message": _("Domestic staff registration rejected.")}


@frappe.whitelist()
def get_pending_staff_approvals():
    """List pending registrations for Estate Office users only."""
    _require_estate_office()

    return frappe.get_all(
        "Domestic Staff",
        filters={"approval_status": "Pending Approval"},
        fields=[
            "name",
            "staff_name",
            "role",
            "phone",
            "status",
            "approval_status",
        ],
        order_by="creation asc",
        limit_page_length=1000,
    )
@frappe.whitelist(methods=["POST"])
def register_staff(staff_name, role, phone):
    """Register domestic staff for review by the Estate Office."""

    resident = _get_resident()

    staff_name = (staff_name or "").strip()
    phone = (phone or "").strip()

    allowed_roles = {"Maid", "Driver", "Cook", "Nanny"}

    if not staff_name:
        frappe.throw(_("Please enter the staff member's name."))

    if not role or role not in allowed_roles:
        frappe.throw(_("Please select a valid staff role."))

    if not phone:
        frappe.throw(_("Please enter a contact number."))

    # Do not accept a flat number from the browser.
    # The resident's authorised flat is resolved server-side.
    doc = frappe.new_doc("Domestic Staff")
    doc.staff_name = staff_name
    doc.role = role
    doc.phone = phone
    doc.status = "Active"
    doc.approval_status = "Pending Approval"

    # Let Frappe's document lifecycle generate the configured name.
    # No active flat link is created until the staff is approved and linked.
    doc.insert(ignore_permissions=True)

    return {
        "name": doc.name,
        "staff_name": doc.staff_name,
        "approval_status": doc.approval_status,
        "message": _("Registration submitted for Estate Office approval."),
    }
