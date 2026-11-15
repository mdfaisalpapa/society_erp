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
            ],
            "count": 1,
        }

    # 1. Resolve Resident Role (Tenant vs Owner) & Committee Membership
    tenant = frappe.db.get_value(
        "Tenants",
        {"email": user_email, "active": 1},
        ["name", "flat", "tenant_name", "mobile_no", "is_email_verified", "is_mobile_verified"],
        as_dict=True
    )
    owner = None
    if not tenant:
        owner = frappe.db.get_value(
            "Owners",
            {"email": user_email, "active": 1},
            ["name", "flat", "owner_name", "mobile_no", "is_aoa_member", "is_email_verified", "is_mobile_verified"],
            as_dict=True
        )

    resident = tenant or owner

    # Requirement 3: Enforce verification gate.
    # Main menu options are only displayed for email and mobile verified users.
    if resident and not (resident.get("is_email_verified") and resident.get("is_mobile_verified")):
        res_name = resident.get("tenant_name") or resident.get("owner_name")
        missing = []
        if not resident.get("is_email_verified"):
            missing.append("📧 Email Address")
        if not resident.get("is_mobile_verified"):
            missing.append("📱 Mobile Number")

        missing_str = " and ".join(missing)
        welcome_msg = (
            f"🏢 *Welcome to Kendriya Vihar Phase-3!*\n\n"
            f"Hello *{res_name}* (Flat: `{resident.get('flat')}`)\n\n"
            f"⚠️ *Account Verification Required*\n"
            f"To access society services and dues, please verify your {missing_str}.\n"
            f"Tap below to complete verification:"
        )

        from society_erp.api.sso import generate_portal_link
        sso_res = generate_portal_link(for_user=user_email, target_route="/resident?standalone=1")
        verify_url = sso_res.get("url") if isinstance(sso_res, dict) else ""

        return {
            "is_owner": bool(owner),
            "is_committee": False,
            "committee_role": "",
            "verification_pending": True,
            "welcome_message": welcome_msg,
            "options": [
                {
                    "id": "verify_contact",
                    "label": "🔐 Complete Verification",
                    "desc": f"Verify {missing_str}",
                    "action": "open_verify_portal",
                    "web_app_url": verify_url,
                },
                {
                    "id": "share_contact",
                    "label": "📱 Share Contact to Verify Mobile",
                    "desc": "1-Click Instant Mobile Verification",
                    "action": "share_contact",
                    "request_contact": True,
                }
            ],
            "count": 2,
        }

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

    # 3. Build Streamlined 8-Hub Menu Options (strictly <= 10 items for WhatsApp & Telegram UX)
    options = []

    # 0. AoA Committee Portal (RESTRICTED TO COMMITTEE MEMBERS)
    if is_committee:
        options.append({
            "id": "committee",
            "label": "🏛️ Committee",
            "desc": "Approvals, Governance & Agency Monitoring",
            "action": "committee"
        })

    # 1. Flat & Ownership (Combines Property Specifications + Owner History)
    if user_tiles.get("profile", True) or user_tiles.get("owners", True):
        options.append({
            "id": "profile_ownership",
            "label": "👤 Flat & Ownership",
            "desc": "Flat Info, UDS, EB & Owner Deeds",
            "action": "profile_ownership"
        })

    # 2. Accounts & Dues (Combines Maintenance Ledger + Live Society Financials)
    if user_tiles.get("dues", True) or user_tiles.get("financials", True):
        options.append({
            "id": "accounts_dues",
            "label": "💳 Accounts & Dues",
            "desc": "Maintenance Ledger & Financial Statements",
            "action": "accounts_dues"
        })

    # 3. Residents & Tenants (Combines Family Members + Tenant Management)
    if user_tiles.get("family", True) or (is_owner and user_tiles.get("tenants", True)):
        options.append({
            "id": "residents_tenants",
            "label": "🏠 Residents & Tenants",
            "desc": "Family Members & Tenant Leases",
            "action": "residents_tenants"
        })

    # 4. Vehicles & Parking
    if user_tiles.get("vehicles", True) or user_tiles.get("parking", True):
        options.append({
            "id": "vehicles_parking",
            "label": "🚗 Vehicles & Parking",
            "desc": "Vehicle Passes & Parking Slots",
            "action": "vehicles_parking"
        })

    # 5. Visitors & Domestic Staff (Gate passes & Staff attendance)
    if user_tiles.get("visitors", True) or user_tiles.get("staff", True):
        options.append({
            "id": "visitors_staff",
            "label": "🎫 Visitors & Staff",
            "desc": "Gate Entry Passes & Domestic Helpers",
            "action": "visitors_staff"
        })

    # 6. Helpdesk & Services (Maintenance Tickets, Facility Bookings & Work Permits)
    if user_tiles.get("maintenance", True) or user_tiles.get("book_facility", True) or user_tiles.get("work_permits", True):
        options.append({
            "id": "helpdesk_services",
            "label": "🛠️ Helpdesk & Services",
            "desc": "Maintenance, Hall Booking & Work Permits",
            "action": "helpdesk_services"
        })

    # 7. Community & Notices (Notice Board, Classifieds, Polls & Pets)
    if user_tiles.get("notices", True) or user_tiles.get("classifieds", True) or user_tiles.get("voting", True) or user_tiles.get("pets", True):
        options.append({
            "id": "community_notices",
            "label": "📢 Community & Notices",
            "desc": "Notice Board, Classifieds, Voting & Pets",
            "action": "community_notices"
        })

    # 8. Emergency SOS (if enabled)
    if enable_emergency_sos and user_tiles.get("emergency", True):
        options.append({
            "id": "emergency",
            "label": "🚨 Emergency SOS",
            "desc": "Security Gate, Doctor & Contacts",
            "action": "emergency"
        })

    # 9. Logout
    options.append({
        "id": "logout",
        "label": "🚪 Logout",
        "desc": "Unlink Account & Reset Session",
        "action": "logout"
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
