import json
import frappe
from frappe import _

# Master list of all controllable tiles on the resident portal
ALL_PORTAL_TILES = [
    {
        "id": "committee",
        "title": "AoA Committee Portal",
        "icon": "🏛️",
        "desc": "Committee member dashboard, approvals, resolutions & notices",
        "default": 1,
        "restricted_to": "Committee Members / Admins"
    },
    {
        "id": "profile",
        "title": "Flat & Profile Details",
        "icon": "👤",
        "desc": "Flat info, UDS, EB service & property tax details",
        "default": 1,
        "restricted_to": "All Residents"
    },
    {
        "id": "owners",
        "title": "Owner Details",
        "icon": "📜",
        "desc": "Current & past flat owner records and ownership contacts",
        "default": 1,
        "restricted_to": "Owners Only"
    },
    {
        "id": "dues",
        "title": "Check Dues & Invoices",
        "icon": "📊",
        "desc": "Maintenance charges, invoices, receipts and dues ledger",
        "default": 1,
        "restricted_to": "All Residents"
    },
    {
        "id": "financials",
        "title": "Society Financials",
        "icon": "📈",
        "desc": "Audited Profit & Loss statement and Balance Sheet",
        "default": 1,
        "restricted_to": "All Residents"
    },
    {
        "id": "tenants",
        "title": "Tenant Management",
        "icon": "🏠",
        "desc": "Register leases, tenant records and agreement documents",
        "default": 1,
        "restricted_to": "Owners Only"
    },
    {
        "id": "book_facility",
        "title": "Book Facility & Amenities",
        "icon": "🏛️",
        "desc": "Community Hall & club facility shift booking",
        "default": 1,
        "restricted_to": "All Residents"
    },
    {
        "id": "visitors",
        "title": "Gate Pass & Visitors",
        "icon": "🎫",
        "desc": "Visitor entry logs, OTP passes & delivery pre-approval",
        "default": 1,
        "restricted_to": "All Residents"
    },
    {
        "id": "maintenance",
        "title": "Maintenance Tickets",
        "icon": "🛠️",
        "desc": "Raise, track and resolve common area and flat issues",
        "default": 1,
        "restricted_to": "All Residents"
    },
    {
        "id": "vehicles",
        "title": "Vehicles & Parking",
        "icon": "🚗",
        "desc": "Register vehicles, request parking stickers & slots",
        "default": 1,
        "restricted_to": "All Residents"
    },
    {
        "id": "family",
        "title": "Family Members",
        "icon": "👨‍👩‍👧‍👦",
        "desc": "Add and manage registered family members and ID proofs",
        "default": 1,
        "restricted_to": "All Residents"
    },
    {
        "id": "staff",
        "title": "Domestic Staff",
        "icon": "🧹",
        "desc": "Maid, driver & cook registration, attendance & reviews",
        "default": 1,
        "restricted_to": "All Residents"
    },
    {
        "id": "pets",
        "title": "Resident Pets",
        "icon": "🐾",
        "desc": "Pet registration, breed, color & vaccination records",
        "default": 1,
        "restricted_to": "All Residents"
    },
    {
        "id": "notices",
        "title": "Notice Board",
        "icon": "📋",
        "desc": "Official circulars, general announcements & resolutions",
        "default": 1,
        "restricted_to": "All Residents"
    },
    {
        "id": "classifieds",
        "title": "Resident Classifieds",
        "icon": "📢",
        "desc": "Community marketplace for rentals, used items & services",
        "default": 1,
        "restricted_to": "All Residents"
    },
    {
        "id": "voting",
        "title": "Polls & Voting",
        "icon": "🗳️",
        "desc": "Secret ballot voting, election electorate & candidate lists",
        "default": 1,
        "restricted_to": "All Residents"
    },
    {
        "id": "work_permits",
        "title": "Work Permits",
        "icon": "👷",
        "desc": "Interior renovation permits & contractor worker passes",
        "default": 1,
        "restricted_to": "Owners Only"
    },
    {
        "id": "emergency",
        "title": "Emergency SOS & Contacts",
        "icon": "🚨",
        "desc": "Main Gate security, manager, police & ambulance quick dial",
        "default": 1,
        "restricted_to": "All Residents"
    }
]


def get_tile_settings():
    """
    Returns a dictionary of tile_id -> bool indicating if the tile is enabled.
    Defaults to True (enabled) if not explicitly set to False.
    """
    val = frappe.db.get_single_value("Society ERP Settings", "enabled_portal_tiles")
    settings = {}
    if val:
        try:
            settings = json.loads(val) if isinstance(val, str) else val
        except Exception:
            settings = {}

    result = {}
    for tile in ALL_PORTAL_TILES:
        tid = tile["id"]
        if tid in settings:
            result[tid] = bool(settings[tid])
        else:
            result[tid] = bool(tile.get("default", 1))
    return result


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
        tiles_list.append({
            **tile,
            "enabled": tile_statuses.get(tile["id"], True)
        })
    context.portal_tiles = tiles_list
    return context


@frappe.whitelist()
def save_tile_toggle(tile_id, enabled):
    """
    Whitelisted API for System Managers only to toggle a resident/committee tile.
    """
    if not is_system_manager():
        frappe.throw(_("Permission Denied: Only users with the System Manager role can configure portal tile switches."), frappe.PermissionError)

    val = frappe.db.get_single_value("Society ERP Settings", "enabled_portal_tiles")
    settings = {}
    if val:
        try:
            settings = json.loads(val) if isinstance(val, str) else val
        except Exception:
            settings = {}

    settings[tile_id] = 1 if (str(enabled).lower() in ("1", "true")) else 0

    frappe.db.set_single_value("Society ERP Settings", "enabled_portal_tiles", json.dumps(settings))
    # If the emergency tile was toggled, keep enable_emergency_sos in sync as well
    if tile_id == "emergency":
        frappe.db.set_single_value("Society ERP Settings", "enable_emergency_sos", settings[tile_id])

    frappe.db.commit()

    return {
        "status": "success",
        "tile_id": tile_id,
        "enabled": bool(settings[tile_id]),
        "message": _("Portal tile '{0}' has been {1}.").format(tile_id, "ENABLED" if settings[tile_id] else "DISABLED")
    }
