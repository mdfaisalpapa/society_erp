import frappe
from society_erp.api.utils import portal_api
from society_erp.www.resident.settings.index import get_tile_settings


@frappe.whitelist()
@portal_api
def get_resident_menu(for_user: str = None) -> dict:
    """
    Returns the dynamically filtered and ordered menu for the resident/committee member,
    strictly adhering to the Master Switch Settings (Society ERP Settings) and role-based
    access control rules matching the Resident Portal UI (`resident/index.html`).
    """
    if for_user is None and frappe.session and frappe.session.user and frappe.session.user != "Guest":
        for_user = frappe.session.user

    user_email = (for_user or "").strip().lower()

    if not user_email or user_email in ("guest", "none", "null", "undefined"):
        return {
            "is_owner": False,
            "is_committee": False,
            "committee_role": "",
            "welcome_message": "🏢 *Welcome to Kendriya Vihar Phase-3!*\n\n👋 Please tap *📱 Share Contact to Login* below to securely verify your mobile number and access your flat details:",
            "options": [
                {
                    "id": "verify_contact",
                    "label": "📱 Share Contact to Login",
                    "desc": "1-Click Verify Mobile Number",
                    "action": "share_contact",
                    "request_contact": True,
                },
                {
                    "id": "emergency",
                    "label": "🚨 Emergency SOS",
                    "desc": "Gate Security, Doctor & Police",
                    "action": "emergency",
                },
            ],
            "count": 2,
        }

    # 1. Resolve Resident Role (Tenant vs Owner) & Committee Membership
    tenant = frappe.db.get_value(
        "Tenants",
        {"email": user_email, "active": 1},
        ["name", "flat", "tenant_name"],
        as_dict=True
    )
    owner = None
    if not tenant:
        owner = frappe.db.get_value(
            "Owners",
            {"email": user_email, "active": 1},
            ["name", "flat", "owner_name", "is_aoa_member"],
            as_dict=True
        )

    is_owner = bool(owner)
    is_committee = False
    committee_role = ""

    if owner and owner.get("is_aoa_member"):
        is_committee = True
    cm = frappe.db.get_value(
        "Committee Member",
        {"member_name": user_email, "status": "Active"},
        ["name", "designation"],
        as_dict=True
    )
    if cm:
        is_committee = True
        committee_role = cm.designation or "Committee Member"

    # 2. Master Portal Switchboard Settings
    tile_cfg = get_tile_settings()
    user_tiles = tile_cfg.get("committee" if is_committee else "residents", {})

    enable_sos = frappe.db.get_single_value("Society ERP Settings", "enable_emergency_sos")
    enable_emergency_sos = bool(int(enable_sos)) if enable_sos is not None else True

    # 3. Build Menu Options adhering strictly to resident/index.html sequence, labels & icons
    options = []

    # 0. AoA Committee Portal (RESTRICTED TO COMMITTEE MEMBERS)
    if is_committee:
        options.append({
            "id": "committee",
            "label": "🏛️ Committee",
            "desc": "Approvals & Notices",
            "action": "committee"
        })

    # 1. Flat & Profile Details (Common)
    if user_tiles.get("profile", True):
        options.append({
            "id": "profile",
            "label": "👤 Flat Details",
            "desc": "Profile & Property Info",
            "action": "profile"
        })

    # 2. Owner Details (RESTRICTED TO OWNERS)
    if is_owner and user_tiles.get("owners", True):
        options.append({
            "id": "owners",
            "label": "📜 Owner Details",
            "desc": "Current & Past Owners",
            "action": "owners"
        })

    # 3. Society Dues (Common)
    if user_tiles.get("dues", True):
        options.append({
            "id": "dues",
            "label": "📊 Check Dues",
            "desc": "Maintenance & Ledger",
            "action": "dues"
        })

    # 3b. Society Financials (Common)
    if user_tiles.get("financials", True):
        options.append({
            "id": "financials",
            "label": "📈 Financials",
            "desc": "P&L & Balance Sheet",
            "action": "financials"
        })

    # 4. Tenant Management (RESTRICTED TO OWNERS)
    if is_owner and user_tiles.get("tenants", True):
        options.append({
            "id": "tenants",
            "label": "🏠 Tenant Mgmt",
            "desc": "Register Leases & Tenants",
            "action": "tenants"
        })

    # 5. Book Facility (Common)
    if user_tiles.get("book_facility", True):
        options.append({
            "id": "book_facility",
            "label": "🏛️ Book Facility",
            "desc": "Clubhouse & Halls",
            "action": "facilities"
        })

    # 6. Visitor Management (Common)
    if user_tiles.get("visitors", True):
        options.append({
            "id": "visitors",
            "label": "🎫 Gate Pass",
            "desc": "Visitor Entry & OTP Pass",
            "action": "visitors"
        })

    # 7. Maintenance Tickets (Common)
    if user_tiles.get("maintenance", True):
        options.append({
            "id": "maintenance",
            "label": "🛠️ Maintenance",
            "desc": "Helpdesk & Issues",
            "action": "tickets"
        })

    # 8. Vehicles & Parking (Common)
    if user_tiles.get("vehicles", True):
        options.append({
            "id": "vehicles",
            "label": "🚗 Vehicles & Parking",
            "desc": "Parking Slots & Stickers",
            "action": "vehicles"
        })

    # 9. Family Members (Common)
    if user_tiles.get("family", True):
        options.append({
            "id": "family",
            "label": "👨‍👩‍👧‍👦 Family",
            "desc": "Members & ID Proofs",
            "action": "family"
        })

    # 10. Domestic Staff (Common)
    if user_tiles.get("staff", True):
        options.append({
            "id": "staff",
            "label": "🧹 Domestic Staff",
            "desc": "Maids & Cooks Gate Attendance",
            "action": "staff"
        })

    # 10b. Resident Pets (Common)
    if user_tiles.get("pets", True):
        options.append({
            "id": "pets",
            "label": "🐾 Pets",
            "desc": "Registrations & Vaccinations",
            "action": "pets"
        })

    # 11. Notice Board (Common)
    if user_tiles.get("notices", True):
        options.append({
            "id": "notices",
            "label": "📋 Notice Board",
            "desc": "Official Circulars & Resolutions",
            "action": "notices"
        })

    # 11b. Resident Classifieds & Marketplace (Common)
    if user_tiles.get("classifieds", True):
        options.append({
            "id": "classifieds",
            "label": "📢 Classifieds",
            "desc": "Rent, Sell & Services",
            "action": "classifieds"
        })

    # 13. Polls & Voting (Common)
    if user_tiles.get("voting", True):
        options.append({
            "id": "voting",
            "label": "🗳️ Polls & Voting",
            "desc": "Elections, Resolutions & Electorate",
            "action": "voting"
        })

    # 12. Work Permit Management (RESTRICTED TO OWNERS)
    if is_owner and user_tiles.get("work_permits", True):
        options.append({
            "id": "work_permits",
            "label": "👷 Work Permits",
            "desc": "Contractors & Approvals",
            "action": "permits"
        })

    # 15. Emergency SOS & Contacts (Common)
    if enable_emergency_sos and user_tiles.get("emergency", True):
        options.append({
            "id": "emergency",
            "label": "🚨 Emergency SOS",
            "desc": "Gate Security, Doctor & Police",
            "action": "emergency"
        })

    res_name = (owner.get("owner_name") if owner else (tenant.get("tenant_name") if tenant else "")).strip()
    flat_num = (owner.get("flat") if owner else (tenant.get("flat") if tenant else "")).strip()
    welcome_msg = f"🏢 *Welcome to Kendriya Vihar Phase-3!*\n\nHello *{res_name}* (Flat: `{flat_num}`)\nSelect any society service below:"

    return {
        "is_owner": is_owner,
        "is_committee": is_committee,
        "committee_role": committee_role,
        "welcome_message": welcome_msg,
        "options": options,
        "count": len(options)
    }
