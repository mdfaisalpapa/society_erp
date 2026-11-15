import random
import string
import frappe
from frappe import _
from society_erp.api.utils import portal_api
from society_erp.account_management import normalize_email, mark_mobile_verified


def _get_resident(user_email):
    """Fetch active Tenant or Owner matching user_email or linked_user."""
    if not user_email:
        return None, None

    clean_email = user_email.strip().lower()

    # 1. Tenants
    tenants = frappe.get_all(
        "Tenants",
        filters={"active": 1},
        fields=["name", "flat", "tenant_name", "email", "mobile_no", "is_email_verified", "is_mobile_verified"],
    )
    for t in tenants:
        if (t.email and t.email.strip().lower() == clean_email) or t.name == clean_email:
            return t, "Tenant"

    # 2. Owners
    owners = frappe.get_all(
        "Owners",
        filters={"active": 1},
        fields=["name", "flat", "owner_name", "email", "mobile_no", "is_email_verified", "is_mobile_verified"],
    )
    for o in owners:
        if (o.email and o.email.strip().lower() == clean_email) or o.name == clean_email:
            return o, "Owner"

    return None, None


@frappe.whitelist()
@portal_api
def get_verification_status(for_user: str = None) -> dict:
    """
    Returns the email & mobile verification status for the current resident.
    Provides WhatsApp and Telegram deep links for 1-click mobile verification.
    """
    user = for_user or frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Authentication required"), frappe.PermissionError)

    resident, r_type = _get_resident(user)
    if not resident:
        return {
            "is_resident": False,
            "message": "No active resident record found."
        }

    # Fetch configured bot details
    settings = frappe.get_single("Society ERP Settings")
    wa_number = getattr(settings, "whatsapp_bot_number", "") or "17374243710"
    tg_username = getattr(settings, "telegram_bot_username", "") or "kvciii_bot"

    # Generate token for mobile link verification
    clean_mobile = "".join(filter(str.isdigit, str(resident.mobile_no or "")))
    if len(clean_mobile) > 10:
        clean_mobile = clean_mobile[-10:]

    wa_text = f"VERIFY {resident.flat} {clean_mobile}"
    import urllib.parse
    wa_link = f"https://wa.me/{wa_number}?text={urllib.parse.quote(wa_text)}"
    tg_link = f"https://t.me/{tg_username}?start=VERIFY_{clean_mobile}"

    return {
        "is_resident": True,
        "resident_type": r_type,
        "flat": resident.flat,
        "name": resident.get("tenant_name") or resident.get("owner_name"),
        "email": resident.email or "",
        "mobile_no": resident.mobile_no or "",
        "is_email_verified": bool(resident.is_email_verified),
        "is_mobile_verified": bool(resident.is_mobile_verified),
        "is_fully_verified": bool(resident.is_email_verified and resident.is_mobile_verified),
        "whatsapp_verification_link": wa_link,
        "telegram_verification_link": tg_link,
    }


@frappe.whitelist()
def send_email_verification_otp():
    """Generates and emails a 6-digit verification OTP to the logged-in resident."""
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Authentication required"), frappe.PermissionError)

    resident, r_type = _get_resident(user)
    if not resident or not resident.email:
        frappe.throw(_("No registered email address found for your flat."))

    # Generate 6-digit OTP
    otp = "".join(random.choices(string.digits, k=6))
    cache_key = f"email_verify_otp:{resident.name}"
    frappe.cache.set_value(cache_key, otp, expires_in_sec=600)  # 10 minutes

    subject = f"🔐 Your Kendriya Vihar Email Verification Code: {otp}"
    message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
        <h3 style="color: #1e3a8a; margin-top: 0;">Kendriya Vihar Phase-3</h3>
        <p>Hello <strong>{resident.get('tenant_name') or resident.get('owner_name')}</strong> (Flat: {resident.flat}),</p>
        <p>Please use the following 6-digit verification code to confirm your email address:</p>
        <div style="font-size: 28px; font-weight: bold; letter-spacing: 6px; text-align: center; padding: 15px; background: #f8fafc; border-radius: 6px; color: #1e293b; margin: 15px 0;">
            {otp}
        </div>
        <p style="font-size: 13px; color: #64748b;">This OTP is valid for 10 minutes. If you did not request this, please ignore this email.</p>
    </div>
    """
    try:
        frappe.sendmail(
            recipients=[resident.email],
            subject=subject,
            message=message,
            now=True
        )
    except Exception as e:
        frappe.log_error("Email Verification OTP Error", str(e))
        frappe.throw(_("Could not send verification email. Please try again later."))

    return {"message": _("Verification code sent to {0}").format(resident.email)}


@frappe.whitelist()
def verify_email_otp(otp: str):
    """Validates the 6-digit email OTP and marks is_email_verified = 1."""
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Authentication required"), frappe.PermissionError)

    resident, r_type = _get_resident(user)
    if not resident:
        frappe.throw(_("Resident record not found."))

    cache_key = f"email_verify_otp:{resident.name}"
    stored_otp = frappe.cache.get_value(cache_key)

    if not stored_otp or str(otp).strip() != str(stored_otp).strip():
        frappe.throw(_("Invalid or expired verification code. Please request a new one."))

    frappe.cache.delete_value(cache_key)

    now = frappe.utils.now_datetime()
    doctype = "Tenants" if r_type == "Tenant" else "Owners"
    frappe.db.set_value(doctype, resident.name, {
        "is_email_verified": 1,
        "email_verified_on": now
    }, update_modified=False)
    frappe.db.commit()

    return {"success": True, "message": _("Email verified successfully!")}
