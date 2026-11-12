import random
import re
import frappe
from frappe import _


def get_context(context):
    context.is_standalone = bool(frappe.form_dict.get("standalone"))
    if context.is_standalone:
        context.no_header = True
        context.no_sidebar = True

    # Require login
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    user = frappe.session.user
    user_email = user.strip().lower()

    # 1. Check whether the logged-in user is an active tenant.
    tenant = frappe.db.get_value(
        "Tenants",
        {"email": user_email, "active": 1},
        [
            "name",
            "flat",
            "tenant_name",
            "mobile_no",
            "email",
        ],
        as_dict=True,
    )

    owner = None

    # 2. If not a tenant, identify the active owner.
    if not tenant:
        owner = frappe.db.get_value(
            "Owners",
            {"linked_user": user, "active": 1},
            [
                "name",
                "flat",
                "owner_name",
                "mobile_no",
                "email",
            ],
            as_dict=True,
        )

        # Support owner accounts linked by email instead.
        if not owner:
            owner = frappe.db.get_value(
                "Owners",
                {"email": user_email, "active": 1},
                [
                    "name",
                    "flat",
                    "owner_name",
                    "mobile_no",
                    "email",
                ],
                as_dict=True,
            )

    resident = tenant or owner

    if not resident or not resident.flat:
        context.not_a_resident = True
        return context

    # 3. Set the resident's flat and identity.
    flat_id = resident.flat

    context.not_a_resident = False
    context.flat_number = flat_id
    context.resident_type = "Tenant" if tenant else "Owner"
    context.resident_name = (
        tenant.tenant_name if tenant else owner.owner_name
    )
    context.resident_email = user_email
    context.resident_mobile = (
        resident.mobile_no
        or frappe.db.get_value("User", user, "mobile_no")
        or ""
    )
    context.is_tenant = bool(tenant)
    context.is_owner = bool(owner)

    # 4. Fetch registered owner details for this flat.
    owner_details = frappe.db.get_value(
        "Owners",
        {"flat": flat_id, "active": 1},
        ["owner_name", "mobile_no", "email"],
        as_dict=True,
    )

    context.owner_details = owner_details or frappe._dict({
        "owner_name": "Not available",
        "mobile_no": None,
        "email": None,
    })

    # 5. Fetch permanent flat details.
    context.flat_details = {}

    if frappe.db.exists("Customer", flat_id):
        flat_doc = frappe.get_doc("Customer", flat_id)

        context.flat_details = {
            "block": flat_doc.get("custom_block"),
            "uds": flat_doc.get("custom_uds"),
            "eb_service_no": (
                flat_doc.get("eb_service_no")
                or flat_doc.get("custom_eb_service_no")
            ),
            "property_tax_no": (
                flat_doc.get("property_tax_no")
                or flat_doc.get("custom_property_tax_no")
            ),
            "corpus_fund": flat_doc.get(
                "corpus_fund_contribution"
            ),
        }

    # 6. Fetch live financial standing for the logged-in owner/flat:
    # A. Actual Corpus Fund Contribution from GL Entry (credits minus debits)
    #    booked against Customer party ID and Corpus Fund account
    from frappe.utils import flt, fmt_money

    company = (
        frappe.db.get_single_value("Global Defaults", "default_company")
        or frappe.db.get_value("Company", {}, "name")
    )
    currency = (
        frappe.db.get_value("Company", company, "default_currency")
        or frappe.db.get_default("currency")
        or "INR"
    )

    corpus_gl_entries = frappe.get_all(
        "GL Entry",
        filters={
            "party_type": "Customer",
            "party": flat_id,
            "account": ["like", "Corpus Fund%"],
            "is_cancelled": 0,
        },
        fields=["debit", "credit"],
    )
    corpus_contribution = sum(
        flt(e.credit) - flt(e.debit) for e in corpus_gl_entries
    )

    # B. Current Outstanding Dues from unpaid Sales Invoices linked to this flat/customer
    unpaid_invoices = frappe.get_all(
        "Sales Invoice",
        filters={
            "customer": flat_id,
            "docstatus": 1,
        },
        fields=["outstanding_amount"],
    )
    current_dues = sum(flt(inv.outstanding_amount) for inv in unpaid_invoices)

    context.currency = currency
    context.corpus_contribution = corpus_contribution
    context.formatted_corpus_contribution = fmt_money(corpus_contribution, currency=currency)
    context.current_dues = current_dues
    context.formatted_current_dues = fmt_money(current_dues, currency=currency)

    return context


def _validate_mobile_number(mobile):
    """
    Validates phone format.
    Accepts 10-digit Indian numbers with optional country prefix (+91 or 91).
    """
    if not mobile or not isinstance(mobile, str):
        frappe.throw(_("Please provide a valid mobile number."))
    cleaned = re.sub(r"[\s\-\(\)\+]", "", mobile.strip())
    if not cleaned.isdigit():
        frappe.throw(_("Mobile number must contain only numeric digits."))
    if len(cleaned) == 10:
        if cleaned[0] not in "6789":
            frappe.throw(_("Mobile number should start with 6, 7, 8, or 9."))
        return cleaned
    elif len(cleaned) == 12 and cleaned.startswith("91"):
        if cleaned[2] not in "6789":
            frappe.throw(_("Mobile number should start with 6, 7, 8, or 9."))
        return cleaned
    else:
        frappe.throw(_("Please enter a valid 10-digit mobile number."))


@frappe.whitelist()
def send_mobile_update_otp(new_mobile):
    """
    Validates new mobile, generates a 6-digit OTP, caches it for 5 minutes,
    and sends an authorization email to the logged-in user.
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in to update your mobile number."), frappe.PermissionError)

    user = frappe.session.user
    valid_mobile = _validate_mobile_number(new_mobile)

    # Generate 6-digit cryptographic-random-like numeric OTP
    otp = f"{random.randint(100000, 999999)}"

    # Cache OTP for 5 minutes (300 seconds)
    cache_key = f"mobile_update_otp:{user}"
    frappe.cache().set_value(
        cache_key,
        {"otp": str(otp), "new_mobile": valid_mobile},
        expires_in_sec=300,
    )

    # Format email message
    subject = _("Your Mobile Number Update OTP - KVC3 AoA Portal")
    message = f"""
    <div style="font-family: Arial, sans-serif; font-size: 14px; color: #333; line-height: 1.6;">
        <h2 style="color: #173d5b; margin-top: 0;">Mobile Number Update Request</h2>
        <p>Dear Resident,</p>
        <p>We received a request to update your registered mobile number on the Kendriya Vihar Chennai Phase III Resident Portal to <strong>{valid_mobile}</strong>.</p>
        <p>Your one-time authorization code (OTP) is:</p>
        <div style="margin: 20px 0; padding: 15px; background: #f1f5f9; border-radius: 8px; text-align: center;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #173d5b;">{otp}</span>
        </div>
        <p style="color: #64748b; font-size: 12px;">This OTP is valid for <strong>5 minutes</strong>. If you did not initiate this request, please contact the AoA Estate Office immediately.</p>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
        <p style="color: #94a3b8; font-size: 11px;">Kendriya Vihar Chennai Phase III Apartment Owners’ Association</p>
    </div>
    """

    try:
        frappe.sendmail(
            recipients=[user],
            subject=subject,
            message=message,
            now=True,
        )
    except Exception as e:
        frappe.log_error(f"Failed to send mobile update OTP to {user}: {str(e)}", "Mobile Update OTP")
        frappe.throw(_("Failed to deliver OTP email. Please ensure your email settings are active or try again."))

    return {
        "status": "success",
        "message": _("A 6-digit OTP has been sent to your registered email ({0}).").format(user),
        "target_email": user,
    }


@frappe.whitelist()
def verify_and_update_mobile(new_mobile, otp):
    """
    Verifies OTP from cache and updates mobile_no in User and Owner/Tenant doctypes.
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in to update your mobile number."), frappe.PermissionError)

    user = frappe.session.user
    user_email = user.strip().lower()

    if not otp or not str(otp).strip():
        frappe.throw(_("Please enter the 6-digit OTP sent to your email."))

    cache_key = f"mobile_update_otp:{user}"
    cached_data = frappe.cache().get_value(cache_key)

    if not cached_data:
        frappe.throw(_("The OTP has expired or was not requested. Please request a new OTP."))

    expected_otp = str(cached_data.get("otp", "")).strip()
    cached_mobile = cached_data.get("new_mobile")

    if str(otp).strip() != expected_otp:
        frappe.throw(_("Invalid OTP. Please check the code sent to your email and try again."))

    # Valid mobile to apply
    target_mobile = cached_mobile or _validate_mobile_number(new_mobile)

    # 1. Update User document
    if frappe.db.exists("User", user):
        frappe.db.set_value("User", user, "mobile_no", target_mobile)

    # 2. Update linked Owners documents
    # Find by linked_user or email
    owner_names = frappe.get_all(
        "Owners",
        filters={"active": 1},
        or_filters={"linked_user": user, "email": user_email},
        pluck="name",
    )
    for o_name in owner_names:
        frappe.db.set_value("Owners", o_name, "mobile_no", target_mobile)

    # 3. Update linked Tenants documents if tenant
    tenant_names = frappe.get_all(
        "Tenants",
        filters={"active": 1},
        or_filters={"linked_user": user, "email": user_email},
        pluck="name",
    )
    for t_name in tenant_names:
        frappe.db.set_value("Tenants", t_name, "mobile_no", target_mobile)

    # Cleanup OTP from cache
    frappe.cache().delete_value(cache_key)

    frappe.db.commit()

    return {
        "status": "success",
        "message": _("Mobile number updated successfully."),
        "mobile_no": target_mobile,
    }
