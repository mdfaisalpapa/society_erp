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

    # Build streamlined 4 Functional Pillars for Committee (strictly <= 10 items for WhatsApp & Telegram UX)
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

    # Pillar 1: Resident Management (Tenants, Vehicles, Permits, Family, Pets, Hall Bookings, Classifieds)
    c_ten = counts.get("tenants_pending", 0)
    c_veh = counts.get("vehicles_pending", 0)
    c_pmt = counts.get("permits_pending", 0)
    c_fam = counts.get("family_pending", 0)
    c_pet = counts.get("pets_pending", 0)
    c_fac = counts.get("facility_bookings_pending", 0)
    c_cls = counts.get("classifieds_pending", 0)
    c_res_mgmt = c_ten + c_veh + c_pmt + c_fam + c_pet + c_fac + c_cls

    route_res_mgmt = "/resident/committee?cat=resident_mgmt&tab=tenants&standalone=1#pane-tenants"
    sso_res_mgmt = create_portal_link(user_email, target_route=route_res_mgmt)
    sub_tiles.append({
        "id": "comm_resident_mgmt",
        "module": "resident_mgmt",
        "label": f"👥 Resident Mgmt ({c_res_mgmt} Pending)" if c_res_mgmt > 0 else "👥 Resident Mgmt",
        "title": "Resident Management",
        "icon": "👥",
        "desc": "Tenants, Vehicles, Permits, Family, Pets, Halls",
        "badge": c_res_mgmt,
        "badge_type": "warning" if c_res_mgmt > 0 else "secondary",
        "value": "open_comm_resident_mgmt",
        "web_app_url": sso_res_mgmt.get("url"),
        "route": route_res_mgmt
    })

    # Pillar 2: Facility Operations & Monitoring (Tickets, Staff, Housekeeping Proofs)
    c_tkt = counts.get("tickets_open", 0)
    c_on_duty = counts.get("facility_on_duty", 0)
    route_fac_ops = "/resident/committee?cat=facility_ops&tab=tickets&standalone=1#pane-tickets"
    sso_fac_ops = create_portal_link(user_email, target_route=route_fac_ops)
    sub_tiles.append({
        "id": "comm_facility_ops",
        "module": "facility_ops",
        "label": f"🛠️ Facility Operations ({c_tkt} Open)" if c_tkt > 0 else "🛠️ Facility Operations",
        "title": "Facility Operations",
        "icon": "🛠️",
        "desc": "Helpdesk Tickets, Security/Staff, Housekeeping",
        "badge": c_tkt,
        "badge_type": "danger" if c_tkt > 0 else "secondary",
        "value": "open_comm_facility_ops",
        "web_app_url": sso_fac_ops.get("url"),
        "route": route_fac_ops
    })

    # Pillar 3: Committee Governance (Notices, Board Resolutions)
    c_res = counts.get("resolutions_pending", 0)
    route_gov = "/resident/committee?cat=governance&tab=notices&standalone=1#pane-notices"
    sso_gov = create_portal_link(user_email, target_route=route_gov)
    sub_tiles.append({
        "id": "comm_governance",
        "module": "governance",
        "label": f"⚖️ Committee Governance ({c_res} Pending)" if c_res > 0 else "⚖️ Committee Governance",
        "title": "Committee Governance",
        "icon": "⚖️",
        "desc": "Society Notices & Board Resolutions",
        "badge": c_res,
        "badge_type": "warning" if c_res > 0 else "secondary",
        "value": "open_comm_governance",
        "web_app_url": sso_gov.get("url"),
        "route": route_gov
    })

    # Pillar 4: Asset & Plant Monitoring (Water/Sumps, OHT Tanks, AMC, STP Chemicals)
    c_chem = counts.get("chemical_low_count", 0)
    route_assets = "/resident/committee?cat=plant_assets&tab=water_log&standalone=1#pane-water_log"
    sso_assets = create_portal_link(user_email, target_route=route_assets)
    sub_tiles.append({
        "id": "comm_plant_assets",
        "module": "plant_assets",
        "label": f"💧 Asset & Plant Monitoring ({c_chem} Alert)" if c_chem > 0 else "💧 Asset & Plant Monitoring",
        "title": "Asset & Plant Monitoring",
        "icon": "💧",
        "desc": "Water Sumps, Tank Cleaning, Asset AMC, STP Chemicals",
        "badge": c_chem,
        "badge_type": "danger" if c_chem > 0 else "secondary",
        "value": "open_comm_plant_assets",
        "web_app_url": sso_assets.get("url"),
        "route": route_assets
    })

    # 5. Add Return to Main Menu option at the bottom
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
