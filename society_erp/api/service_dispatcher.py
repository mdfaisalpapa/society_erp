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
        "target_route": "/resident/committee?standalone=1",
        "btn_label": "🌐 Open Full Committee Canvas (WebApp)"
    },
    # --- Consolidated 8-Hub Mappings ---
    "profile_ownership": {
        "title": "Flat & Ownership Details",
        "icon": "👤",
        "target_route": "/resident/profile?standalone=1",
        "btn_label": "👤 View Flat Profile (WebApp)",
        "sub_actions": [
            {"id": "owners", "label": "📜 Ownership History & Deeds (WebApp)", "route": "/resident/owners?standalone=1"},
            {"id": "profile", "label": "✏️ Update Mobile & Contacts (WebApp)", "route": "/resident/profile?standalone=1&modal=update_mobile"}
        ]
    },
    "accounts_dues": {
        "title": "Accounts & Society Dues",
        "icon": "💳",
        "target_route": "/resident/dues?standalone=1",
        "btn_label": "💳 Pay Dues & View Ledger (WebApp)",
        "sub_actions": [
            {"id": "financials", "label": "📈 Society Financials & P&L (WebApp)", "route": "/resident/financials?standalone=1"}
        ]
    },
    "residents_tenants": {
        "title": "Residents & Tenants",
        "icon": "🏠",
        "target_route": "/resident/family?standalone=1",
        "btn_label": "👨‍👩‍👧‍👦 Family Members (WebApp)",
        "sub_actions": [
            {"id": "tenants", "label": "🏠 Tenant Management & Leases (WebApp)", "route": "/resident/tenants?standalone=1"}
        ]
    },
    "vehicles_parking": {
        "title": "Vehicles & Parking Allocation",
        "icon": "🚗",
        "target_route": "/resident/vehicles?standalone=1",
        "btn_label": "🚗 Manage Vehicles & Parking (WebApp)"
    },
    "visitors_staff": {
        "title": "Visitors & Domestic Staff",
        "icon": "🎫",
        "target_route": "/resident/visitors?standalone=1",
        "btn_label": "📋 Visitor Passes & Logs (WebApp)",
        "has_instant_pass": True,
        "sub_actions": [
            {"id": "staff", "label": "🧹 Domestic Staff & Helper Attendance (WebApp)", "route": "/resident/staff?standalone=1"}
        ]
    },
    "helpdesk_services": {
        "title": "Helpdesk & Resident Services",
        "icon": "🛠️",
        "target_route": "/resident/maintenance?standalone=1",
        "btn_label": "🛠️ Maintenance Tickets (WebApp)",
        "sub_actions": [
            {"id": "facilities", "label": "🏛️ Book Community Hall (WebApp)", "route": "/resident/book_facility?standalone=1"},
            {"id": "permits", "label": "👷 Work Permits & Contractor Passes (WebApp)", "route": "/resident/work_permits?standalone=1"}
        ]
    },
    "community_notices": {
        "title": "Community, Notices & Voting",
        "icon": "📢",
        "target_route": "/resident/notices?standalone=1",
        "btn_label": "📋 Official Notice Board (WebApp)",
        "sub_actions": [
            {"id": "classifieds", "label": "📢 Resident Marketplace Classifieds (WebApp)", "route": "/resident/classifieds?standalone=1"},
            {"id": "voting", "label": "🗳️ Polls & Governance Voting (WebApp)", "route": "/consensus-vote?standalone=1"},
            {"id": "pets", "label": "🐾 Pets Registry & Vaccinations (WebApp)", "route": "/resident/pets?standalone=1"}
        ]
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

    # Handle incoming verification messages (e.g. "VERIFY TC2-411 9445698019" or "VERIFY 814610")
    if act_lower.startswith("verify"):
        parts = act.split()
        mobile_to_verify = None
        otp_to_verify = None

        for p in reversed(parts):
            digits = "".join(filter(str.isdigit, p))
            if len(digits) >= 10:
                mobile_to_verify = digits[-10:]
                break
            elif len(digits) == 6:
                otp_to_verify = digits

        # Check if this is a web portal mobile update initiated verification: "VERIFY <otp>"
        target_email = for_user
        if otp_to_verify:
            # Check cached mobile_update_otp
            if for_user:
                cache_key = f"mobile_update_otp:{for_user}"
                cached = frappe.cache.get_value(cache_key)
                if cached and str(cached.get("otp", "")).strip() == otp_to_verify:
                    new_mobile = cached.get("new_mobile")
                    from society_erp.www.resident.profile.index import verify_and_update_mobile
                    # Direct update via profile module logic
                    from society_erp.account_management import mark_mobile_verified
                    mark_mobile_verified(new_mobile)
                    frappe.cache.delete_value(cache_key)
                    clean_m = "".join(filter(str.isdigit, str(new_mobile)))[-10:]
                    frappe.cache.delete_value(f"mobile_verify_link:{clean_m}")

                    # Update User and Owners/Tenants
                    frappe.db.set_value("User", for_user, "mobile_no", new_mobile)
                    frappe.db.sql(
                        "UPDATE `tabOwners` SET mobile_no = %s, is_mobile_verified = 1, mobile_verified_on = NOW() WHERE active = 1 AND email = %s",
                        (new_mobile, for_user)
                    )
                    frappe.db.sql(
                        "UPDATE `tabTenants` SET mobile_no = %s, is_mobile_verified = 1, mobile_verified_on = NOW() WHERE active = 1 AND email = %s",
                        (new_mobile, for_user)
                    )
                    frappe.db.commit()

                    from society_erp.api.menu import get_resident_menu
                    menu_data = get_resident_menu(for_user=for_user, channel="WhatsApp")
                    prompt = (
                        f"🎉 *Mobile Number Updated & Verified Successfully!*\n\n"
                        f"Your registered mobile number has been updated to *{new_mobile}*.\n\n"
                        + menu_data.get("welcome_message", "Select any society service below:")
                    )
                    return {
                        "title": "Mobile Updated",
                        "icon": "✅",
                        "summary_text": prompt,
                        "prompt": prompt,
                        "options": menu_data.get("options", []),
                    }

        if not mobile_to_verify and for_user:
            # Check owner or tenant mobile
            m = frappe.db.get_value("Owners", {"email": for_user, "active": 1}, "mobile_no") or \
                frappe.db.get_value("Tenants", {"email": for_user, "active": 1}, "mobile_no")
            if m:
                mobile_to_verify = "".join(filter(str.isdigit, str(m)))[-10:]

        if mobile_to_verify:
            from society_erp.account_management import mark_mobile_verified
            mark_mobile_verified(mobile_to_verify)

        from society_erp.api.menu import get_resident_menu
        menu_data = get_resident_menu(for_user=for_user, channel="WhatsApp")
        prompt = (
            "✅ *Mobile Number Verified Successfully!*\n\n"
            "Thank you! Your mobile number is now verified in Kendriya Vihar Phase-III records.\n\n"
            + menu_data.get("welcome_message", "Select any society service below:")
        )
        return {
            "title": "Mobile Verified",
            "icon": "✅",
            "summary_text": prompt,
            "prompt": prompt,
            "options": menu_data.get("options", []),
        }

    # Handle request to change registered email: "change_email:<new_email>"
    if act_lower.startswith("change_email:"):
        new_email = act.split(":", 1)[1].strip().lower()
        if "@" in new_email and "." in new_email:
            target_res = None
            if for_user:
                target_res = frappe.db.get_value("Owners", {"email": for_user, "active": 1}, ["name", "flat", "owner_name", "email"], as_dict=True) or \
                             frappe.db.get_value("Tenants", {"email": for_user, "active": 1}, ["name", "flat", "tenant_name", "email"], as_dict=True)

            if target_res:
                import random, string
                otp = "".join(random.choices(string.digits, k=6))
                # Store update email request in cache with doc name
                cache_payload = {
                    "otp": otp,
                    "new_email": new_email,
                    "target_doc": target_res.name,
                    "doctype": "Owners" if "owner_name" in target_res else "Tenants"
                }
                frappe.cache.set_value(f"email_change_req:{target_res.name}", cache_payload, expires_in_sec=600)
                frappe.cache.set_value(f"email_change_user:{for_user}", cache_payload, expires_in_sec=600)

                subject = f"🔐 Your Kendriya Vihar Email Update Code: {otp}"
                res_display_name = target_res.get("tenant_name") or target_res.get("owner_name")
                message = f"""
                <div style="font-family: Arial, sans-serif; max-width: 500px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
                    <h3 style="color: #1e3a8a; margin-top: 0;">Kendriya Vihar Phase-3</h3>
                    <p>Hello <strong>{res_display_name}</strong> (Flat: {target_res.flat}),</p>
                    <p>You requested to update your registered email address to <strong>{new_email}</strong>.</p>
                    <p>Please enter the following 6-digit confirmation code in WhatsApp to verify and complete the change:</p>
                    <div style="font-size: 28px; font-weight: bold; letter-spacing: 6px; text-align: center; padding: 15px; background: #f8fafc; border-radius: 6px; color: #1e293b; margin: 15px 0;">
                        {otp}
                    </div>
                    <p style="font-size: 13px; color: #64748b;">This OTP is valid for 10 minutes. If you did not request this, please contact the Estate Office.</p>
                </div>
                """
                try:
                    frappe.sendmail(recipients=[new_email], subject=subject, message=message, now=True)
                except Exception as e:
                    frappe.log_error("Email Change OTP Error", str(e))

                prompt = (
                    f"📩 *Verification Code Sent!*\n\n"
                    f"A 6-digit confirmation code has been sent to your new email `{new_email}`.\n\n"
                    f"👉 Please reply with the *6-digit OTP* (e.g. `123456`) to confirm and update your email address."
                )
                return {
                    "title": "Email OTP Sent",
                    "icon": "📩",
                    "summary_text": prompt,
                    "prompt": prompt,
                    "options": [{"label": "🏠 Main Menu", "value": "menu"}]
                }

    # Handle email input for verification or update (e.g. user typed "mdfaisalpapa@gmail.com")
    if "@" in act and "." in act and " " not in act:
        user_input_email = act.strip().lower()
        # Find active resident by email or by for_user
        res_owner = frappe.db.get_value("Owners", {"email": user_input_email, "active": 1}, ["name", "flat", "owner_name", "email"], as_dict=True)
        res_tenant = frappe.db.get_value("Tenants", {"email": user_input_email, "active": 1}, ["name", "flat", "tenant_name", "email"], as_dict=True)
        target_res = res_tenant or res_owner

        # Fallback check by for_user if input email matches record email
        if not target_res and for_user:
            target_res = frappe.db.get_value("Owners", {"email": for_user, "active": 1}, ["name", "flat", "owner_name", "email"], as_dict=True) or \
                         frappe.db.get_value("Tenants", {"email": for_user, "active": 1}, ["name", "flat", "tenant_name", "email"], as_dict=True)

        if target_res and target_res.get("email", "").strip().lower() == user_input_email:
            # Generate and send 6-digit OTP
            import random, string
            otp = "".join(random.choices(string.digits, k=6))
            frappe.cache.set_value(f"email_verify_otp:{target_res.name}", otp, expires_in_sec=600)

            subject = f"🔐 Your Kendriya Vihar Email Verification Code: {otp}"
            res_display_name = target_res.get("tenant_name") or target_res.get("owner_name")
            message = f"""
            <div style="font-family: Arial, sans-serif; max-width: 500px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
                <h3 style="color: #1e3a8a; margin-top: 0;">Kendriya Vihar Phase-3</h3>
                <p>Hello <strong>{res_display_name}</strong> (Flat: {target_res.flat}),</p>
                <p>Please use the following 6-digit verification code to confirm your email address:</p>
                <div style="font-size: 28px; font-weight: bold; letter-spacing: 6px; text-align: center; padding: 15px; background: #f8fafc; border-radius: 6px; color: #1e293b; margin: 15px 0;">
                    {otp}
                </div>
                <p style="font-size: 13px; color: #64748b;">This OTP is valid for 10 minutes. If you did not request this, please ignore this email.</p>
            </div>
            """
            try:
                frappe.sendmail(recipients=[user_input_email], subject=subject, message=message, now=True)
            except Exception as e:
                frappe.log_error("Email Verification OTP Error", str(e))

            prompt = (
                f"📩 *Verification Code Sent!*\n\n"
                f"A 6-digit verification code has been emailed to `{user_input_email}`.\n\n"
                f"👉 Please reply with the *6-digit OTP* (e.g. `123456`) to verify your email."
            )
            return {
                "title": "Email OTP Sent",
                "icon": "📩",
                "summary_text": prompt,
                "prompt": prompt,
                "options": [{"label": "🏠 Main Menu", "value": "menu"}]
            }
        else:
            # User's typed email does NOT match the registered record!
            # Since mobile number is already authenticated via WhatsApp, provide option to update email.
            prompt = (
                f"❌ *Email Does Not Match Records*\n\n"
                f"The email address `{user_input_email}` does not match the registered email for this flat.\n\n"
                f"Since your mobile number is already verified, would you like to update your registered email to `{user_input_email}`?\n\n"
                f"Tap *Change Email* below to send an OTP to `{user_input_email}`:"
            )
            return {
                "title": "Email Mismatch",
                "icon": "⚠️",
                "summary_text": prompt,
                "prompt": prompt,
                "options": [
                    {
                        "label": "✏️ Change Email",
                        "value": f"change_email:{user_input_email}"
                    },
                    {
                        "label": "🏠 Main Menu",
                        "value": "menu"
                    }
                ]
            }

    # Handle request to change registered email: "change_email:<new_email>"
    if act_lower.startswith("change_email:"):
        new_email = act.split(":", 1)[1].strip().lower()
        if "@" in new_email and "." in new_email:
            target_res = None
            if for_user:
                target_res = frappe.db.get_value("Owners", {"email": for_user, "active": 1}, ["name", "flat", "owner_name", "email"], as_dict=True) or \
                             frappe.db.get_value("Tenants", {"email": for_user, "active": 1}, ["name", "flat", "tenant_name", "email"], as_dict=True)

            if target_res:
                import random, string
                otp = "".join(random.choices(string.digits, k=6))
                # Store update email request in cache with doc name
                cache_payload = {
                    "otp": otp,
                    "new_email": new_email,
                    "target_doc": target_res.name,
                    "doctype": "Owners" if "owner_name" in target_res else "Tenants"
                }
                frappe.cache.set_value(f"email_change_req:{target_res.name}", cache_payload, expires_in_sec=600)
                frappe.cache.set_value(f"email_change_user:{for_user}", cache_payload, expires_in_sec=600)

                subject = f"🔐 Your Kendriya Vihar Email Update Code: {otp}"
                res_display_name = target_res.get("tenant_name") or target_res.get("owner_name")
                message = f"""
                <div style="font-family: Arial, sans-serif; max-width: 500px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
                    <h3 style="color: #1e3a8a; margin-top: 0;">Kendriya Vihar Phase-3</h3>
                    <p>Hello <strong>{res_display_name}</strong> (Flat: {target_res.flat}),</p>
                    <p>You requested to update your registered email address to <strong>{new_email}</strong>.</p>
                    <p>Please enter the following 6-digit confirmation code in WhatsApp to verify and complete the change:</p>
                    <div style="font-size: 28px; font-weight: bold; letter-spacing: 6px; text-align: center; padding: 15px; background: #f8fafc; border-radius: 6px; color: #1e293b; margin: 15px 0;">
                        {otp}
                    </div>
                    <p style="font-size: 13px; color: #64748b;">This OTP is valid for 10 minutes. If you did not request this, please contact the Estate Office.</p>
                </div>
                """
                try:
                    frappe.sendmail(recipients=[new_email], subject=subject, message=message, now=True)
                except Exception as e:
                    frappe.log_error("Email Change OTP Error", str(e))

                prompt = (
                    f"📩 *Verification Code Sent!*\n\n"
                    f"A 6-digit confirmation code has been sent to your new email `{new_email}`.\n\n"
                    f"👉 Please reply with the *6-digit OTP* (e.g. `123456`) to confirm and update your email address."
                )
                return {
                    "title": "Email OTP Sent",
                    "icon": "📩",
                    "summary_text": prompt,
                    "prompt": prompt,
                    "options": [{"label": "🏠 Main Menu", "value": "menu"}]
                }

    # Handle 6-digit OTP reply (e.g. user typed "849201")
    if act.isdigit() and len(act) == 6:
        otp_entered = act.strip()
        matched = False
        target_doc = None
        doctype = None
        updated_new_email = None

        if for_user:
            # 1. Check if this is an email change OTP
            change_req = frappe.cache.get_value(f"email_change_user:{for_user}")
            if not change_req:
                owner_d = frappe.db.get_value("Owners", {"email": for_user, "active": 1}, ["name"], as_dict=True)
                tenant_d = frappe.db.get_value("Tenants", {"email": for_user, "active": 1}, ["name"], as_dict=True)
                doc_name = (tenant_d or owner_d or {}).get("name")
                if doc_name:
                    change_req = frappe.cache.get_value(f"email_change_req:{doc_name}")

            if change_req and str(change_req.get("otp", "")).strip() == otp_entered:
                new_email = change_req.get("new_email")
                target_doc = change_req.get("target_doc")
                doctype = change_req.get("doctype", "Owners")
                now = frappe.utils.now_datetime()

                # Update email in Owners / Tenants
                frappe.db.set_value(doctype, target_doc, {
                    "email": new_email,
                    "is_email_verified": 1,
                    "email_verified_on": now
                }, update_modified=False)

                # Ensure resident user exists and is linked
                from society_erp.account_management import ensure_resident_user
                res_first_name = frappe.db.get_value(doctype, target_doc, "owner_name" if doctype == "Owners" else "tenant_name") or "Resident"
                role = "Resident" if doctype == "Owners" else "Tenant"
                ensure_resident_user(new_email, res_first_name, role)

                # Update linked Channel Identity records
                frappe.db.sql(
                    "UPDATE `tabChannel Identity` SET resident_email = %s WHERE resident_email = %s",
                    (new_email, for_user)
                )
                frappe.db.commit()

                # Cleanup cache
                frappe.cache.delete_value(f"email_change_req:{target_doc}")
                frappe.cache.delete_value(f"email_change_user:{for_user}")

                matched = True
                updated_new_email = new_email

            if not matched:
                # 2. Check standard verification OTP
                owner_doc = frappe.db.get_value("Owners", {"email": for_user, "active": 1}, ["name"], as_dict=True)
                tenant_doc = frappe.db.get_value("Tenants", {"email": for_user, "active": 1}, ["name"], as_dict=True)
                if tenant_doc:
                    target_doc = tenant_doc.name
                    doctype = "Tenants"
                elif owner_doc:
                    target_doc = owner_doc.name
                    doctype = "Owners"

                if target_doc:
                    cache_key = f"email_verify_otp:{target_doc}"
                    stored_otp = frappe.cache.get_value(cache_key)
                    if stored_otp and str(stored_otp).strip() == otp_entered:
                        frappe.cache.delete_value(cache_key)
                        now = frappe.utils.now_datetime()
                        frappe.db.set_value(doctype, target_doc, {
                            "is_email_verified": 1,
                            "email_verified_on": now
                        }, update_modified=False)
                        frappe.db.commit()
                        matched = True

        if matched:
            active_email = updated_new_email or for_user
            from society_erp.api.menu import get_resident_menu
            menu_data = get_resident_menu(for_user=active_email, channel="WhatsApp")
            menu_options = menu_data.get("options", [])

            # Format formatted menu options list for WhatsApp
            action_options = []
            for opt in menu_options:
                val = opt.get("id") or opt.get("value") or opt.get("action")
                lbl = opt.get("label") or opt.get("title")
                action_options.append({"label": lbl, "value": val})

            success_heading = (
                f"🎉 *Email Updated & Verified Successfully!*\n\n"
                f"Your registered email has been updated to `{active_email}` and verified.\n"
                f"Full access to society services is now unlocked:\n\n"
                if updated_new_email else
                f"🎉 *Email Verified Successfully!*\n\n"
                f"Your email address and mobile number are both verified.\n"
                f"Full access to society services is now unlocked:\n\n"
            )
            prompt = success_heading + menu_data.get("welcome_message", "Select any society service below:")
            return {
                "title": "Email Verified",
                "icon": "✅",
                "summary_text": prompt,
                "prompt": prompt,
                "options": action_options
            }
        else:
            prompt = (
                "❌ *Invalid or Expired Code*\n\n"
                "The 6-digit OTP entered is invalid or has expired.\n"
                "Please type your email address again to receive a fresh verification code."
            )
            return {
                "title": "Invalid OTP",
                "icon": "⚠️",
                "summary_text": prompt,
                "prompt": prompt,
                "options": [{"label": "🏠 Main Menu", "value": "menu"}]
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

    # Handling for open_<act>_portal (e.g. open_dues_portal, open_profile_portal, open_verify_portal)
    if act_lower.startswith("open_") and act_lower.endswith("_portal"):
        base_act = act_lower[5:-7]
        target_route = "/resident?standalone=1" if base_act == "verify" else (SERVICE_REGISTRY.get(base_act, {}).get("target_route") or f"/resident/{base_act}?standalone=1")
        title = "Resident Portal" if base_act == "verify" else (SERVICE_REGISTRY.get(base_act, {}).get("title") or "Portal")
        icon = "🔐" if base_act == "verify" else (SERVICE_REGISTRY.get(base_act, {}).get("icon") or "🔗")

        from society_erp.api.sso import generate_portal_link
        sso_res = generate_portal_link(for_user=for_user, target_route=target_route)
        sso_url = sso_res.get("url") or (sso_res.get("data", {}).get("url") if isinstance(sso_res, dict) else "")
        prompt = (
            f"{icon} *{title}*\n\n"
            f"🔗 Tap the secure link below to open in your browser:\n\n"
            f"{sso_url}\n\n"
            f"_(Link is valid for 15 minutes. Tap below to proceed)_"
        )
        return {
            "title": title,
            "icon": icon,
            "summary_text": prompt,
            "prompt": prompt,
            "sso_url": sso_url,
            "options": [
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

    # Consolidated Hub synthesizers
    if act == "profile_ownership":
        from society_erp.api.profile_summary import get_flat_profile, get_ownership_history
        p_res = get_flat_profile(for_user=for_user)
        p_data = p_res.get("data", p_res) if isinstance(p_res, dict) else {}
        o_res = get_ownership_history(for_user=for_user)
        o_data = o_res.get("data", o_res) if isinstance(o_res, dict) else {}
        curr_o = o_data.get("current_owner") or {}
        o_name = curr_o.get("name") or p_data.get("resident_name") or "Owner"
        s_date = curr_o.get("formatted_start_date") or "-"
        summary_text = (
            f"• Flat: `{p_data.get('flat')}` ({p_data.get('block')})\n"
            f"• Registered Owner: *{o_name}* (Since: {s_date})\n"
            f"• UDS: {p_data.get('uds')} sqft | Corpus: *{p_data.get('formatted_corpus')}*\n"
            f"• EB Service: `{p_data.get('eb_service_no') or '-'}` | Property Tax: `{p_data.get('property_tax_no') or '-'}`"
        )
    elif act == "accounts_dues":
        from society_erp.api.dues import get_flat_dues
        d_res = get_flat_dues(for_user=for_user)
        d_data = d_res.get("data", d_res) if isinstance(d_res, dict) else {}
        summary_text = (
            f"• Outstanding Maintenance: *{d_data.get('formatted_outstanding_balance', '₹ 0.00')}*\n"
            f"• Unpaid Invoices on Record: {d_data.get('invoice_count', 0)}\n\n"
            f"• Fiscal Year: 2026-2027\n"
            f"• Society Statements: Profit & Loss, Balance Sheet, Sinking & Corpus Funds"
        )
    elif act == "residents_tenants":
        from society_erp.api.resident_family import get_family_members
        from society_erp.tenant_portal import get_tenants
        f_res = get_family_members(for_user=for_user)
        f_data = f_res.get("data", f_res) if isinstance(f_res, dict) else {}
        t_res = get_tenants(for_user=for_user)
        t_data = t_res.get("data", t_res) if isinstance(t_res, dict) else {}
        f_count = len(f_data.get("members", []))
        t_active = len(t_data.get("active_tenants", []))
        t_total = t_data.get("count", 0)
        summary_text = (
            f"• Registered Family Members: *{f_count}*\n"
            f"• Active Tenants: *{t_active}* (Total on Record: {t_total})\n\n"
            f"Manage lease agreements, tenant registrations, and ID proofs below:"
        )
    elif act == "visitors_staff":
        from society_erp.api.visitor import get_recent_visitors
        from society_erp.api.domestic_staff import get_my_staff
        v_res = get_recent_visitors(for_user=for_user)
        v_data = v_res.get("data", v_res) if isinstance(v_res, dict) else {}
        s_res = get_my_staff(for_user=for_user)
        s_data = s_res.get("data", s_res) if isinstance(s_res, dict) else {}
        v_count = v_data.get("count", 0)
        s_count = len(s_data.get("staff", []))
        summary_text = (
            f"• Active Visitors / Passes: *{v_count}*\n"
            f"• Linked Domestic Helpers: *{s_count}*\n\n"
            f"Generate instant guest entry passes or inspect staff gate check-in:"
        )
    elif act == "helpdesk_services":
        from society_erp.api.maintenance_portal import get_resident_tickets_summary
        t_res = get_resident_tickets_summary(for_user=for_user)
        t_data = t_res.get("data", t_res) if isinstance(t_res, dict) else {}
        summary_text = (
            f"• Open Helpdesk Complaints: *{t_data.get('open_tickets', 0)}*\n"
            f"• Resolved Tickets: *{t_data.get('resolved_tickets', 0)}*\n\n"
            f"Raise new maintenance requests, reserve community hall, or file work permits:"
        )
    elif act == "community_notices":
        from society_erp.api.notices import get_active_notices
        from society_erp.api.classifieds import get_classifieds
        try:
            n_res = get_active_notices()
        except Exception:
            n_res = {}
        n_data = n_res.get("data", n_res) if isinstance(n_res, dict) else {}
        try:
            c_res = get_classifieds(for_user=for_user)
        except Exception:
            c_res = {}
        c_data = c_res.get("data", c_res) if isinstance(c_res, dict) else {}
        n_count = len(n_data.get("notices", []))
        c_count = len(c_data.get("ads", []))
        summary_text = (
            f"• Active Society Circulars: *{n_count}*\n"
            f"• Community Classifieds: *{c_count}*\n\n"
            f"View official announcements, voting polls, classifieds, and pet registry:"
        )
    elif meta.get("summary"):
        summary_text = meta["summary"]
    elif meta.get("method"):
        try:
            fn = frappe.get_attr(meta["method"])
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

    # If additional sub-actions exist in hub metadata, generate SSO for each
    if meta.get("sub_actions") and for_user:
        for sa in meta["sub_actions"]:
            try:
                from society_erp.api.sso import generate_portal_link
                sa_sso = generate_portal_link(for_user=for_user, target_route=sa["route"])
                sa_url = sa_sso.get("url") or (sa_sso.get("data", {}).get("url") if isinstance(sa_sso, dict) else "")
                sa_val = sa.get("id") or f"open_{sa.get('label')[:10].strip()}_sub"
                options.append({
                    "label": sa["label"],
                    "value": sa_val,
                    "web_app_url": sa_url
                })
            except Exception:
                pass

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
