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
    }
    if cm and cm.name:
        counts["resolutions_pending"] = frappe.db.count(
            "Resolution Signatory",
            {"signatory": cm.name, "signature_status": "Pending"}
        )

    # Build sub-tiles in exact sequence of committeeTabs in resident/committee/index.html
    sub_tiles = []

    # 1. Tenants
    if comm_tiles.get("tenants", True):
        c = counts.get("tenants_pending", 0)
        route = "/resident/committee?tab=tenants&standalone=1#pane-tenants"
        sso = create_portal_link(user_email, target_route=route)
        sub_tiles.append({
            "id": "comm_tenants",
            "module": "tenants",
            "label": f"🏠 Tenants ({c} Pending)" if c > 0 else "🏠 Tenants",
            "title": "Tenants",
            "icon": "🏠",
            "badge": c,
            "badge_type": "warning" if c > 0 else "secondary",
            "value": "open_comm_tenants",
            "web_app_url": sso.get("url"),
            "route": route
        })

    # 2. Vehicles
    if comm_tiles.get("vehicles", True):
        c = counts.get("vehicles_pending", 0)
        route = "/resident/committee?tab=vehicles&standalone=1#pane-vehicles"
        sso = create_portal_link(user_email, target_route=route)
        sub_tiles.append({
            "id": "comm_vehicles",
            "module": "vehicles",
            "label": f"🚗 Vehicles ({c} Pending)" if c > 0 else "🚗 Vehicles",
            "title": "Vehicles",
            "icon": "🚗",
            "badge": c,
            "badge_type": "warning" if c > 0 else "secondary",
            "value": "open_comm_vehicles",
            "web_app_url": sso.get("url"),
            "route": route
        })

    # 3. Work Permits
    if comm_tiles.get("work_permits", True):
        c = counts.get("permits_pending", 0)
        route = "/resident/committee?tab=work_permits&standalone=1#pane-work_permits"
        sso = create_portal_link(user_email, target_route=route)
        sub_tiles.append({
            "id": "comm_permits",
            "module": "work_permits",
            "label": f"👷 Permits ({c} Pending)" if c > 0 else "👷 Permits",
            "title": "Permits",
            "icon": "👷",
            "badge": c,
            "badge_type": "warning" if c > 0 else "secondary",
            "value": "open_comm_permits",
            "web_app_url": sso.get("url"),
            "route": route
        })

    # 4. Family Members
    if comm_tiles.get("family", True):
        c = counts.get("family_pending", 0)
        route = "/resident/committee?tab=family&standalone=1#pane-family"
        sso = create_portal_link(user_email, target_route=route)
        sub_tiles.append({
            "id": "comm_family",
            "module": "family",
            "label": f"👨‍👩‍👦 Family ({c} Pending)" if c > 0 else "👨‍👩‍👦 Family",
            "title": "Family",
            "icon": "👨‍👩‍👦",
            "badge": c,
            "badge_type": "warning" if c > 0 else "secondary",
            "value": "open_comm_family",
            "web_app_url": sso.get("url"),
            "route": route
        })

    # 5. Resident Pets
    if comm_tiles.get("pets", True):
        c = counts.get("pets_pending", 0)
        route = "/resident/committee?tab=pets&standalone=1#pane-pets"
        sso = create_portal_link(user_email, target_route=route)
        sub_tiles.append({
            "id": "comm_pets",
            "module": "pets",
            "label": f"🐾 Pets ({c} Pending)" if c > 0 else "🐾 Pets",
            "title": "Pets",
            "icon": "🐾",
            "badge": c,
            "badge_type": "warning" if c > 0 else "secondary",
            "value": "open_comm_pets",
            "web_app_url": sso.get("url"),
            "route": route
        })

    # 6. Maintenance Tickets
    if comm_tiles.get("maintenance", True):
        c = counts.get("tickets_open", 0)
        route = "/resident/committee?tab=tickets&standalone=1#pane-tickets"
        sso = create_portal_link(user_email, target_route=route)
        sub_tiles.append({
            "id": "comm_tickets",
            "module": "tickets",
            "label": f"🛠️ Tickets ({c} Open)" if c > 0 else "🛠️ Tickets",
            "title": "Tickets",
            "icon": "🛠️",
            "badge": c,
            "badge_type": "danger" if c > 0 else "secondary",
            "value": "open_comm_tickets",
            "web_app_url": sso.get("url"),
            "route": route
        })

    # 7. Hall Bookings
    if comm_tiles.get("book_facility", True):
        c = counts.get("facility_bookings_pending", 0)
        route = "/resident/committee?tab=facility_bookings&standalone=1#pane-facility_bookings"
        sso = create_portal_link(user_email, target_route=route)
        sub_tiles.append({
            "id": "comm_facilities",
            "module": "facility_bookings",
            "label": f"🏛️ Hall Bookings ({c} Pending)" if c > 0 else "🏛️ Hall Bookings",
            "title": "Hall Bookings",
            "icon": "🏛️",
            "badge": c,
            "badge_type": "warning" if c > 0 else "secondary",
            "value": "open_comm_facilities",
            "web_app_url": sso.get("url"),
            "route": route
        })

    # 8. Classifieds
    if comm_tiles.get("classifieds", True):
        c = counts.get("classifieds_pending", 0)
        route = "/resident/committee?tab=classifieds&standalone=1#pane-classifieds"
        sso = create_portal_link(user_email, target_route=route)
        sub_tiles.append({
            "id": "comm_classifieds",
            "module": "classifieds",
            "label": f"📢 Classifieds ({c} Pending)" if c > 0 else "📢 Classifieds",
            "title": "Classifieds",
            "icon": "📢",
            "badge": c,
            "badge_type": "warning" if c > 0 else "secondary",
            "value": "open_comm_classifieds",
            "web_app_url": sso.get("url"),
            "route": route
        })

    # 9. Notice Board
    if comm_tiles.get("notices", True):
        route = "/resident/committee?tab=notices&standalone=1#pane-notices"
        sso = create_portal_link(user_email, target_route=route)
        sub_tiles.append({
            "id": "comm_notices",
            "module": "notices",
            "label": "📋 Post Notices",
            "title": "Notices",
            "icon": "📋",
            "badge": 0,
            "badge_type": "secondary",
            "value": "open_comm_notices",
            "web_app_url": sso.get("url"),
            "route": route
        })

    # 10. Resolutions
    c = counts.get("resolutions_pending", 0)
    route = "/resident/committee?tab=resolutions&standalone=1#pane-resolutions"
    sso = create_portal_link(user_email, target_route=route)
    sub_tiles.append({
        "id": "comm_resolutions",
        "module": "resolutions",
        "label": f"⚖️ Resolutions ({c} Pending Vote)" if c > 0 else "⚖️ Resolutions",
        "title": "Resolutions",
        "icon": "⚖️",
        "badge": c,
        "badge_type": "warning" if c > 0 else "secondary",
        "value": "open_comm_resolutions",
        "web_app_url": sso.get("url"),
        "route": route
    })

    # 11. Emergency SOS
    if enable_emergency_sos and comm_tiles.get("emergency", True):
        route = "/resident/committee?tab=emergency&standalone=1#pane-emergency"
        sso = create_portal_link(user_email, target_route=route)
        sub_tiles.append({
            "id": "comm_emergency",
            "module": "emergency",
            "label": "🚨 Emergency Directory",
            "title": "Emergency SOS",
            "icon": "🚨",
            "badge": 0,
            "badge_type": "danger",
            "value": "open_comm_emergency",
            "web_app_url": sso.get("url"),
            "route": route
        })

    # Add Return to Main Menu option at the bottom
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
        summary_lines.append(f"• {t['icon']} *{t['title']}*: {t['badge']} Pending" if t['badge'] > 0 else f"• {t['icon']} *{t['title']}*")

    summary_text = "\n".join(summary_lines)

    return {
        "authorized": True,
        "role": cm.designation if cm else "Committee",
        "sub_tiles": sub_tiles,
        "count": len(sub_tiles),
        "summary_text": summary_text
    }
