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

    # Build streamlined committee sub-tiles (strictly <= 10 items for WhatsApp & Telegram UX)
    sub_tiles = []

    # 1. Direct WebApp Canvas Button
    canvas_route = "/resident/committee?standalone=1"
    sso_canvas = create_portal_link(user_email, target_route=canvas_route)
    sub_tiles.append({
        "id": "comm_canvas",
        "module": "committee_canvas",
        "label": "🌐 Full Committee Canvas",
        "title": "Full Committee Portal",
        "icon": "🌐",
        "badge": 0,
        "badge_type": "primary",
        "value": "open_comm_canvas",
        "web_app_url": sso_canvas.get("url"),
        "route": canvas_route
    })

    # 2. Tenants & Occupancy (Tenants + Family Pending)
    c_ten = counts.get("tenants_pending", 0)
    c_fam = counts.get("family_pending", 0)
    c_res_total = c_ten + c_fam
    route_ten = "/resident/committee?tab=tenants&standalone=1#pane-tenants"
    sso_ten = create_portal_link(user_email, target_route=route_ten)
    sub_tiles.append({
        "id": "comm_tenants",
        "module": "tenants",
        "label": f"🏠 Tenants & Residents ({c_res_total} Pending)" if c_res_total > 0 else "🏠 Tenants & Residents",
        "title": "Tenants & Residents",
        "icon": "🏠",
        "badge": c_res_total,
        "badge_type": "warning" if c_res_total > 0 else "secondary",
        "value": "open_comm_tenants",
        "web_app_url": sso_ten.get("url"),
        "route": route_ten
    })

    # 3. Vehicles & Parking
    c_veh = counts.get("vehicles_pending", 0)
    route_veh = "/resident/committee?tab=vehicles&standalone=1#pane-vehicles"
    sso_veh = create_portal_link(user_email, target_route=route_veh)
    sub_tiles.append({
        "id": "comm_vehicles",
        "module": "vehicles",
        "label": f"🚗 Vehicles ({c_veh} Pending)" if c_veh > 0 else "🚗 Vehicles",
        "title": "Vehicles",
        "icon": "🚗",
        "badge": c_veh,
        "badge_type": "warning" if c_veh > 0 else "secondary",
        "value": "open_comm_vehicles",
        "web_app_url": sso_veh.get("url"),
        "route": route_veh
    })

    # 4. Tickets & Maintenance (Helpdesk + Work Permits)
    c_tkt = counts.get("tickets_open", 0)
    c_pmt = counts.get("permits_pending", 0)
    route_tkt = "/resident/committee?tab=tickets&standalone=1#pane-tickets"
    sso_tkt = create_portal_link(user_email, target_route=route_tkt)
    tkt_label = f"🛠️ Tickets & Permits ({c_tkt} Open)" if c_tkt > 0 else "🛠️ Tickets & Permits"
    if c_pmt > 0:
        tkt_label += f" • {c_pmt} Pmt"
    sub_tiles.append({
        "id": "comm_tickets",
        "module": "tickets",
        "label": tkt_label,
        "title": "Tickets & Maintenance",
        "icon": "🛠️",
        "badge": c_tkt + c_pmt,
        "badge_type": "danger" if (c_tkt + c_pmt) > 0 else "secondary",
        "value": "open_comm_tickets",
        "web_app_url": sso_tkt.get("url"),
        "route": route_tkt
    })

    # 5. Hall & Amenity Bookings
    c_fac = counts.get("facility_bookings_pending", 0)
    route_fac = "/resident/committee?tab=facility_bookings&standalone=1#pane-facility_bookings"
    sso_fac = create_portal_link(user_email, target_route=route_fac)
    sub_tiles.append({
        "id": "comm_facilities",
        "module": "facility_bookings",
        "label": f"🏛️ Hall Bookings ({c_fac} Pending)" if c_fac > 0 else "🏛️ Hall Bookings",
        "title": "Hall Bookings",
        "icon": "🏛️",
        "badge": c_fac,
        "badge_type": "warning" if c_fac > 0 else "secondary",
        "value": "open_comm_facilities",
        "web_app_url": sso_fac.get("url"),
        "route": route_fac
    })

    # 6. Circulars & Resolutions (Notices + Resolutions)
    c_res = counts.get("resolutions_pending", 0)
    route_res = "/resident/committee?tab=resolutions&standalone=1#pane-resolutions"
    sso_res = create_portal_link(user_email, target_route=route_res)
    sub_tiles.append({
        "id": "comm_resolutions",
        "module": "resolutions",
        "label": f"⚖️ Resolutions & Notices ({c_res} Pending)" if c_res > 0 else "⚖️ Resolutions & Notices",
        "title": "Resolutions & Notices",
        "icon": "⚖️",
        "badge": c_res,
        "badge_type": "warning" if c_res > 0 else "secondary",
        "value": "open_comm_resolutions",
        "web_app_url": sso_res.get("url"),
        "route": route_res
    })

    # 7. Facility & Agency Monitoring (Security, Water, Housekeeping, Tank, AMC, Chemicals)
    c_on_duty = counts.get("facility_on_duty", 0)
    route_fac_mgmt = "/resident/committee?tab=facility_staff&standalone=1#pane-facility_staff"
    sso_fac_mgmt = create_portal_link(user_email, target_route=route_fac_mgmt)
    sub_tiles.append({
        "id": "comm_agency_monitoring",
        "module": "agency_monitoring",
        "label": f"🏗️ Facility Monitoring ({c_on_duty} On Duty)" if c_on_duty > 0 else "🏗️ Facility Monitoring",
        "title": "Facility Agency Oversight",
        "icon": "🏗️",
        "badge": c_on_duty,
        "badge_type": "success" if c_on_duty > 0 else "secondary",
        "value": "open_comm_facility_monitoring",
        "web_app_url": sso_fac_mgmt.get("url"),
        "route": route_fac_mgmt
    })

    # 8. Add Return to Main Menu option at the bottom
    sub_tiles.append({
        "id": "comm_menu_back",
        "module": "menu",
        "label": "🔙 Back to Main Menu",
        "title": "Main Menu",
        "icon": "🔙",
        "badge": 0,
        "value": "menu"
    })

    summary_lines = []
    for t in sub_tiles:
        if t["value"] == "menu":
            summary_lines.append(f"• {t['icon']} *{t['title']}*")
        elif t.get("badge", 0) > 0:
            summary_lines.append(f"• {t['icon']} *{t['title']}*: {t['badge']} Pending / Open")
        else:
            summary_lines.append(f"• {t['icon']} *{t['title']}*")

    summary_text = "\n".join(summary_lines)

    return {
        "authorized": True,
        "role": cm.designation if cm else "Committee",
        "sub_tiles": sub_tiles,
        "count": len(sub_tiles),
        "summary_text": summary_text
    }
