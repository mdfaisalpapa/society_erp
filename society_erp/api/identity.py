import frappe
from frappe import _
from society_erp.resident_portal import get_verified_owner_records
from society_erp.api.utils import portal_api


@frappe.whitelist(allow_guest=True)
@portal_api
def resolve_chat_user(channel: str, channel_user_id: str, phone_number: str = None) -> dict:
    """
    Called by universal_chatbot to identify and authenticate incoming messages.
    If phone_number is provided (e.g. via 1-click Contact Sharing), automatically links
    and verifies the resident if found in Owners or Tenants.

    :param channel: 'Telegram' or 'WhatsApp'
    :param channel_user_id: Telegram chat_id or WhatsApp phone number
    :param phone_number: Verified phone number shared by user
    :return: Clean JSON payload with resident profile context or unauthenticated status
    """
    if not channel or not channel_user_id:
        return {
            "authenticated": False,
            "reason": "Missing channel or channel_user_id",
        }

    # Normalize channel name matching DocType Select ('Telegram' or 'WhatsApp')
    channel_lower = (channel or "").strip().lower()
    channel_norm = "WhatsApp" if channel_lower in ("whatsapp", "wa") else ("Telegram" if channel_lower in ("telegram", "tg") else channel.strip().capitalize())
    user_id_norm = str(channel_user_id).strip()

    # Clean phone if provided or from WhatsApp user ID
    clean_phone = None
    if phone_number:
        clean_phone = "".join(c for c in str(phone_number) if c.isdigit())
    elif channel_norm == "WhatsApp":
        clean_phone = "".join(c for c in str(channel_user_id) if c.isdigit())

    if clean_phone and len(clean_phone) > 10:
        clean_phone = clean_phone[-10:]

    # Auto-verify mobile for incoming WhatsApp/Telegram activity
    if clean_phone:
        from society_erp.account_management import mark_mobile_verified
        mark_mobile_verified(clean_phone)

    # 1. Auto-registration / linking if phone is known (WhatsApp channel_user_id or shared phone_number)
    if clean_phone:
        # Match in Owners or Tenants
        matched_owner = frappe.db.sql(
            """
            SELECT email, owner_name as resident_name, mobile_no
            FROM `tabOwners`
            WHERE active = 1 AND RIGHT(REGEXP_REPLACE(mobile_no, '[^0-9]', ''), 10) = %s
            ORDER BY creation DESC LIMIT 1
            """,
            (clean_phone,),
            as_dict=True,
        )
        if not matched_owner:
            matched_owner = frappe.db.sql(
                """
                SELECT email, tenant_name as resident_name, mobile_no
                FROM `tabTenants`
                WHERE active = 1 AND RIGHT(REGEXP_REPLACE(mobile_no, '[^0-9]', ''), 10) = %s
                ORDER BY creation DESC LIMIT 1
                """,
                (clean_phone,),
                as_dict=True,
            )

        if matched_owner and matched_owner[0].get("email"):
            res_email = matched_owner[0]["email"]
            # Upsert Channel Identity
            ci_name = frappe.db.get_value(
                "Channel Identity",
                {"channel": channel_norm, "channel_user_id": user_id_norm},
                "name",
            )
            if ci_name:
                ci_doc = frappe.get_doc("Channel Identity", ci_name)
                ci_doc.resident_email = res_email
                ci_doc.verified = 1
                ci_doc.save(ignore_permissions=True)
            else:
                frappe.get_doc({
                    "doctype": "Channel Identity",
                    "channel": channel_norm,
                    "channel_user_id": user_id_norm,
                    "resident_email": res_email,
                    "verified": 1,
                }).insert(ignore_permissions=True)
            frappe.db.commit()

    # Query Channel Identity
    identity = frappe.db.get_value(
        "Channel Identity",
        {
            "channel": channel_norm,
            "channel_user_id": user_id_norm,
            "verified": 1,
        },
        ["name", "resident_email"],
        as_dict=True,
    )

    if not identity or not identity.resident_email:
        return {
            "authenticated": False,
            "channel": channel_norm,
            "channel_user_id": user_id_norm,
            "reason": "Unlinked or unverified channel account",
        }

    # Fetch verified resident flats using the refactored core logic
    try:
        records = get_verified_owner_records(user_override=identity.resident_email)
    except frappe.PermissionError:
        return {
            "authenticated": False,
            "channel": channel_norm,
            "channel_user_id": user_id_norm,
            "resident_email": identity.resident_email,
            "reason": "No active flat records found for this verified email",
        }

    flats = sorted({r.flat for r in records if r.flat})
    primary = records[0]

    # Check AoA Committee Membership
    committee = frappe.db.get_value(
        "Committee Member",
        {"member_name": identity.resident_email, "status": "Active"},
        ["name", "designation"],
        as_dict=True,
    )

    # Check Guard / Staff Authorized Device
    device = frappe.db.get_value(
        "Authorized Bot Device",
        {"messenger_id": user_id_norm, "is_active": 1},
        ["name", "device_name"],
        as_dict=True,
    )

    return {
        "authenticated": True,
        "channel": channel_norm,
        "channel_user_id": user_id_norm,
        "resident_email": identity.resident_email,
        "resident_name": primary.resident_name,
        "resident_type": primary.resident_type,
        "is_committee": bool(committee),
        "committee_role": committee.designation if committee else None,
        "is_guard": bool(device),
        "guard_device": device.device_name if device else None,
        "flats": flats,
        "primary_flat": flats[0] if flats else None,
        "profiles": [
            {
                "flat": r.flat,
                "resident_type": r.resident_type,
                "name": r.name,
                "registration_status": r.registration_status,
                "mobile_no": r.mobile_no,
            }
            for r in records
        ],
    }


@frappe.whitelist(allow_guest=True)
@portal_api
def logout_chat_user(channel: str, channel_user_id: str) -> dict:
    """
    Unlinks and logs out a chat account from Society ERP.
    Deleting the Channel Identity ensures that future queries will require
    the resident to Share Contact again to log back in.
    """
    if not channel or not channel_user_id:
        return {"success": False, "message": "Missing channel or channel_user_id"}

    channel_norm = channel.strip().capitalize()
    user_id_norm = str(channel_user_id).strip()

    frappe.db.delete(
        "Channel Identity",
        {
            "channel": channel_norm,
            "channel_user_id": user_id_norm,
        },
    )
    frappe.db.commit()

    return {
        "success": True,
        "logged_out": True,
        "message": f"Successfully logged out and unlinked {channel_norm} account.",
    }


@frappe.whitelist()
@portal_api
def whois_flat(flat_number: str) -> dict:
    """Lookup public directory information for a flat."""
    flat = (flat_number or "").strip().upper()
    if not flat:
        return {"found": False, "message": "Flat number required"}

    owner = frappe.db.get_value("Owners", {"flat": flat, "active": 1}, ["owner_name", "flat"], as_dict=True)
    if owner:
        return {
            "found": True,
            "flat": owner.flat,
            "occupant_name": owner.owner_name,
            "type": "Owner Occupied"
        }

    return {"found": False, "message": f"No active registered resident found for {flat}"}


@frappe.whitelist(allow_guest=True)
@portal_api
def whois_chat_user(
    channel: str = "Telegram",
    target_user_id: str = None,
    target_first_name: str = None,
    is_bot: bool = False,
    query: str = None,
) -> dict:
    """
    Looks up a user's verified identity in Society ERP.
    Supports:
    1. Direct reply in Telegram (target_user_id from message.reply_to_message)
    2. Bot self-identification check (is_bot = True)
    3. Query by flat number or phone number (e.g. /whois TC2-411)
    """
    if is_bot:
        return {
            "found": True,
            "is_bot": True,
            "reply_message": "🤖 *That's me!*\n\nI am the automated Society Bot, managing community services, verifying records, and keeping the database clean 24/7."
        }

    user_id_str = str(target_user_id or "").strip()
    first_name_str = (target_first_name or "This user").strip()
    query_str = (query or "").strip()

    # 1. Check if user queried a flat number directly (e.g. /whois TC2-411)
    flat_match = None
    if query_str:
        # Check flat pattern (e.g. TA1-101, TC2-411, etc.)
        fl = query_str.upper()
        if frappe.db.exists("Customer", fl) or frappe.db.exists("Owners", {"flat": fl, "active": 1}):
            flat_match = fl

    if flat_match:
        # Lookup flat details
        owner = frappe.db.get_value("Owners", {"flat": flat_match, "active": 1}, ["owner_name", "flat", "is_aoa_member"], as_dict=True)
        tenant = frappe.db.get_value("Tenants", {"flat": flat_match, "active": 1}, ["tenant_name", "flat"], as_dict=True)
        if tenant:
            name = tenant.tenant_name
            role = "Tenant"
        elif owner:
            name = owner.owner_name
            role = "Owner"
        else:
            name = "Resident"
            role = "Occupant"

        reply = (
            f"🔍 *Verified Member*\n\n"
            f"👤 *Name:* {name}\n"
            f"🏠 *Flat:* {flat_match}\n"
            f"🏷️ *Role:* {role}"
        )
        return {
            "found": True,
            "name": name,
            "flat": flat_match,
            "role": role,
            "reply_message": reply
        }

    # 2. Check Authorized Bot Device (Staff / Security Guard / Office Admin)
    if user_id_str:
        device = frappe.db.sql(
            """
            SELECT name, device_name, device_role, assigned_staff_name
            FROM `tabAuthorized Bot Device`
            WHERE is_active = 1 AND (messenger_id = %s OR telegram_chat_id = %s OR telegram_user_id = %s)
            ORDER BY creation DESC LIMIT 1
            """,
            (user_id_str, user_id_str, user_id_str),
            as_dict=True,
        )
        if device:
            dev = device[0]
            staff_name = dev.get("assigned_staff_name") or dev.get("device_name") or "Staff"
            role = dev.get("device_role") or "Authorized Staff"
            reply = (
                f"🛡️ *Authorized Device / Staff*\n\n"
                f"👤 *Staff:* {staff_name}\n"
                f"🏢 *Office:* ESTATE OFFICE\n"
                f"🏷️ *Role:* {role}"
            )
            return {
                "found": True,
                "name": staff_name,
                "flat": "ESTATE OFFICE",
                "role": role,
                "reply_message": reply
            }

        # 3. Check Channel Identity
        channel_norm = "WhatsApp" if channel.lower() in ("whatsapp", "wa") else "Telegram"
        ci = frappe.db.get_value(
            "Channel Identity",
            {"channel": channel_norm, "channel_user_id": user_id_str, "verified": 1},
            ["resident_email"],
            as_dict=True,
        )
        if ci and ci.resident_email:
            from society_erp.resident_portal import get_verified_owner_records
            try:
                records = get_verified_owner_records(user_override=ci.resident_email)
                if records:
                    primary = records[0]
                    role = primary.resident_type or "Resident"
                    reply = (
                        f"🔍 *Verified Member*\n\n"
                        f"👤 *Name:* {primary.resident_name}\n"
                        f"🏠 *Flat:* {primary.flat}\n"
                        f"🏷️ *Role:* {role}"
                    )
                    return {
                        "found": True,
                        "name": primary.resident_name,
                        "flat": primary.flat,
                        "role": role,
                        "reply_message": reply
                    }
            except Exception:
                pass

        # 4. Check Owners by telegram_chat_id or telegram_user_id
        owner = frappe.db.sql(
            """
            SELECT owner_name, flat
            FROM `tabOwners`
            WHERE active = 1 AND (telegram_chat_id = %s OR telegram_user_id = %s)
            ORDER BY creation DESC LIMIT 1
            """,
            (user_id_str, user_id_str),
            as_dict=True,
        )
        if owner:
            reply = (
                f"🔍 *Verified Member*\n\n"
                f"👤 *Name:* {owner[0].owner_name}\n"
                f"🏠 *Flat:* {owner[0].flat}\n"
                f"🏷️ *Role:* Owner"
            )
            return {
                "found": True,
                "name": owner[0].owner_name,
                "flat": owner[0].flat,
                "role": "Owner",
                "reply_message": reply
            }

        # 5. Check Tenants by telegram_chat_id or telegram_user_id
        tenant = frappe.db.sql(
            """
            SELECT tenant_name, flat
            FROM `tabTenants`
            WHERE active = 1 AND (telegram_chat_id = %s OR telegram_user_id = %s)
            ORDER BY creation DESC LIMIT 1
            """,
            (user_id_str, user_id_str),
            as_dict=True,
        )
        if tenant:
            reply = (
                f"🔍 *Verified Member*\n\n"
                f"👤 *Name:* {tenant[0].tenant_name}\n"
                f"🏠 *Flat:* {tenant[0].flat}\n"
                f"🏷️ *Role:* Tenant"
            )
            return {
                "found": True,
                "name": tenant[0].tenant_name,
                "flat": tenant[0].flat,
                "role": "Tenant",
                "reply_message": reply
            }

        # 6. Check Family Members by telegram_chat_id or telegram_user_id
        fam = frappe.db.sql(
            """
            SELECT member_name, parent_flat
            FROM `tabFamily Members`
            WHERE status = 'Active' AND (telegram_chat_id = %s OR telegram_user_id = %s)
            ORDER BY creation DESC LIMIT 1
            """,
            (user_id_str, user_id_str),
            as_dict=True,
        )
        if fam:
            reply = (
                f"🔍 *Verified Member*\n\n"
                f"👤 *Name:* {fam[0].member_name}\n"
                f"🏠 *Flat:* {fam[0].parent_flat}\n"
                f"🏷️ *Role:* Family"
            )
            return {
                "found": True,
                "name": fam[0].member_name,
                "flat": fam[0].parent_flat,
                "role": "Family",
                "reply_message": reply
            }

    # Not found in any registered record
    return {
        "found": False,
        "reply_message": f"❌ *Unverified User*\n\nCould not find a registered profile for {first_name_str} in the system."
    }

