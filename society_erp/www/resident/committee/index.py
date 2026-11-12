import frappe
from frappe import _
from frappe.utils import format_date, get_datetime, nowdate, today


def check_committee_access(user=None):
    """
    Verifies that the session user is an authorized Committee Member
    identified via Owners.is_aoa_member = 1 (or System Manager / Administrator).
    Returns (has_access: bool, committee_member_info: dict).
    """
    user = user or frappe.session.user
    if not user or user == "Guest":
        return False, None

    user_email = user.strip().lower()

    # 1. System Managers and Administrator
    roles = frappe.get_roles(user)
    if "System Manager" in roles or user == "Administrator":
        return True, {
            "name": user,
            "owner_name": "System Administrator",
            "is_admin": True,
            "flat": "Estate Office",
            "email": user_email,
        }

    # 2. Check active Owner record with is_aoa_member = 1
    owners = frappe.get_all(
        "Owners",
        filters={"active": 1, "is_aoa_member": 1},
        fields=["name", "flat", "owner_name", "email", "mobile_no", "linked_user"],
    )

    for o in owners:
        if (
            (o.linked_user and o.linked_user.strip().lower() == user_email)
            or (o.email and o.email.strip().lower() == user_email)
            or (o.name == user)
        ):
            return True, o

    return False, None


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/resident/committee"
        raise frappe.Redirect

    has_access, member_info = check_committee_access()
    if not has_access:
        context.access_denied = True
        context.title = _("Access Denied - Committee Portal")
        return context

    context.access_denied = False
    context.title = _("AoA Committee Member Portal")
    context.committee_member = member_info
    context.today_date = today()

    # Fetch count summaries
    context.counts = {
        "tenants_pending": frappe.db.count(
            "Tenants", {"registration_status": "Pending"}
        ),
        "vehicles_pending": frappe.db.count(
            "Resident Vehicle", {"approval_status": "Pending"}
        ),
        "permits_pending": frappe.db.count(
            "Work Permit", {"status": "Pending"}
        ),
        "pets_pending": frappe.db.count(
            "Resident Pets", {"approval_status": "Pending"}
        ),
        "family_pending": frappe.db.count(
            "Family Members", {"registration_status": "Pending"}
        ),
        "tickets_open": frappe.db.count(
            "Maintenance Ticket", {"status": "Open"}
        ),
        "notices_active": frappe.db.count(
            "Society Notice", {"is_active": 1}
        ),
    }

    return context


@frappe.whitelist()
def get_committee_data(module_type="all"):
    """
    API endpoint for Committee Members to load items across modules:
    - tenants
    - vehicles
    - work_permits
    - pets
    - family
    - notices
    - tickets
    """
    has_access, member_info = check_committee_access()
    if not has_access:
        frappe.throw(
            _("Access Denied: Only authorized AoA Committee Members can access this portal."),
            frappe.PermissionError,
        )

    data = {}

    # 1. Tenants
    if module_type in ("all", "tenants"):
        tenants = frappe.get_all(
            "Tenants",
            fields=[
                "name",
                "flat",
                "tenant_name",
                "mobile_no",
                "email",
                "registration_status",
                "active",
                "start_date",
                "end_date",
                "remarks",
                "rental_agreement",
                "police_verification",
                "id_proof",
                "creation",
            ],
            order_by="creation desc",
            limit_page_length=150,
        )
        # Sort pending first in Python
        tenants.sort(key=lambda x: (0 if x.get("registration_status") == "Pending" else 1, str(x.get("flat"))))
        data["tenants"] = tenants

    # 2. Resident Vehicles
    if module_type in ("all", "vehicles"):
        vehicles = frappe.get_all(
            "Resident Vehicle",
            fields=[
                "name",
                "flat",
                "registered_owner_name",
                "vehicle_type",
                "registration_number",
                "make",
                "model",
                "color",
                "belongs_to",
                "relationship_to_resident",
                "approval_status",
                "rfid_number",
                "rc_copy",
                "noc",
                "creation",
            ],
            order_by="creation desc",
            limit_page_length=150,
        )
        vehicles.sort(key=lambda x: (0 if x.get("approval_status") == "Pending" else 1, str(x.get("flat"))))
        data["vehicles"] = vehicles

    # 3. Work Permits
    if module_type in ("all", "work_permits"):
        permits = frappe.get_all(
            "Work Permit",
            fields=[
                "name",
                "flat_number",
                "contractor_name",
                "work_type",
                "start_date",
                "end_date",
                "status",
                "remarks",
                "creation",
            ],
            order_by="creation desc",
            limit_page_length=150,
        )
        permits.sort(key=lambda x: (0 if x.get("status") == "Pending" else 1, str(x.get("flat_number"))))
        data["work_permits"] = permits

    # 4. Resident Pets
    if module_type in ("all", "pets"):
        pets = frappe.get_all(
            "Resident Pets",
            fields=[
                "name",
                "parent",
                "flat",
                "pet_name",
                "license_no",
                "license_issue_date",
                "license_expiry_date",
                "vaccination_certificate_no",
                "vaccination_date",
                "vaccination_due_date",
                "approval_status",
                "pet_photo",
                "creation",
            ],
            order_by="creation desc",
            limit_page_length=150,
        )
        for p in pets:
            if not p.get("flat") and p.get("parent"):
                p["flat"] = p["parent"]
        pets.sort(key=lambda x: (0 if x.get("approval_status") == "Pending" else 1, str(x.get("flat"))))
        data["pets"] = pets

    # 5. Family Members
    if module_type in ("all", "family"):
        family = frappe.get_all(
            "Family Members",
            fields=[
                "name",
                "parent_flat",
                "member_name",
                "relationship",
                "mobile_no",
                "status",
                "registration_status",
                "id_proof_type",
                "id_proof_document",
                "verified_by",
                "verification_date",
                "creation",
            ],
            order_by="creation desc",
            limit_page_length=200,
        )
        family.sort(key=lambda x: (0 if x.get("registration_status") == "Pending" else 1, str(x.get("parent_flat"))))
        data["family"] = family

    # 6. Society Notices
    if module_type in ("all", "notices"):
        notices = frappe.get_all(
            "Society Notice",
            fields=[
                "name",
                "title",
                "content",
                "date",
                "is_active",
                "posted_by",
                "creation",
            ],
            order_by="date desc, creation desc",
            limit_page_length=50,
        )
        data["notices"] = notices

    # 7. Maintenance Tickets
    if module_type in ("all", "tickets"):
        tickets = frappe.get_all(
            "Maintenance Ticket",
            fields=[
                "name",
                "resident",
                "category",
                "priority_level",
                "status",
                "description",
                "resolution_remarks",
                "received_on",
                "preferred_visit_time",
                "photo",
                "creation",
            ],
            order_by="creation desc",
            limit_page_length=150,
        )
        status_rank = {"Open": 0, "Assigned": 1, "Resolved": 2}
        tickets.sort(key=lambda x: (status_rank.get(x.get("status"), 3), str(x.get("creation"))), reverse=False)
        data["tickets"] = tickets

    # Counts summary
    data["counts"] = {
        "tenants_pending": frappe.db.count("Tenants", {"registration_status": "Pending"}),
        "vehicles_pending": frappe.db.count("Resident Vehicle", {"approval_status": "Pending"}),
        "permits_pending": frappe.db.count("Work Permit", {"status": "Pending"}),
        "pets_pending": frappe.db.count("Resident Pets", {"approval_status": "Pending"}),
        "family_pending": frappe.db.count("Family Members", {"registration_status": "Pending"}),
        "tickets_open": frappe.db.count("Maintenance Ticket", {"status": "Open"}),
        "notices_active": frappe.db.count("Society Notice", {"is_active": 1}),
    }

    return data


@frappe.whitelist()
def update_item_status(doctype, docname, action, remarks=None):
    """
    Handles committee approval/rejection/status updates across target DocTypes:
    - Tenants: action in ('Verified Physically', 'Rejected')
    - Resident Vehicle: action in ('Approved', 'Rejected')
    - Work Permit: action in ('Approved', 'Rejected', 'Completed')
    - Resident Pets: action in ('Approved', 'Rejected')
    - Family Members: action in ('Verified', 'Rejected')
    - Maintenance Ticket: action in ('Assigned', 'Resolved', 'Open')
    """
    has_access, member_info = check_committee_access()
    if not has_access:
        frappe.throw(_("Permission Denied: Committee authorization required."), frappe.PermissionError)

    if not doctype or not docname or not action:
        frappe.throw(_("Missing doctype, docname or action."))

    allowed_doctypes = {
        "Tenants",
        "Resident Vehicle",
        "Work Permit",
        "Resident Pets",
        "Family Members",
        "Maintenance Ticket",
        "Society Notice",
    }
    if doctype not in allowed_doctypes:
        frappe.throw(_("Invalid DocType."))

    doc = frappe.get_doc(doctype, docname)
    user = frappe.session.user
    comm_name = member_info.get("owner_name") or user

    if doctype == "Tenants":
        if action in ("Verified Physically", "Verified by Bot", "Approved"):
            doc.registration_status = "Verified Physically"
            doc.active = 1
        elif action == "Rejected":
            doc.registration_status = "Rejected"
            doc.active = 0
        if remarks:
            doc.remarks = f"{doc.remarks or ''}\n[{today()}] {comm_name}: {remarks}".strip()

    elif doctype == "Resident Vehicle":
        if action in ("Approved", "Rejected", "Inactive"):
            doc.approval_status = action
        if remarks:
            doc.remarks = f"{doc.remarks or ''}\n[{today()}] {comm_name}: {remarks}".strip()

    elif doctype == "Work Permit":
        if action in ("Approved", "Rejected", "Revoked", "Completed"):
            doc.status = action
        if remarks:
            doc.remarks = f"{doc.remarks or ''}\n[{today()}] {comm_name}: {remarks}".strip()

    elif doctype == "Resident Pets":
        if action in ("Approved", "Rejected", "Pending"):
            doc.approval_status = action

    elif doctype == "Family Members":
        if action in ("Verified", "Approved"):
            doc.registration_status = "Verified"
            doc.status = "Active"
            doc.verified_by = user
            doc.verification_date = today()
        elif action == "Rejected":
            doc.registration_status = "Rejected"
            doc.status = "Inactive"
            doc.verified_by = user
            doc.verification_date = today()

    elif doctype == "Maintenance Ticket":
        if action in ("Open", "Assigned", "Resolved"):
            doc.status = action
        if remarks:
            existing = doc.resolution_remarks or ""
            doc.resolution_remarks = f"{existing}\n[{today()}] 🏢 Committee ({comm_name}): {remarks}".strip()

    elif doctype == "Society Notice":
        if action == "toggle_active":
            doc.is_active = 0 if doc.is_active else 1
            doc.save(ignore_permissions=True)
            frappe.db.commit()
            return {"status": "success", "message": _("Notice status updated.")}
        elif action == "delete":
            frappe.delete_doc(doctype, docname, ignore_permissions=True)
            frappe.db.commit()
            return {"status": "success", "message": _("Notice deleted.")}

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "message": _("{0} {1} updated to '{2}'.").format(doctype, docname, action),
    }


@frappe.whitelist()
def post_society_notice(title, content, is_active=1):
    """
    Allows a Committee Member to post an official Society Notice directly to the Notice Board.
    """
    has_access, member_info = check_committee_access()
    if not has_access:
        frappe.throw(_("Permission Denied: Only AoA Committee Members can publish notices."), frappe.PermissionError)

    if not title or not title.strip():
        frappe.throw(_("Notice Title is required."))
    if not content or not content.strip():
        frappe.throw(_("Notice Content is required."))

    doc = frappe.new_doc("Society Notice")
    doc.title = title.strip()
    doc.content = content.strip()
    doc.date = today()
    doc.is_active = 1 if int(is_active) else 0
    doc.posted_by = member_info.get("name") if member_info.get("name") else None
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "message": _("Notice published successfully!"),
        "notice_id": doc.name,
    }
