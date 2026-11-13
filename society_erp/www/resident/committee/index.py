import frappe
from frappe import _
from frappe.utils import format_date, get_datetime, nowdate, today


def mask_phone_number(phone):
    """Masks phone number showing only prefix and last 3-4 digits e.g., +91 98****1234"""
    if not phone:
        return ""
    p = str(phone).strip()
    if len(p) <= 4:
        return "****"
    if len(p) <= 7:
        return p[:2] + "****" + p[-2:]
    return p[:4] + "****" + p[-4:]


def mask_email_address(email):
    """Masks email address e.g., fa****@gmail.com"""
    if not email or "@" not in email:
        return ""
    parts = email.strip().split("@")
    user, domain = parts[0], parts[1]
    if len(user) <= 2:
        masked_user = user[0] + "*"
    else:
        masked_user = user[:2] + "****"
    return f"{masked_user}@{domain}"


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
        "facility_bookings_pending": frappe.db.count(
            "Facility Booking", {"status": "Pending Approval"}
        ),
        "classifieds_pending": frappe.db.count(
            "Resident Classified", {"approval_status": "Pending Approval"}
        ),
        "resolutions_pending": 0,
        "facility_on_duty": frappe.db.count(
            "Facility Staff Attendance", {"attendance_date": nowdate(), "status": "Present", "out_time": ("is", "not set")}
        ),
        "facility_staff_total": frappe.db.count("Facility Staff", {"status": "Active"}),
        "amc_logs_total": frappe.db.count("Facility AMC Log"),
    }

    # Count pending resolutions for the current user
    user_email = (member_info.get("email") or frappe.session.user).strip().lower()
    comm_member_name = frappe.db.get_value("Committee Member", {"member_name": user_email, "status": "Active"}, "name")
    if comm_member_name:
        context.counts["resolutions_pending"] = frappe.db.count(
            "Resolution Signatory",
            {"signatory": comm_member_name, "signature_status": "Pending"}
        )

    # Emergency SOS feature status and contacts count
    enable_sos = frappe.db.get_single_value("Society ERP Settings", "enable_emergency_sos")
    context.enable_emergency_sos = bool(int(enable_sos)) if enable_sos is not None else True
    context.emergency_contacts_count = frappe.db.count("Emergency Contact", {"enabled": 1})

    # Portal tile master switch configuration (committee specific)
    from society_erp.www.resident.settings.index import get_tile_settings
    tile_cfg = get_tile_settings()
    context.tiles = tile_cfg.get("committee", {})

    # Detect standalone / WebApp view mode
    context.is_standalone = bool(frappe.form_dict.get("standalone"))
    context.target_tab = (frappe.form_dict.get("tab") or "").strip().lower()
    if context.is_standalone:
        context.no_header = True
        context.no_sidebar = True

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
        for t in tenants:
            t["raw_mobile_no"] = t.get("mobile_no")
            t["raw_email"] = t.get("email")
            t["mobile_no"] = mask_phone_number(t.get("mobile_no"))
            t["email"] = mask_email_address(t.get("email"))
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
        for f in family:
            f["raw_mobile_no"] = f.get("mobile_no")
            f["mobile_no"] = mask_phone_number(f.get("mobile_no"))
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

    # 8. Board Resolutions
    user_email = (member_info.get("email") or frappe.session.user).strip().lower()
    comm_member_name = frappe.db.get_value("Committee Member", {"member_name": user_email, "status": "Active"}, "name")
    
    if module_type in ("all", "resolutions"):
        resolutions = frappe.get_all(
            "Board Resolution",
            fields=[
                "name",
                "resolution_title",
                "resolution_text",
                "status",
                "docstatus",
                "owner",
                "created_by_member",
                "is_published_to_notice_board",
                "published_notice",
                "published_on",
                "creation",
            ],
            order_by="creation desc",
            limit_page_length=100,
        )
        
        # Load signatories for each resolution
        for res in resolutions:
            signatories = frappe.get_all(
                "Resolution Signatory",
                filters={"parent": res.name},
                fields=[
                    "name",
                    "signatory",
                    "signatory_name",
                    "designation_name",
                    "signature_status",
                    "signed_on",
                    "rejection_reason",
                ],
                order_by="idx asc",
            )
            res["signatories"] = signatories
            
            # Check current user's voting status and authorship
            res["user_signatory_row"] = None
            res["user_has_voted"] = False
            res["user_status"] = "Not Signatory"

            # Check if current user is the author (drafter) of this resolution
            is_author = False
            if member_info.get("is_admin") or frappe.session.user == "Administrator":
                is_author = True
            elif res.owner and res.owner.strip().lower() in (frappe.session.user.lower(), user_email):
                is_author = True
            elif comm_member_name and res.created_by_member == comm_member_name:
                is_author = True
            res["is_author"] = is_author
            
            for s in signatories:
                if comm_member_name and s.signatory == comm_member_name:
                    res["user_signatory_row"] = s
                    res["user_has_voted"] = s.signature_status in ("Signed", "Declined")
                    res["user_status"] = s.signature_status
                    break
                    
        # Sort pending-signature first for this member
        resolutions.sort(
            key=lambda x: (
                0 if (x.get("user_status") == "Pending" and x.get("status") in ("Circulated", "Draft")) else 1,
                str(x.get("creation")),
            ),
            reverse=False,
        )
        data["resolutions"] = resolutions

    # 9. Facility Bookings (Community Hall)
    if module_type in ("all", "facility_bookings"):
        bookings = frappe.get_all(
            "Facility Booking",
            fields=[
                "name",
                "facility",
                "shift",
                "resident",
                "booking_date",
                "status",
                "remarks",
                "creation",
            ],
            order_by="booking_date desc, creation desc",
            limit_page_length=100,
        )
        for b in bookings:
            b["formatted_booking_date"] = format_date(b.booking_date, "dd-MM-yyyy") if b.booking_date else ""
        bookings.sort(key=lambda x: (0 if x.get("status") == "Pending Approval" else 1, str(x.get("booking_date"))))
        data["facility_bookings"] = bookings

    # 10. Resident Classifieds
    if module_type in ("all", "classifieds"):
        classifieds = frappe.get_all(
            "Resident Classified",
            fields=[
                "name",
                "title",
                "category",
                "listing_type",
                "price",
                "resident",
                "contact_person",
                "contact_phone",
                "approval_status",
                "status",
                "description",
                "committee_remarks",
                "creation",
            ],
            order_by="creation desc",
            limit_page_length=100,
        )
        for c in classifieds:
            c["formatted_date"] = format_date(c.creation, "dd-MM-yyyy")
        classifieds.sort(key=lambda x: (0 if x.get("approval_status") == "Pending Approval" else 1, str(x.get("creation"))), reverse=False)
        data["classifieds"] = classifieds

    # 11. Facility & Security Staff
    if module_type in ("all", "facility_staff"):
        from society_erp.api.facility_staff import get_daily_roster
        data["facility_staff"] = get_daily_roster().get("roster", [])
        data["facility_musters"] = frappe.get_all(
            "Facility Shift Muster",
            filters={"shift_date": nowdate()},
            fields=["name", "agency", "shift", "category", "muster_photo", "reported_count", "briefing_notes", "creation"],
            order_by="creation desc"
        )

    # 12. Block Water Sump & Pump Monitoring
    if module_type in ("all", "water_log"):
        from society_erp.api.water import get_daily_water_summary
        data["water_summary"] = get_daily_water_summary()

    # 13. Housekeeping Cleaning Proofs
    if module_type in ("all", "cleaning_log"):
        from society_erp.api.facility_staff import get_daily_cleaning_summary
        data["cleaning_summary"] = get_daily_cleaning_summary()

    # 14. Overhead Tank Cleaning Records
    if module_type in ("all", "tank_cleaning"):
        data["tank_cleanings"] = frappe.get_all(
            "Tank Cleaning Log",
            fields=[
             "name", "block", "tank_type", "tank_location", "activity_date",
             "cleaning_status", "cleaning_agency", "supervisor_in_charge",
             "photo_before", "photo_after", "sediment_level_observed",
             "chlorination_done", "next_due_date", "remarks"
            ],
            order_by="activity_date desc, creation desc",
            limit_page_length=50
        )

    # 15. Facility AMC & Equipment Logs (Lifts, DG, STP, Fire Safety)
    if module_type in ("all", "amc_log"):
        data["amc_logs"] = frappe.get_all(
            "Facility AMC Log",
            fields=[
                "name", "equipment_name", "asset_category", "location_or_block",
                "service_type", "service_date", "vendor_agency", "technician_name",
                "technician_contact", "service_cost", "next_service_due_date",
                "amc_contract_expiry", "equipment_operational_status",
                "service_report_document", "equipment_photo", "work_carried_out",
                "parts_replaced", "remarks"
            ],
            order_by="service_date desc, creation desc",
            limit_page_length=60
        )

    # Counts summary
    res_pending_count = 0
    if comm_member_name:
        res_pending_count = frappe.db.count(
            "Resolution Signatory",
            {"signatory": comm_member_name, "signature_status": "Pending"}
        )

    enable_sos = frappe.db.get_single_value("Society ERP Settings", "enable_emergency_sos")
    data["enable_emergency_sos"] = bool(int(enable_sos)) if enable_sos is not None else True
    
    from society_erp.www.resident.settings.index import get_tile_settings
    data["tiles"] = get_tile_settings().get("committee", {})

    data["emergency_contacts"] = frappe.get_all(
        "Emergency Contact",
        fields=["name", "title", "category", "phone", "operating_hours", "icon", "description", "enabled", "sort_order"],
        order_by="sort_order asc, title asc"
    )

    data["counts"] = {
        "tenants_pending": frappe.db.count("Tenants", {"registration_status": "Pending"}),
        "vehicles_pending": frappe.db.count("Resident Vehicle", {"approval_status": "Pending"}),
        "permits_pending": frappe.db.count("Work Permit", {"status": "Pending"}),
        "pets_pending": frappe.db.count("Resident Pets", {"approval_status": "Pending"}),
        "family_pending": frappe.db.count("Family Members", {"registration_status": "Pending"}),
        "tickets_open": frappe.db.count("Maintenance Ticket", {"status": "Open"}),
        "notices_active": frappe.db.count("Society Notice", {"is_active": 1}),
        "facility_bookings_pending": frappe.db.count("Facility Booking", {"status": "Pending Approval"}),
        "classifieds_pending": frappe.db.count("Resident Classified", {"approval_status": "Pending Approval"}),
        "resolutions_pending": res_pending_count,
        "facility_on_duty": frappe.db.count("Facility Staff Attendance", {"attendance_date": nowdate(), "status": "Present", "out_time": ("is", "not set")}),
        "facility_staff_total": frappe.db.count("Facility Staff", {"status": "Active"}),
        "facility_staff_pending": frappe.db.count("Facility Staff", {"approval_status": "Pending"}),
        "amc_logs_total": frappe.db.count("Facility AMC Log"),
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
        "Facility Booking",
        "Resident Classified",
        "Facility Staff",
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

        # If assigned, post magic link to QRT Telegram Group
        if action == "Assigned":
            try:
                from society_erp.api.qrt_maintenance import assign_ticket_and_notify_qrt
                assign_ticket_and_notify_qrt(ticket_name=doc.name, remarks=remarks)
            except Exception as e:
                frappe.logger("society_erp").error(f"Failed to post to QRT: {e}")

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

    elif doctype == "Facility Booking":
        if action in ("Approved", "Confirmed"):
            # Check if shift/date is already booked by another confirmed booking
            conflicts = frappe.get_all(
                "Facility Booking",
                filters={
                    "facility": doc.facility,
                    "booking_date": doc.booking_date,
                    "status": ["in", ["Confirmed", "Approved"]],
                    "name": ["!=", doc.name],
                },
                fields=["shift", "name"],
            )
            for c in conflicts:
                c_shift = c.shift or "Full Day (9:00 AM - 10:00 PM)"
                d_shift = doc.shift or "Full Day (9:00 AM - 10:00 PM)"
                if "Full Day" in c_shift or "Full Day" in d_shift or c_shift == d_shift:
                    frappe.throw(
                        _("Facility '{0}' is already booked and approved on {1} for {2}.").format(
                            doc.facility, format_date(doc.booking_date, "dd-MM-yyyy"), c_shift
                        )
                    )
            doc.status = "Confirmed"
        elif action in ("Rejected", "Cancelled"):
            doc.status = action
        if remarks:
            doc.remarks = f"{doc.remarks or ''}\n[{today()}] {comm_name}: {remarks}".strip()

    elif doctype == "Resident Classified":
        if action in ("Approved", "Rejected"):
            doc.approval_status = action
            doc.approved_by = comm_name
            doc.approval_date = today()
        if remarks:
            doc.committee_remarks = f"{doc.committee_remarks or ''}\n[{today()}] {comm_name}: {remarks}".strip()

    elif doctype == "Facility Staff":
        if action in ("Approved", "Rejected"):
            doc.approval_status = action
            doc.approved_by = user
            doc.approval_date = today()
            doc.status = "Active" if action == "Approved" else "Inactive"
            if action == "Rejected" and remarks:
                doc.rejection_remarks = remarks
            elif action == "Approved":
                doc.rejection_remarks = None

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


@frappe.whitelist()
def respond_board_resolution(docname, action, rejection_reason=None):
    """
    Whitelisted API for Committee Members to vote (Signed / Declined) on a Board Resolution
    from the Committee Portal.
    """
    has_access, member_info = check_committee_access()
    if not has_access:
        frappe.throw(_("Permission Denied: Only AoA Committee Members can respond to resolutions."), frappe.PermissionError)

    if action not in ("Signed", "Declined"):
        frappe.throw(_("Invalid action. Must be 'Signed' or 'Declined'."))

    if action == "Declined" and not rejection_reason:
        frappe.throw(_("Please provide a reason for declining this resolution."))

    doc = frappe.get_doc("Board Resolution", docname)

    # Determine user identity - support User, Committee Member link, and Owner email
    user = frappe.session.user
    user_email = (member_info.get("email") or user).strip().lower()

    # Find the corresponding Committee Member docname
    comm_member_names = frappe.get_all(
        "Committee Member",
        filters={"member_name": ["in", [user, user_email]], "status": "Active"},
        pluck="name",
    )

    user_found = False
    for row in doc.get("signatories"):
        member_user = frappe.db.get_value("Committee Member", row.signatory, "member_name")
        is_match = False

        if row.signatory in comm_member_names:
            is_match = True
        elif member_user and member_user.strip().lower() in (user.lower(), user_email):
            is_match = True

        if is_match:
            user_found = True
            if row.signature_status in ("Signed", "Declined"):
                frappe.throw(_(f"You have already responded to this resolution (Status: {row.signature_status})."))

            row.signature_status = action
            now_dt = frappe.utils.now_datetime()
            row.timestamp = now_dt
            row.signed_on = now_dt
            row.rejection_reason = rejection_reason if action == "Declined" else None
            break

    if not user_found:
        frappe.throw(_("You are not listed as an active signatory for this resolution."))

    # --- 51% MAJORITY CHECK ---
    total_signatories = len(doc.get("signatories"))
    if total_signatories > 0:
        signed_count = sum(1 for r in doc.get("signatories") if r.signature_status == "Signed")
        declined_count = sum(1 for r in doc.get("signatories") if r.signature_status == "Declined")

        if (signed_count / total_signatories) >= 0.51:
            doc.status = "Passed"
        elif (declined_count / total_signatories) >= 0.51:
            doc.status = "Rejected"

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "message": _("Your response has been recorded successfully."),
        "resolution_status": doc.status,
    }


@frappe.whitelist()
def create_board_resolution(title, text):
    """
    Creates a new Board Resolution from the Committee Portal and circulates it to all active Committee Members.
    """
    has_access, member_info = check_committee_access()
    if not has_access:
        frappe.throw(_("Permission Denied: Only AoA Committee Members can create resolutions."), frappe.PermissionError)

    if not title or not title.strip():
        frappe.throw(_("Resolution Title is required."))
    if not text or not text.strip():
        frappe.throw(_("Resolution Text is required."))

    user = frappe.session.user
    user_email = (member_info.get("email") or user).strip().lower()
    comm_member_name = frappe.db.get_value(
        "Committee Member",
        {"member_name": ["in", [user, user_email]], "status": "Active"},
        "name",
    )

    doc = frappe.new_doc("Board Resolution")
    doc.resolution_title = title.strip()
    doc.resolution_text = text.strip()
    doc.status = "Circulated"
    if comm_member_name:
        doc.created_by_member = comm_member_name

    # Auto-populate all active Committee Members as signatories
    from society_erp.society_erp.doctype.board_resolution.board_resolution import get_active_committee_members
    active_members = get_active_committee_members()
    if not active_members:
        frappe.throw(_("No active Committee Members found to add as signatories."))

    for m in active_members:
        doc.append("signatories", {
            "signatory": m.get("name"),
            "role": m.get("designation"),
            "signatory_name": m.get("signatory_name"),
            "designation_name": m.get("designation_name"),
            "signature_status": "Pending",
        })

    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "message": _("Board Resolution created and circulated for voting!"),
        "resolution_id": doc.name,
    }


@frappe.whitelist()
def publish_resolution_to_notice_board(docname):
    """
    Publishes a Passed Board Resolution to the Society Notice Board.
    Restricted to the Committee Member who drafted the resolution (or System Administrator).
    """
    has_access, member_info = check_committee_access()
    if not has_access:
        frappe.throw(_("Permission Denied: Only AoA Committee Members can publish resolutions."), frappe.PermissionError)

    doc = frappe.get_doc("Board Resolution", docname)

    # 1. Must be in 'Passed' status
    if doc.status != "Passed":
        frappe.throw(_("Only Passed Board Resolutions can be published to the Notice Board. (Current status: {0})").format(doc.status))

    # 2. Check already published
    if doc.is_published_to_notice_board and doc.published_notice:
        frappe.throw(_("This resolution has already been published to the Notice Board (Notice ID: {0}).").format(doc.published_notice))

    # 3. Verify author authority
    user = frappe.session.user
    user_email = (member_info.get("email") or user).strip().lower()
    comm_member_name = frappe.db.get_value(
        "Committee Member",
        {"member_name": ["in", [user, user_email]], "status": "Active"},
        "name",
    )

    is_author = False
    if member_info.get("is_admin") or user == "Administrator":
        is_author = True
    elif doc.owner and doc.owner.strip().lower() in (user.lower(), user_email):
        is_author = True
    elif comm_member_name and doc.created_by_member == comm_member_name:
        is_author = True

    if not is_author:
        frappe.throw(_("Permission Denied: Only the Committee Member who drafted this resolution can publish it to the Notice Board."))

    # 4. Generate the Society Notice text
    # Strip HTML tags or present clean announcement
    import re
    clean_text = re.sub('<[^<]+?>', '', doc.resolution_text or "").strip()
    notice_title = f"Passed Board Resolution: {doc.resolution_title}"
    notice_content = (
        f"Official Board Resolution {doc.name} has been passed by the Managing Committee with required majority.\n\n"
        f"Resolution Summary:\n{clean_text}\n\n"
        f"Passed on: {doc.modified.strftime('%d-%b-%Y') if hasattr(doc.modified, 'strftime') else today()}\n"
        f"Published by: {member_info.get('owner_name', 'Managing Committee')}"
    )

    notice_doc = frappe.new_doc("Society Notice")
    notice_doc.title = notice_title
    notice_doc.content = notice_content
    notice_doc.date = today()
    notice_doc.is_active = 1
    notice_doc.posted_by = member_info.get("name") if member_info.get("name") else None
    notice_doc.insert(ignore_permissions=True)

    # 5. Update resolution tracking fields
    now_dt = frappe.utils.now_datetime()
    doc.is_published_to_notice_board = 1
    doc.published_notice = notice_doc.name
    doc.published_on = now_dt
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "message": _("Board Resolution successfully published to Society Notice Board! (Notice ID: {0})").format(notice_doc.name),
        "notice_id": notice_doc.name,
    }


@frappe.whitelist()
def reveal_contact_details(doctype, docname):
    """
    Whitelisted API to audit and temporarily reveal full contact details (Phone/Email)
    for a specific person/record in compliance with DPDP Act.
    Logs access into 'Committee Access Log'.
    """
    has_access, member_info = check_committee_access()
    if not has_access:
        frappe.throw(_("Permission Denied: Only AoA Committee Members can reveal contact details."), frappe.PermissionError)

    if doctype not in ("Tenants", "Family Members", "Owners"):
        frappe.throw(_("Invalid target DocType."))

    doc = frappe.get_doc(doctype, docname)

    target_flat = doc.get("flat") or doc.get("parent_flat") or "-"
    target_person = doc.get("tenant_name") or doc.get("member_name") or doc.get("owner_name") or "-"
    mobile_no = doc.get("mobile_no") or ""
    email = doc.get("email") or ""

    # Record Access in Committee Access Log
    user = frappe.session.user
    comm_desc = f"{member_info.get('owner_name', '')} ({member_info.get('flat', '')})"

    log = frappe.new_doc("Committee Access Log")
    log.accessed_by = user
    log.accessed_by_name = member_info.get("owner_name") or user
    log.committee_member_name = comm_desc
    log.action_type = "Reveal Contact Details"
    log.target_doctype = doctype
    log.target_docname = docname
    log.target_flat = target_flat
    log.target_person_name = target_person
    log.timestamp = frappe.utils.now_datetime()
    log.ip_address = frappe.local.request_ip if hasattr(frappe.local, "request_ip") else None
    log.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "docname": docname,
        "mobile_no": mobile_no,
        "email": email,
        "person_name": target_person,
        "message": _("Contact details unmasked and logged for audit compliance.")
    }


@frappe.whitelist()
def toggle_emergency_sos_feature(enabled):
    """
    Committee endpoint to enable or disable the Emergency SOS & Contacts feature for residents.
    """
    has_access, member_info = check_committee_access()
    if not has_access:
        frappe.throw(_("Permission Denied: Only AoA Committee Members can update portal settings."), frappe.PermissionError)

    val = 1 if (str(enabled).lower() in ("1", "true")) else 0
    frappe.db.set_single_value("Society ERP Settings", "enable_emergency_sos", val)
    frappe.db.commit()

    return {
        "status": "success",
        "enabled": bool(val),
        "message": _("Emergency SOS feature has been {0} for residents.").format("ENABLED" if val else "DISABLED")
    }


@frappe.whitelist()
def save_emergency_contact(title, phone, category="Society Security", operating_hours="24x7", icon="📞", description=None, contact_name=None, enabled=1):
    """
    Committee endpoint to create or update an Emergency / SOS contact entry.
    """
    has_access, member_info = check_committee_access()
    if not has_access:
        frappe.throw(_("Permission Denied: Only AoA Committee Members can manage emergency contacts."), frappe.PermissionError)

    if not title or not phone:
        frappe.throw(_("Title and Phone Number are required."))

    if contact_name and frappe.db.exists("Emergency Contact", contact_name):
        doc = frappe.get_doc("Emergency Contact", contact_name)
    else:
        doc = frappe.new_doc("Emergency Contact")

    doc.title = title.strip()
    doc.phone = phone.strip()
    doc.category = category
    doc.operating_hours = operating_hours or "24x7"
    doc.icon = icon or "📞"
    doc.description = (description or "").strip()
    doc.enabled = 1 if str(enabled).lower() in ("1", "true") else 0
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "contact_name": doc.name,
        "message": _("Emergency contact saved successfully.")
    }

