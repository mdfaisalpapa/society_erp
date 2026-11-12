import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, get_datetime, time_diff_in_hours


@frappe.whitelist()
def punch_attendance(
    staff_id: str = None,
    qr_code: str = None,
    shift: str = None,
    duty_post: str = None,
    gate: str = "Main Gate",
    method: str = "Supervisor Punch",
    punch_type: str = "auto",  # 'in', 'out', or 'auto'
    verified_by: str = None,
    remarks: str = None
) -> dict:
    """
    Records a punch-in or punch-out for an agency facility staff member.
    Can identify staff either via staff_id (e.g. FS-2026-00001) or qr_code (e.g. KVC3-STAFF-FS-2026-00001).
    Also assigns dynamic physical duty post and derives Cost Center.
    """
    if qr_code and not staff_id:
        staff_id = frappe.db.get_value("Facility Staff", {"qr_code_id": qr_code.strip()}, "name")
        if not staff_id:
            if frappe.db.exists("Facility Staff", qr_code.strip()):
                staff_id = qr_code.strip()
            else:
                frappe.throw(_("Invalid or unrecognized Staff QR Code: {0}").format(qr_code))

    if not staff_id or not frappe.db.exists("Facility Staff", staff_id):
        frappe.throw(_("Invalid staff ID: {0}").format(staff_id))

    staff = frappe.get_doc("Facility Staff", staff_id)
    if staff.status != "Active":
        frappe.throw(_("Staff member {0} is currently '{1}' and cannot be punched in.").format(staff.full_name, staff.status))

    today = nowdate()
    now_dt = now_datetime()
    verifier = verified_by or frappe.session.user

    # Auto-detect active shift if not provided
    if not shift:
        shift = get_active_shift_for_time()

    # Determine duty post and cost center
    post_name = duty_post or staff.default_duty_post
    cost_center = None
    if post_name and frappe.db.exists("Facility Duty Post", post_name):
        cost_center = frappe.db.get_value("Facility Duty Post", post_name, "cost_center")

    # Look for open punch for today
    existing = frappe.db.get_value(
        "Facility Staff Attendance",
        {"staff": staff_id, "attendance_date": today, "out_time": ("is", "not set")},
        ["name", "in_time", "shift", "duty_post", "cost_center"],
        as_dict=True
    )

    if punch_type == "in" or (punch_type == "auto" and not existing):
        # Create Punch-In
        doc = frappe.get_doc({
            "doctype": "Facility Staff Attendance",
            "staff": staff_id,
            "attendance_date": today,
            "shift": shift or (existing.get("shift") if existing else shift),
            "status": "Present",
            "in_time": now_dt,
            "verification_method": method,
            "duty_post": post_name,
            "cost_center": cost_center,
            "gate": gate,
            "verified_by": verifier,
            "remarks": remarks
        })
        doc.insert(ignore_permissions=True)
        return {
            "status": "success",
            "action": "punch_in",
            "message": _("{0} punched IN successfully at {1}").format(staff.full_name, now_dt.strftime("%H:%M:%S")),
            "attendance_id": doc.name,
            "staff_name": staff.full_name,
            "role": staff.role,
            "duty_post": post_name,
            "cost_center": cost_center,
            "in_time": str(now_dt)
        }

    else:
        # Punch-Out
        att_name = existing.name if existing else frappe.db.get_value(
            "Facility Staff Attendance",
            {"staff": staff_id, "attendance_date": today},
            "name",
            order_by="creation desc"
        )

        if not att_name:
            frappe.throw(_("No attendance record found for {0} today to punch out.").format(staff.full_name))

        doc = frappe.get_doc("Facility Staff Attendance", att_name)
        doc.out_time = now_dt
        if remarks:
            doc.remarks = ((doc.remarks or "") + " | " + remarks).strip(" | ")
        doc.save(ignore_permissions=True)

        return {
            "status": "success",
            "action": "punch_out",
            "message": _("{0} punched OUT successfully at {1} (Hours worked: {2})").format(staff.full_name, now_dt.strftime("%H:%M:%S"), doc.hours_worked),
            "attendance_id": doc.name,
            "staff_name": staff.full_name,
            "role": staff.role,
            "out_time": str(now_dt),
            "hours_worked": doc.hours_worked
        }


@frappe.whitelist()
def get_daily_roster(date: str = None, agency: str = None, shift: str = None, include_pending: bool = True) -> dict:
    """
    Returns today's deployment roster with real-time punch status for each staff member.
    """
    target_date = date or nowdate()
    filters = {}
    if agency:
        filters["agency"] = agency
    
    if not include_pending:
        filters["status"] = "Active"
        filters["approval_status"] = "Approved"
    else:
        # Include Active staff OR staff Pending approval
        filters["status"] = ["in", ["Active", "Inactive"]]
        filters["approval_status"] = ["in", ["Approved", "Pending"]]

    all_staff = frappe.get_all(
        "Facility Staff",
        filters=filters,
        fields=[
            "name", "full_name", "agency", "role", "contact_number",
            "gate_assigned", "default_duty_post", "photo", "police_verification_status",
            "rfid_badge_id", "qr_code_id", "approval_status", "status"
        ],
        order_by="approval_status desc, role asc, full_name asc"
    )

    # Get today's attendances
    att_filters = {"attendance_date": target_date}
    if shift:
        att_filters["shift"] = shift

    attendances = frappe.get_all(
        "Facility Staff Attendance",
        filters=att_filters,
        fields=["name", "staff", "shift", "status", "in_time", "out_time", "hours_worked", "gate", "duty_post", "cost_center", "verification_method"],
        order_by="creation desc"
    )
    # Map latest attendance per staff member
    att_by_staff = {}
    for a in attendances:
        if a.staff not in att_by_staff:
            att_by_staff[a.staff] = a
        elif a.in_time and not a.out_time:
            # Prefer active on-duty punch
            att_by_staff[a.staff] = a

    roster = []
    present_count = 0
    total_count = len(all_staff)

    for s in all_staff:
        att = att_by_staff.get(s.name)
        is_on_duty = bool(att and att.in_time and not att.out_time)
        if att and att.status == "Present":
            present_count += 1

        duty_post = att.duty_post if (att and att.duty_post) else s.default_duty_post
        cost_center = att.cost_center if (att and att.cost_center) else None
        if not cost_center and duty_post:
            cost_center = frappe.db.get_value("Facility Duty Post", duty_post, "cost_center")

        roster.append({
            "staff_id": s.name,
            "full_name": s.full_name,
            "agency": s.agency,
            "role": s.role,
            "contact_number": s.contact_number,
            "gate_assigned": s.gate_assigned,
            "default_duty_post": s.default_duty_post,
            "duty_post": duty_post,
            "cost_center": cost_center,
            "photo": s.photo,
            "police_status": s.police_verification_status,
            "rfid_badge_id": s.rfid_badge_id,
            "qr_code_id": s.qr_code_id or f"KVC3-STAFF-{s.name}",
            "attendance_id": att.name if att else None,
            "status": att.status if att else "Not Marked",
            "approval_status": s.approval_status or "Approved",
            "is_on_duty": is_on_duty,
            "in_time": str(att.in_time) if att and att.in_time else None,
            "out_time": str(att.out_time) if att and att.out_time else None,
            "hours_worked": att.hours_worked if att else 0.0,
            "gate": att.gate if att else s.gate_assigned,
            "shift": att.shift if att else shift
        })

    return {
        "date": target_date,
        "total_active_staff": total_count,
        "present_count": present_count,
        "on_duty_count": sum(1 for r in roster if r["is_on_duty"]),
        "pending_approval_count": sum(1 for r in roster if r.get("approval_status") == "Pending"),
        "roster": roster
    }


def get_active_shift_for_time(target_dt=None) -> str:
    """Helper to detect active shift based on current time."""
    from datetime import datetime, time, timedelta

    target = target_dt or now_datetime()
    now_time = target.time()

    shifts = frappe.get_all(
        "Facility Shift",
        filters={"enabled": 1},
        fields=["name", "start_time", "end_time", "is_night_shift"]
    )

    def to_time_obj(val):
        if isinstance(val, time):
            return val
        if isinstance(val, timedelta):
            total_sec = int(val.total_seconds()) % 86400
            return time(hour=total_sec // 3600, minute=(total_sec % 3600) // 60, second=total_sec % 60)
        if isinstance(val, str):
            parts = val.split(":")
            return time(hour=int(parts[0]), minute=int(parts[1]), second=int(float(parts[2])) if len(parts) > 2 else 0)
        return time(0, 0, 0)

    for s in shifts:
        st = to_time_obj(s.start_time)
        et = to_time_obj(s.end_time)

        if s.is_night_shift:
            if now_time >= st or now_time <= et:
                return s.name
        else:
            if st <= now_time <= et:
                return s.name

    return shifts[0].name if shifts else None


@frappe.whitelist()
def get_on_duty_security_summary() -> dict:
    """
    Returns verified on-duty security guards and supervisors currently clocked-in.
    Used for Telegram bot on-duty security quick lookups and emergency routing.
    """
    today = nowdate()
    on_duty_attendances = frappe.get_all(
        "Facility Staff Attendance",
        filters={
            "attendance_date": today,
            "status": "Present",
            "out_time": ("is", "not set")
        },
        fields=["name", "staff", "staff_name", "role", "gate", "in_time", "shift"]
    )

    guards = []
    lines = []

    for att in on_duty_attendances:
        staff_doc = frappe.get_value("Facility Staff", att.staff, ["contact_number", "photo"], as_dict=True)
        phone = staff_doc.contact_number if staff_doc else ""
        item = {
            "name": att.staff_name,
            "role": att.role,
            "gate": att.gate or "Main Gate",
            "shift": att.shift,
            "in_time": str(att.in_time),
            "phone": phone
        }
        guards.append(item)
        lines.append(f"• 👮 *{att.staff_name}* ({att.role})\n  📍 Gate: `{item['gate']}` | 📞 `{phone or 'Via Gate Intercom'}` | In: {str(att.in_time)[11:16]}")

    if not lines:
        summary_text = "ℹ️ _No security personnel currently checked-in via electronic gate punch._\n📞 Main Gate 24x7 Security Intercom: `Ext 100`"
    else:
        summary_text = "*Current On-Duty Security & Supervisors:*\n\n" + "\n\n".join(lines)

    return {
        "on_duty_count": len(guards),
        "guards": guards,
        "summary_text": summary_text
    }


@frappe.whitelist()
def onboard_facility_staff(
    full_name: str,
    agency: str,
    role: str,
    contact_number: str = None,
    gate_assigned: str = "All Gates",
    government_id_type: str = "Aadhaar",
    government_id_number: str = None,
    police_verification_status: str = "Pending",
    notes: str = None
) -> dict:
    """
    Called by Agency Manager (or Committee) to onboard a new staff member.
    If called by Agency Manager: automatically enters with approval_status='Pending'.
    If called by System Manager / Committee: enters as 'Approved'.
    """
    user = frappe.session.user
    roles = frappe.get_roles(user)
    is_admin = "System Manager" in roles or "Society Committee" in roles or "Society Committee Member" in roles or user == "Administrator" or frappe.db.exists("Committee Member", {"member_name": user, "status": "Active"})

    if not is_admin:
        # Verify user is the authorized agency manager for this agency
        authorized_agency = frappe.db.get_value("Facility Agency", {"portal_user": user}, "agency_name")
        if not authorized_agency or authorized_agency != agency:
            frappe.throw(_("Unauthorized: You can only onboard staff for your assigned agency ({0})").format(authorized_agency or "None"))

    doc = frappe.get_doc({
        "doctype": "Facility Staff",
        "full_name": full_name.strip(),
        "agency": agency,
        "role": role,
        "contact_number": contact_number,
        "gate_assigned": gate_assigned,
        "government_id_type": government_id_type,
        "government_id_number": government_id_number,
        "police_verification_status": police_verification_status,
        "approval_status": "Approved" if is_admin else "Pending",
        "status": "Active" if is_admin else "Inactive",
        "approved_by": user if is_admin else None,
        "approval_date": nowdate() if is_admin else None,
        "notes": notes
    })
    doc.insert(ignore_permissions=True)

    status_msg = _("Staff {0} ({1}) onboarded and activated.").format(doc.full_name, doc.name) if is_admin else _("Staff {0} ({1}) submitted for Committee Approval.").format(doc.full_name, doc.name)

    return {
        "status": "success",
        "staff_id": doc.name,
        "approval_status": doc.approval_status,
        "message": status_msg
    }


@frappe.whitelist()
def review_facility_staff(staff_id: str, action: str, remarks: str = None) -> dict:
    """
    Committee action to Approve or Reject agency-onboarded staff.
    action: 'Approved' or 'Rejected'
    """
    user = frappe.session.user
    roles = frappe.get_roles(user)
    if not ("System Manager" in roles or "Society Committee" in roles or "Society Committee Member" in roles or user == "Administrator" or frappe.db.exists("Committee Member", {"member_name": user, "status": "Active"})):
        frappe.throw(_("Unauthorized: Only Committee Members or System Managers can approve staff."))

    if not staff_id or not frappe.db.exists("Facility Staff", staff_id):
        frappe.throw(_("Staff record not found: {0}").format(staff_id))

    doc = frappe.get_doc("Facility Staff", staff_id)
    doc.approval_status = action
    doc.approved_by = user
    doc.approval_date = nowdate()

    if action == "Approved":
        doc.status = "Active"
        doc.rejection_remarks = None
    else:
        doc.status = "Inactive"
        doc.rejection_remarks = remarks

    doc.save(ignore_permissions=True)

    return {
        "status": "success",
        "staff_id": doc.name,
        "approval_status": doc.approval_status,
        "message": _("Staff {0} has been {1}.").format(doc.full_name, action)
    }



@frappe.whitelist()
def assign_duty_post(attendance_id: str = None, staff_id: str = None, duty_post: str = None) -> dict:
    """
    Dynamically assign or update physical post and cost center for a staff attendance record.
    """
    if not duty_post or not frappe.db.exists("Facility Duty Post", duty_post):
        frappe.throw(_("Invalid Duty Post: {0}").format(duty_post))

    cost_center = frappe.db.get_value("Facility Duty Post", duty_post, "cost_center")

    if not attendance_id and staff_id:
        attendance_id = frappe.db.get_value(
            "Facility Staff Attendance",
            {"staff": staff_id, "attendance_date": nowdate(), "out_time": ("is", "not set")},
            "name"
        )

    if attendance_id:
        frappe.db.set_value("Facility Staff Attendance", attendance_id, {
            "duty_post": duty_post,
            "cost_center": cost_center
        })

    if staff_id:
        # Also update staff default
        frappe.db.set_value("Facility Staff", staff_id, "default_duty_post", duty_post)

    frappe.db.commit()

    return {
        "status": "success",
        "duty_post": duty_post,
        "cost_center": cost_center,
        "message": _("Duty post assigned to {0} (Cost Center: {1})").format(duty_post, cost_center)
    }


@frappe.whitelist()
def record_shift_muster(agency: str, shift: str, category: str, muster_photo: str, reported_count: int = 0, notes: str = None) -> dict:
    """
    Records a shift lineup group photo and muster headcount before/during roll call.
    """
    user = frappe.session.user
    doc = frappe.get_doc({
        "doctype": "Facility Shift Muster",
        "agency": agency,
        "shift_date": nowdate(),
        "shift": shift,
        "category": category,
        "muster_photo": muster_photo,
        "reported_count": reported_count,
        "supervisor_in_charge": user,
        "briefing_notes": notes
    })
    doc.insert(ignore_permissions=True)

    return {
        "status": "success",
        "muster_id": doc.name,
        "photo": doc.muster_photo,
        "message": _("Shift Lineup Group Photo saved successfully for {0}.").format(shift)
    }
