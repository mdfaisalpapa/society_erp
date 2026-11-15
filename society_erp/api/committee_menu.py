import frappe
from society_erp.api.utils import portal_api
from society_erp.api.sso import create_portal_link
from society_erp.www.resident.settings.index import get_tile_settings
from society_erp.www.resident.committee.index import get_committee_data


@frappe.whitelist()
@portal_api
def get_committee_sub_tiles(for_user: str = None) -> dict:
    """
    Returns all committee sub-tiles dynamically matching `/resident/committee`,
    respecting Master Portal Settings with live pending counts and deep-link routes.
    """
    user_email = (for_user or frappe.session.user or "").strip().lower()

    # Verify committee status
    cm = frappe.db.get_value(
        "Committee Member",
        {"member_name": user_email, "status": "Active"},
        ["name", "designation"],
        as_dict=True
    )
    if not cm and frappe.session.user != "Administrator" and "System Manager" not in frappe.get_roles(user_email):
        return {"authorized": False, "tiles": [], "count": 0}

    # Tile switches for committee
    tile_cfg = get_tile_settings()
    comm_tiles = tile_cfg.get("committee", {})

    enable_sos = frappe.db.get_single_value("Society ERP Settings", "enable_emergency_sos")
    enable_emergency_sos = bool(int(enable_sos)) if enable_sos is not None else True

    # Get live counts
    counts = {
        "tenants_pending": frappe.db.count("Tenants", {"registration_status": "Pending"}),
        "vehicles_pending": frappe.db.count("Resident Vehicle", {"approval_status": "Pending"}),
        "permits_pending": frappe.db.count("Work Permit", {"status": "Pending"}),
        "pets_pending": frappe.db.count("Resident Pets", {"approval_status": "Pending"}),
        "family_pending": frappe.db.count("Family Members", {"registration_status": "Pending"}),
        "tickets_open": frappe.db.count("Maintenance Ticket", {"status": "Open"}),
        "facility_bookings_pending": frappe.db.count("Facility Booking", {"status": "Pending Approval"}),
        "classifieds_pending": frappe.db.count("Resident Classified", {"approval_status": "Pending Approval"}),
        "resolutions_pending": 0,
        "facility_on_duty": frappe.db.count("Facility Staff Attendance", {"attendance_date": frappe.utils.nowdate(), "status": "Present", "out_time": ("is", "not set")}),
    }
    if cm and cm.name:
        counts["resolutions_pending"] = frappe.db.count(
            "Resolution Signatory",
            {"signatory": cm.name, "signature_status": "Pending"}
        )

    # Streamlined Single-Gateway pattern: concise summary + single WebApp CTA button
    sub_tiles = []
    canvas_route = "/resident/committee?standalone=1"
    sso_canvas = create_portal_link(user_email, target_route=canvas_route)
    sub_tiles.append({
        "id": "comm_canvas",
        "module": "committee_canvas",
        "label": "🌐 Open Committee Portal",
        "title": "Open Committee Portal",
        "icon": "🌐",
        "badge": 0,
        "badge_type": "primary",
        "value": "open_comm_canvas",
        "web_app_url": sso_canvas.get("url"),
        "route": canvas_route
    })

    # Return to Main Menu option
    sub_tiles.append({
        "id": "comm_menu_back",
        "module": "menu",
        "label": "🔙 Back to Main Menu",
        "title": "Main Menu",
        "icon": "🔙",
        "badge": 0,
        "value": "menu"
    })

    c_ten = counts.get("tenants_pending", 0)
    c_veh = counts.get("vehicles_pending", 0)
    c_pmt = counts.get("permits_pending", 0)
    c_fam = counts.get("family_pending", 0)
    c_pet = counts.get("pets_pending", 0)
    c_fac = counts.get("facility_bookings_pending", 0)
    c_cls = counts.get("classifieds_pending", 0)
    c_res_mgmt = c_ten + c_veh + c_pmt + c_fam + c_pet + c_fac + c_cls
    c_tkt = counts.get("tickets_open", 0)
    c_res = counts.get("resolutions_pending", 0)
    c_on_duty = counts.get("facility_on_duty", 0)

    summary_lines = [
        f"• Pending Approvals: *{c_res_mgmt}* (Tenants, Vehicles, Permits)",
        f"• Open Helpdesk Tickets: *{c_tkt}*",
        f"• Pending Resolutions: *{c_res}*",
        f"• Facility Staff on Duty: *{c_on_duty}*",
        "",
        "Tap below to review and manage all committee operations in the portal:"
    ]
    summary_text = "\n".join(summary_lines)

    return {
        "authorized": True,
        "role": cm.designation if cm else "Committee",
        "sub_tiles": sub_tiles,
        "count": len(sub_tiles),
        "summary_text": summary_text
    }
