import frappe
from society_erp.api.utils import portal_api

# Registry mapping menu action IDs to their handler function and web app target route
SERVICE_REGISTRY = {
    "profile": {
        "title": "Flat Details & Property Profile",
        "icon": "👤",
        "method": "society_erp.api.profile_summary.get_flat_profile",
        "target_route": "/resident/profile?standalone=1&modal=update_mobile",
        "btn_label": "✏️ Update Mobile / Profile (WebApp)"
    },
    "owners": {
        "title": "Flat Ownership Records",
        "icon": "📜",
        "method": "society_erp.api.profile_summary.get_ownership_history",
        "target_route": "/resident/owners?standalone=1",
        "btn_label": "📜 View Deeds & Co-Owners (WebApp)"
    },
    "dues": {
        "title": "Check Dues - Maintenance Ledger",
        "icon": "📊",
        "method": "society_erp.api.dues.get_flat_dues",
        "target_route": "/resident/dues?standalone=1",
        "btn_label": "💳 Pay Now / Full Ledger (WebApp)"
    },
    "financials": {
        "title": "Society Financial Statements",
        "icon": "📈",
        "summary": "• Fiscal Year: 2026-2027\n• Audited Statements: P&L, Balance Sheet, Income & Expenditure, Sinking & Corpus Funds\n\nTap below to inspect verified audited statements:",
        "target_route": "/resident/financials?standalone=1",
        "btn_label": "📈 View Financials & P&L (WebApp)"
    },
    "tenants": {
        "title": "Tenant Management & Leases",
        "icon": "🏠",
        "method": "society_erp.api.tenant_summary.get_tenants",
        "target_route": "/resident/tenants?standalone=1",
        "btn_label": "➕ Add / Edit Tenants (WebApp)"
    },
    "facilities": {
        "title": "Book Facility & Amenities",
        "icon": "🏛️",
        "method": "society_erp.api.facility_booking.get_facility_bookings",
        "target_route": "/resident/book_facility?standalone=1",
        "btn_label": "📅 Reserve Hall / Shift (WebApp)"
    },
    "visitors": {
        "title": "Gate Pass & Visitors",
        "icon": "🎫",
        "method": "society_erp.api.visitor.get_recent_visitors",
        "target_route": "/resident/visitors?standalone=1",
        "btn_label": "📋 Manage Passes & Deliveries (WebApp)",
        "has_instant_pass": True
    },
    "tickets": {
        "title": "Maintenance Tickets & Helpdesk",
        "icon": "🛠️",
        "method": "society_erp.api.maintenance_portal.get_resident_tickets_summary",
        "target_route": "/resident/maintenance?standalone=1",
        "btn_label": "📸 Raise / Manage Complaints (WebApp)"
    },
    "vehicles": {
        "title": "Vehicles & Parking Allocation",
        "icon": "🚗",
        "method": "society_erp.api.vehicle_summary.get_vehicles",
        "target_route": "/resident/vehicles?standalone=1",
        "btn_label": "➕ Add / Edit Vehicle & RC (WebApp)"
    },
    "family": {
        "title": "Family Members",
        "icon": "👨‍👩‍👧‍👦",
        "method": "society_erp.api.resident_family.get_family_members",
        "target_route": "/resident/family?standalone=1",
        "btn_label": "👨‍👩‍👧‍👦 Add / Edit Family & ID (WebApp)"
    },
    "staff": {
        "title": "Domestic Staff & Helpers",
        "icon": "🧹",
        "method": "society_erp.api.domestic_staff.get_my_staff",
        "target_route": "/resident/staff?standalone=1",
        "btn_label": "🧹 Manage / Link Helpers (WebApp)"
    },
    "pets": {
        "title": "Resident Pets",
        "icon": "🐾",
        "method": "society_erp.api.pets.get_pets",
        "target_route": "/resident/pets?standalone=1",
        "btn_label": "🐾 Add / Edit Pet (WebApp)"
    },
    "notices": {
        "title": "Notice Board & Broadcasts",
        "icon": "📋",
        "method": "society_erp.api.notices.get_active_notices",
        "target_route": "",
        "btn_label": ""
    },
    "classifieds": {
        "title": "Resident Classifieds Marketplace",
        "icon": "📢",
        "method": "society_erp.api.classifieds.get_classifieds",
        "target_route": "/resident/classifieds?standalone=1",
        "btn_label": "📢 Post / Edit Classifieds (WebApp)"
    },
    "voting": {
        "title": "Polls & Voting",
        "icon": "🗳️",
        "method": "society_erp.api.voting_summary.get_voting_summary",
        "target_route": "/consensus-vote?standalone=1",
        "btn_label": "🗳️ Open Voting & Ballots (WebApp)"
    },
    "permits": {
        "title": "Work Permits & Contractor Passes",
        "icon": "👷",
        "method": "society_erp.api.work_permit.get_work_permits",
        "target_route": "/resident/work_permits?standalone=1",
        "btn_label": "👷 Apply / Manage Work Permit (WebApp)"
    },
    "emergency": {
        "title": "Emergency SOS & Contacts Directory",
        "icon": "🚨",
        "method": "society_erp.api.emergency.get_emergency_contacts",
        "target_route": "/resident/emergency?standalone=1",
        "btn_label": "🚨 One-Touch SOS Directory (WebApp)"
    },
    "committee": {
        "title": "AoA Managing Committee Portal",
        "icon": "🏛️",
        "method": "society_erp.api.committee_menu.get_committee_sub_tiles",
        "target_route": "",
        "btn_label": ""
    }
}


@frappe.whitelist()
@portal_api
def get_service_details(action_id: str, for_user: str = None) -> dict:
    """
    Unified Single-Node Dispatcher for Universal Chatbot.
    Given an action_id (e.g. 'dues', 'visitors', 'tickets'), executes the corresponding
    module API, formats summary text, generates the SSO link, and returns structured options
    for the dynamic Chatbot UI card.
    """
    act = (action_id or "").strip().lower()
    meta = SERVICE_REGISTRY.get(act)
    if not meta:
        return {
            "title": "Service",
            "summary_text": f"Service '{action_id}' is currently being updated.",
            "options": [{"label": "🔙 Back to Main Menu", "value": "menu"}]
        }

    # 1. Fetch data from underlying API
    summary_text = ""
    raw_data = {}
    if meta.get("summary"):
        summary_text = meta["summary"]
    elif meta.get("method"):
        try:
            fn = frappe.get_attr(meta["method"])
            res = fn(for_user=for_user) if "for_user" in fn.__code__.co_varnames else fn()
            raw_data = res.get("data", res) if isinstance(res, dict) else {}
            summary_text = raw_data.get("summary_text", "")
            if not summary_text:
                if act == "profile":
                    summary_text = (
                        f"• Flat: `{raw_data.get('flat')}` ({raw_data.get('block')})\n"
                        f"• Resident: {raw_data.get('resident_name')} ({raw_data.get('resident_type')})\n"
                        f"• Contact: 📞 `{raw_data.get('mobile_no')}` | ✉️ `{raw_data.get('email')}`\n"
                        f"• Corpus Contribution: *{raw_data.get('formatted_corpus')}*\n"
                        f"• Current Outstanding: *{raw_data.get('formatted_dues')}*"
                    )
                elif act == "owners":
                    summary_text = (
                        f"• Flat: `{raw_data.get('flat')}`\n"
                        f"• Current Registered Owner: *{raw_data.get('current_owner')}*\n"
                        f"• Total Historic Transfers: {raw_data.get('count', 0)}"
                    )
                elif act == "classifieds":
                    my_s = raw_data.get("my_summary", "None")
                    ad_s = raw_data.get("ads_summary", "No active listings.")
                    summary_text = f"*Your Listings:*\n{my_s}\n\n*Active Community Ads:*\n{ad_s}"
                else:
                    summary_text = str(raw_data)
        except Exception as e:
            summary_text = f"Could not load details: {str(e)}"

    # 2. Generate SSO link if target_route is defined
    sso_url = ""
    target_route = meta.get("target_route")
    if target_route and for_user:
        try:
            from society_erp.api.sso import generate_portal_link
            sso_res = generate_portal_link(for_user=for_user, target_route=target_route)
            sso_url = sso_res.get("url") or (sso_res.get("data", {}).get("url") if isinstance(sso_res, dict) else "")
        except Exception:
            sso_url = ""

    # 3. Build Card UI Prompt and Action Options
    prompt = f"{meta['icon']} *{meta['title']}*\n\n{summary_text}"
    options = []

    if meta.get("has_instant_pass"):
        options.append({
            "label": "⚡ Instant 1-Day Guest Pass",
            "value": "gen_pass"
        })

    if sso_url and meta.get("btn_label"):
        options.append({
            "label": meta["btn_label"],
            "value": f"open_{act}_portal",
            "web_app_url": sso_url
        })

    # If sub-tiles exist (e.g. committee sub-tiles)
    if raw_data.get("sub_tiles"):
        for st in raw_data["sub_tiles"]:
            options.append(st)

    options.append({
        "label": "🔙 Back to Main Menu",
        "value": "menu"
    })

    return {
        "title": meta["title"],
        "icon": meta["icon"],
        "summary_text": summary_text,
        "prompt": prompt,
        "sso_url": sso_url,
        "options": options
    }
