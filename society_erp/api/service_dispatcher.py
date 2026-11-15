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
        "summary": "• Fiscal Year: 2026-2027\n• Statements: Profit & Loss, Balance Sheet, Income & Expenditure, Sinking & Corpus Funds\n\nTap below to view live financial statements from ERPNext:",
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
    Given an action_id (e.g. 'dues', 'visitors', 'tickets', or sub-action like 'open_comm_vehicles'),
    executes the corresponding module API, formats summary text, generates the SSO link,
    and returns structured options for the dynamic Chatbot UI card.
    """
    act = (action_id or "").strip()
    act_lower = act.lower()

    # If action_id is 'menu', route cleanly to get_resident_menu
    if act_lower in ("menu", "main_menu"):
        from society_erp.api.menu import get_resident_menu
        menu_data = get_resident_menu(for_user=for_user)
        return {
            "title": "Main Menu",
            "icon": "🏢",
            "summary_text": menu_data.get("welcome_message", "Main Menu"),
            "prompt": menu_data.get("welcome_message", "Main Menu"),
            "options": menu_data.get("options", []),
        }

    # Special handling for direct open actions (e.g. when selected in WhatsApp)
    if act_lower.startswith("open_comm_"):
        from society_erp.api.committee_menu import get_committee_sub_tiles
        res = get_committee_sub_tiles(for_user=for_user)
        raw_tiles = res.get("sub_tiles") or (res.get("data", {}).get("sub_tiles") if isinstance(res.get("data"), dict) else [])
        tile_map = {st["value"]: st for st in raw_tiles if isinstance(st, dict)}
        st = tile_map.get(act) or tile_map.get(act_lower)
        if st:
            title = st.get("title") or st.get("label", "Committee Item")
            icon = st.get("icon", "🏛️")
            web_url = st.get("web_app_url", "")
            badge = st.get("badge", 0)
            status_desc = f" ({badge} Pending)" if badge > 0 else ""
            prompt = (
                f"{icon} *{title}{status_desc}*\n\n"
                f"🔗 Tap the secure link below to open this section in your browser:\n\n"
                f"{web_url}\n\n"
                f"_(Link is valid for 15 minutes. Tap below to proceed)_"
            )
            return {
                "title": title,
                "icon": icon,
                "summary_text": prompt,
                "prompt": prompt,
                "sso_url": web_url,
                "options": [
                    {
                        "label": "🏛️ Back to Committee",
                        "value": "committee"
                    },
                    {
                        "label": "🏠 Main Menu",
                        "value": "menu"
                    }
                ]
            }

    # Handling for open_<act>_portal (e.g. open_dues_portal, open_profile_portal)
    if act_lower.startswith("open_") and act_lower.endswith("_portal"):
        base_act = act_lower[5:-7]
        meta = SERVICE_REGISTRY.get(base_act)
        if meta and meta.get("target_route"):
            from society_erp.api.sso import generate_portal_link
            sso_res = generate_portal_link(for_user=for_user, target_route=meta["target_route"])
            sso_url = sso_res.get("url") or (sso_res.get("data", {}).get("url") if isinstance(sso_res, dict) else "")
            prompt = (
                f"{meta['icon']} *{meta['title']}*\n\n"
                f"🔗 Tap the secure link below to open this portal in your browser:\n\n"
                f"{sso_url}\n\n"
                f"_(Link is valid for 15 minutes. Tap below to proceed)_"
            )
            return {
                "title": meta["title"],
                "icon": meta["icon"],
                "summary_text": prompt,
                "prompt": prompt,
                "sso_url": sso_url,
                "options": [
                    {
                        "label": f"🔙 Back to {meta['title'][:15]}",
                        "value": base_act
                    },
                    {
                        "label": "🏠 Main Menu",
                        "value": "menu"
                    }
                ]
            }

    meta = SERVICE_REGISTRY.get(act_lower)
    if not meta:
        fallback_msg = f"Service '{action_id}' is currently being updated."
        return {
            "title": "Service",
            "icon": "ℹ️",
            "summary_text": fallback_msg,
            "prompt": f"ℹ️ *Service Details*\n\n{fallback_msg}",
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
            # Always try passing for_user first; if TypeError fallback to no args
            try:
                res = fn(for_user=for_user)
            except TypeError:
                res = fn()

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
                    curr_owner = raw_data.get("current_owner") or {}
                    if isinstance(curr_owner, dict):
                        owner_name = curr_owner.get("name") or "Not registered"
                        start_d = curr_owner.get("formatted_start_date") or curr_owner.get("start_date") or "-"
                        mobile_str = curr_owner.get("mobile") or "-"
                        email_str = curr_owner.get("email") or "-"
                        owner_summary = (
                            f"*{owner_name}*\n"
                            f"• Since: *{start_d}*\n"
                            f"• Contact: 📞 `{mobile_str}` | ✉️ `{email_str}`"
                        )
                    else:
                        owner_summary = str(curr_owner)

                    prev_count = len(raw_data.get("previous_owners", [])) or raw_data.get("count", 0)
                    summary_text = (
                        f"• Flat: `{raw_data.get('flat')}`\n"
                        f"• Current Registered Owner: {owner_summary}\n"
                        f"• Total Historic Transfers: {prev_count}"
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
