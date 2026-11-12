import json
import frappe
from frappe import _

# Master list of all controllable tiles on the resident portal
ALL_PORTAL_TILES = [
    {
        "id": "committee",
        "title": "AoA Committee Portal Tile",
        "icon": "🏛️",
        "desc": "Main entrance tile to AoA Managing Committee member dashboard",
        "default_resident": 0, # Residents don't see this anyway
        "default_committee": 1,
        "applies_to_resident": False,
        "applies_to_committee": True,
        "note": "Only applicable to Committee Members"
    },
    {
        "id": "profile",
        "title": "Flat Details & Profile",
        "icon": "👤",
        "desc": "Property specifications, UDS, EB service & Tax numbers",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": False,
    },
    {
        "id": "owners",
        "title": "Owner Details",
        "icon": "📜",
        "desc": "Flat ownership records, registered owner names and contacts",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": False,
        "note": "Owners / Co-owners"
    },
    {
        "id": "dues",
        "title": "Check Dues & Invoices",
        "icon": "📊",
        "desc": "Maintenance charges, invoices, receipts and dues ledger",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": False,
    },
    {
        "id": "financials",
        "title": "Society Financials",
        "icon": "📈",
        "desc": "Audited Profit & Loss statement and Balance Sheet",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": False,
    },
    {
        "id": "tenants",
        "title": "Tenant Management",
        "icon": "🏠",
        "desc": "Resident lease registration / Committee tenant approval queue",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "book_facility",
        "title": "Book Facility & Amenities",
        "icon": "🏛️",
        "desc": "Resident hall booking / Committee hall booking approval queue",
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
        "applies_to_committee": False,
    },
    {
        "id": "maintenance",
        "title": "Maintenance Tickets",
        "icon": "🛠️",
        "desc": "Resident ticket creation / Committee maintenance oversight",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "vehicles",
        "title": "Vehicles & Parking",
        "icon": "🚗",
        "desc": "Resident vehicle registrations / Committee sticker approvals",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "family",
        "title": "Family Members",
        "icon": "👨‍👩‍👧‍👦",
        "desc": "Resident family records / Committee ID proof verification queue",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "staff",
        "title": "Domestic Staff",
        "icon": "🧹",
        "desc": "Maid, driver & cook registration, attendance & reviews",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": False,
    },
    {
        "id": "pets",
        "title": "Resident Pets",
        "icon": "🐾",
        "desc": "Resident pet records / Committee pet licensing approvals",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "notices",
        "title": "Notice Board",
        "icon": "📋",
        "desc": "Resident notice board viewing / Committee notice publishing",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "classifieds",
        "title": "Resident Classifieds",
        "icon": "📢",
        "desc": "Resident ad marketplace / Committee classified ad approvals",
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
        "applies_to_committee": False,
    },
    {
        "id": "work_permits",
        "title": "Work Permits",
        "icon": "👷",
        "desc": "Resident contractor permits / Committee permit approval queue",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    },
    {
        "id": "emergency",
        "title": "Emergency SOS & Contacts",
        "icon": "🚨",
        "desc": "Resident SOS quick-dial / Committee SOS directory manager",
        "default_resident": 1,
        "default_committee": 1,
        "applies_to_resident": True,
        "applies_to_committee": True,
    }
]


def get_tile_settings():
    """
    Returns separate dictionaries for residents and committee members:
    {
        "residents": { "tenants": True/False, ... },
        "committee": { "tenants": True/False, ... }
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

    for tile in ALL_PORTAL_TILES:
        tid = tile["id"]

        # Support both new granular format {"residents": {...}, "committee": {...}}
        # and fallback for legacy flat format {"tenants": 1, ...}
        if "residents" in settings and isinstance(settings["residents"], dict):
            res_val = settings["residents"].get(tid, tile.get("default_resident", 1))
        else:
            res_val = settings.get(tid, tile.get("default_resident", 1))

        if "committee" in settings and isinstance(settings["committee"], dict):
            comm_val = settings["committee"].get(tid, tile.get("default_committee", 1))
        else:
            comm_val = settings.get(tid, tile.get("default_committee", 1))

        residents_dict[tid] = bool(int(res_val))
        committee_dict[tid] = bool(int(comm_val))

    return {
        "residents": residents_dict,
        "committee": committee_dict
    }


def is_system_manager(user=None):
    user = user or frappe.session.user
    if not user or user == "Guest":
        return False
    roles = frappe.get_roles(user)
    return "System Manager" in roles or user == "Administrator"


def get_context(context):
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
        })
    context.portal_tiles = tiles_list
    return context


@frappe.whitelist()
def save_tile_toggle(tile_id, target_role, enabled):
    """
    Whitelisted API for System Managers to toggle a feature for 'residents' or 'committee'.
    target_role must be 'residents' or 'committee'.
    """
    if not is_system_manager():
        frappe.throw(_("Permission Denied: Only users with the System Manager role can configure portal tile switches."), frappe.PermissionError)

    if target_role not in ("residents", "committee"):
        frappe.throw(_("Invalid target role. Must be 'residents' or 'committee'."))

    val = frappe.db.get_single_value("Society ERP Settings", "enabled_portal_tiles")
    settings = {}
    if val:
        try:
            settings = json.loads(val) if isinstance(val, str) else val
        except Exception:
            settings = {}

    if "residents" not in settings or not isinstance(settings["residents"], dict):
        # Migrate old format if present
        old_data = dict(settings)
        settings = {
            "residents": dict(old_data),
            "committee": dict(old_data)
        }
    if "committee" not in settings or not isinstance(settings["committee"], dict):
        settings["committee"] = {}

    val_int = 1 if (str(enabled).lower() in ("1", "true")) else 0
    settings[target_role][tile_id] = val_int

    frappe.db.set_single_value("Society ERP Settings", "enabled_portal_tiles", json.dumps(settings))

    # Keep enable_emergency_sos in sync for residents
    if tile_id == "emergency" and target_role == "residents":
        frappe.db.set_single_value("Society ERP Settings", "enable_emergency_sos", val_int)

    frappe.db.commit()

    role_label = "Residents" if target_role == "residents" else "Committee Members"
    status_label = "ENABLED" if val_int else "DISABLED"

    return {
        "status": "success",
        "tile_id": tile_id,
        "target_role": target_role,
        "enabled": bool(val_int),
        "message": _("'{0}' is now {1} for {2}.").format(tile_id, status_label, role_label)
    }
