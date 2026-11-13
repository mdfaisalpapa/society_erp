import frappe
from frappe import _
from frappe.utils import now_datetime


def get_context(context):
    ticket_id = frappe.form_dict.get("id")
    claim_key = frappe.form_dict.get("key")

    context.no_cache = 1
    context.title = "Maintenance Job Card"

    if not ticket_id or not frappe.db.exists("Maintenance Ticket", ticket_id):
        context.error = "Invalid or missing Maintenance Ticket ID."
        return

    doc = frappe.get_doc("Maintenance Ticket", ticket_id)

    # Validate claim key
    if not claim_key or doc.claim_key != claim_key:
        context.error = "Unauthorized magic link or expired security token."
        return

    context.ticket = doc
    context.ticket_id = ticket_id
    context.claim_key = claim_key
    context.error = None

    # Load active on-duty facility staff list for claiming
    context.staff_list = frappe.get_all(
        "Facility Staff",
        filters={"status": "Active", "approval_status": "Approved"},
        fields=["name", "full_name", "role", "contact_number"]
    )


@frappe.whitelist(allow_guest=True)
def claim_and_update_job(ticket_id: str, claim_key: str, action: str, staff_id: str = None, remarks: str = None, completion_photo: str = None):
    """
    Publicly callable via secure claim key token from the magic link.
    action: 'claim', 'start', 'complete'
    """
    if not ticket_id or not frappe.db.exists("Maintenance Ticket", ticket_id):
        frappe.throw(_("Invalid ticket"))

    doc = frappe.get_doc("Maintenance Ticket", ticket_id)
    if not claim_key or doc.claim_key != claim_key:
        frappe.throw(_("Invalid or expired authorization key"), frappe.PermissionError)

    now_dt = now_datetime()

    if action == "claim":
        if not staff_id or not frappe.db.exists("Facility Staff", staff_id):
            frappe.throw(_("Please select a valid staff member"))
        staff = frappe.get_doc("Facility Staff", staff_id)
        doc.assigned_staff = staff.name
        doc.claimed_by = f"{staff.full_name} ({staff.role})"
        doc.claimed_on = now_dt
        doc.status = "Assigned"
        if not doc.work_started_on:
            doc.work_started_on = now_dt
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {
            "success": True,
            "message": f"Job claimed by {staff.full_name}!",
            "status": doc.status,
            "claimed_by": doc.claimed_by
        }

    elif action == "start":
        doc.work_started_on = now_dt
        doc.status = "Assigned"
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {"success": True, "message": "Work started timestamp recorded.", "status": doc.status}

    elif action == "complete":
        doc.status = "Resolved"
        doc.work_completed_on = now_dt
        if completion_photo:
            doc.completion_photo = completion_photo
        if remarks:
            existing = doc.resolution_remarks or ""
            doc.resolution_remarks = f"{existing}\n[Technician Completion ({now_dt.strftime('%d-%m %H:%M')}]: {remarks}".strip()

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        # Notify QRT on completion
        try:
            from society_erp.api.qrt_maintenance import send_telegram_message
            tech_name = doc.claimed_by or (frappe.db.get_value("Facility Staff", doc.assigned_staff, "full_name") if doc.assigned_staff else "Technician")
            msg = (
                f"✅ *Job Completed — #{doc.name}*\n"
                f"🏢 *Flat:* `{doc.resident or 'Common'}`\n"
                f"🛠️ *Category:* `{doc.category}`\n"
                f"👷 *Completed By:* `{tech_name}`\n"
                f"📝 *Remarks:* _{remarks or 'Rectification finished'}_"
            )
            send_telegram_message(msg)
        except Exception:
            pass

        return {
            "success": True,
            "message": f"Ticket #{doc.name} marked Resolved! Great job.",
            "status": doc.status
        }

    frappe.throw(_("Invalid action"))
