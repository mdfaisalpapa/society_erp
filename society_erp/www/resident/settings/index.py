import json
import frappe
from frappe import _

# Master list of all controllable tiles on the resident portal
ALL_PORTAL_TILES = [
    {
        "id": "book_facility",
        "title": "Book Facility & Amenities",
        "icon": "🏛️",
        "desc": "Community Hall & club facility shift booking",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "classifieds",
        "title": "Resident Classifieds",
        "icon": "📢",
        "desc": "Community marketplace for rentals, used items & services",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "emergency",
        "title": "Emergency SOS & Contacts",
        "icon": "🚨",
        "desc": "Main Gate security, manager, police & ambulance quick dial",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "visitors",
        "title": "Gate Pass & Visitors",
        "icon": "🎫",
        "desc": "Visitor entry logs, OTP passes & delivery pre-approval",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "maintenance",
        "title": "Maintenance Tickets",
        "icon": "🛠️",
        "desc": "Raise and track tickets for flat and common issues",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "vehicles",
        "title": "Vehicles & Parking",
        "icon": "🚗",
        "desc": "Manage vehicles, parking allocations & stickers",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "work_permits",
        "title": "Work Permits",
        "icon": "👷",
        "desc": "Contractor interior and repair permit passes",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
        "note": "Owners / Committee"
    },
    {
        "id": "tenants",
        "title": "Tenant Management",
        "icon": "🏠",
        "desc": "Register leases, tenants & agreements",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
        "note": "Owners / Committee"
    },
    {
        "id": "family",
        "title": "Family Members",
        "icon": "👨‍👩‍👧‍👦",
        "desc": "Register family members and upload ID proofs",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "pets",
        "title": "Resident Pets",
        "icon": "🐾",
        "desc": "Pet registrations and vaccination records",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "staff",
        "title": "Domestic Staff",
        "icon": "🧹",
        "desc": "Maids, drivers & cooks gate attendance & reviews",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "notices",
        "title": "Notice Board",
        "icon": "📋",
        "desc": "Official circulars, general announcements & resolutions",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "voting",
        "title": "Polls & Voting",
        "icon": "🗳️",
        "desc": "Secret ballot voting, election electorate & candidate lists",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "dues",
        "title": "Check Dues & Invoices",
        "icon": "📊",
        "desc": "Maintenance charges, invoices, receipts and dues ledger",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "financials",
        "title": "Society Financials",
        "icon": "📈",
        "desc": "Audited Profit & Loss statement and Balance Sheet",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "profile",
        "title": "Flat Details & Profile",
        "icon": "👤",
        "desc": "Property specifications, UDS, EB service & Tax numbers",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "owners",
        "title": "Owner Details",
        "icon": "📜",
        "desc": "Flat ownership records, registered owner names and contacts",
        "default_resident": 1,
        "default_committee": 1,
        "default_agency": 0,
        "applies_to_resident": True,
        "applies_to_committee": True,
        "applies_to_agency": False,
        "note": "Owners / Committee"
    },
    {
        "id": "facility_staff",
        "title": "Security & Staff Roster",
        "icon": "🛡️",
        "desc": "Staff onboarding, QR badge scanning, duty roster & muster roll calls",
        "default_resident": 0,
        "default_committee": 1,
        "default_agency": 1,
        "applies_to_resident": False,
        "applies_to_committee": True,
        "applies_to_agency": True,
    },
    {
        "id": "water_log",
        "title": "Water Sump & Pump Telemetry",
        "icon": "💧",
        "desc": "Sump depth levels, gauge photos, and OHT pump run monitoring",
        "default_resident": 0,
        "default_committee": 1,
        "default_agency": 1,
        "applies_to_resident": False,
        "applies_to_committee": True,
        "applies_to_agency": True,
    },
    {
        "id": "water_tanker",
        "title": "Water Tanker Inflow",
        "icon": "🚚",
        "desc": "Commercial water tanker arrivals, delivery challans & capacity logs",
        "default_resident": 0,
        "default_committee": 1,
        "default_agency": 1,
        "applies_to_resident": False,
        "applies_to_committee": True,
        "applies_to_agency": True,
    },
    {
        "id": "cleaning_log",
        "title": "Housekeeping Floor Proofs",
        "icon": "🧹",
        "desc": "Corridor and common area cleaning before/after inspection photos",
        "default_resident": 0,
        "default_committee": 1,
        "default_agency": 1,
        "applies_to_resident": False,
        "applies_to_committee": True,
        "applies_to_agency": True,
    },
    {
        "id": "tank_cleaning",
        "title": "OHT & Sump Cleaning",
        "icon": "🚰",
        "desc": "Periodic rooftop Overhead Tank and ground sump desiltation proofs",
        "default_resident": 0,
        "default_committee": 1,
        "default_agency": 1,
        "applies_to_resident": False,
        "applies_to_committee": True,
        "applies_to_agency": True,
    },
    {
        "id": "amc_log",
        "title": "Asset & Equipment AMC",
        "icon": "⚙️",
        "desc": "Lifts, DG, STP, Fire Safety & pump AMC servicing and certificate logs",
        "default_resident": 0,
        "default_committee": 1,
        "default_agency": 1,
        "applies_to_resident": False,
        "applies_to_committee": True,
        "applies_to_agency": True,
    }
]


def get_tile_settings():
    """
    Returns separate dictionaries for residents, committee members, and agency portal:
    {
        "residents": { "book_facility": True/False, ... },
        "committee": { "book_facility": True/False, ... },
        "agency": { "water_log": True/False, ... }
    }
    """
    val = frappe.db.get_single_value("Society ERP Settings", "enabled_portal_tiles")
    settings = {}
    if val:
        try:
            settings = json.loads(val) if isinstance(val, str) else val
        except Exception:
            settings = {}

    residents_dict = {}
    committee_dict = {}
    agency_dict = {}

    for tile in ALL_PORTAL_TILES:
        tid = tile["id"]

        if "residents" in settings and isinstance(settings["residents"], dict):
            res_val = settings["residents"].get(tid, tile.get("default_resident", 1))
        else:
            res_val = settings.get(tid, tile.get("default_resident", 1))

        if "committee" in settings and isinstance(settings["committee"], dict):
            comm_val = settings["committee"].get(tid, tile.get("default_committee", 1))
        else:
            comm_val = settings.get(tid, tile.get("default_committee", 1))

        if "agency" in settings and isinstance(settings["agency"], dict):
            agy_val = settings["agency"].get(tid, tile.get("default_agency", 1))
        else:
            agy_val = settings.get(tid, tile.get("default_agency", 1))

        residents_dict[tid] = bool(int(res_val))
        committee_dict[tid] = bool(int(comm_val))
        agency_dict[tid] = bool(int(agy_val))

    return {
        "residents": residents_dict,
        "committee": committee_dict,
        "agency": agency_dict
    }


def is_system_manager(user=None):
    user = user or frappe.session.user
    if not user or user == "Guest":
        return False
    roles = frappe.get_roles(user)
    return "System Manager" in roles or user == "Administrator"


def get_context(context):
    context.is_standalone = bool(frappe.form_dict.get("standalone"))
    if context.is_standalone:
        context.no_header = True
        context.no_sidebar = True

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    user = frappe.session.user
    context.no_cache = 1
    context.user = user
    context.title = "Settings & Notifications"
    context.is_system_manager = is_system_manager(user)

    tile_statuses = get_tile_settings()
    tiles_list = []
    for tile in ALL_PORTAL_TILES:
        tid = tile["id"]
        tiles_list.append({
            **tile,
            "enabled_resident": tile_statuses["residents"].get(tid, True),
            "enabled_committee": tile_statuses["committee"].get(tid, True),
            "enabled_agency": tile_statuses["agency"].get(tid, True),
        })
    context.portal_tiles = tiles_list
    return context


@frappe.whitelist()
def save_tile_toggle(tile_id, target_role, enabled):
    """
    Whitelisted API for System Managers to toggle a feature for 'residents', 'committee', or 'agency'.
    target_role must be 'residents', 'committee', or 'agency'.
    """
    if not is_system_manager():
        frappe.throw(_("Permission Denied: Only users with the System Manager role can configure portal tile switches."), frappe.PermissionError)

    if target_role not in ("residents", "committee", "agency"):
        frappe.throw(_("Invalid target role. Must be 'residents', 'committee', or 'agency'."))

    val = frappe.db.get_single_value("Society ERP Settings", "enabled_portal_tiles")
    settings = {}
    if val:
        try:
            settings = json.loads(val) if isinstance(val, str) else val
        except Exception:
            settings = {}

    if "residents" not in settings or not isinstance(settings["residents"], dict):
        old_data = dict(settings)
        settings = {
            "residents": dict(old_data),
            "committee": dict(old_data),
            "agency": {}
        }
    if "committee" not in settings or not isinstance(settings["committee"], dict):
        settings["committee"] = {}
    if "agency" not in settings or not isinstance(settings["agency"], dict):
        settings["agency"] = {}

    val_int = 1 if (str(enabled).lower() in ("1", "true")) else 0
    settings[target_role][tile_id] = val_int

    frappe.db.set_single_value("Society ERP Settings", "enabled_portal_tiles", json.dumps(settings))

    # Keep enable_emergency_sos in sync for residents
    if tile_id == "emergency" and target_role == "residents":
        frappe.db.set_single_value("Society ERP Settings", "enable_emergency_sos", val_int)

    frappe.db.commit()

    if target_role == "residents":
        role_label = "Residents"
    elif target_role == "committee":
        role_label = "Committee Members"
    else:
        role_label = "Agency Portal"
    status_label = "ENABLED" if val_int else "DISABLED"

    return {
        "status": "success",
        "tile_id": tile_id,
        "target_role": target_role,
        "enabled": bool(val_int),
        "message": _("'{0}' is now {1} for {2}.").format(tile_id, status_label, role_label)
    }
