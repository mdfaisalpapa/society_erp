import frappe


def get_context(context):
    # Public landing page: intentionally does not require login.
    context.no_cache = 1
    context.title = "Kendriya Vihar Chennai Phase III Apartment Owners’ Association"
    context.show_sidebar = False
    return context


def mask_email(email):
    """
    Mask email address for privacy preserving first characters and domain.
    e.g. 'faisal@gmail.com' -> 'fais***@gmail.com'
    """
    if not email or not isinstance(email, str) or "@" not in email:
        return ""
    email = email.strip()
    name_part, domain = email.split("@", 1)
    if len(name_part) <= 4:
        masked_name = name_part[0] + "***"
    else:
        masked_name = name_part[:4] + "***"
    return f"{masked_name}@{domain}"


def mask_mobile(mobile):
    """
    Mask mobile phone number for privacy preserving first 2 and last 2 digits.
    e.g. '9876543210' -> '98******10'
         '919865325128' -> '9198******28'
    """
    if not mobile or not isinstance(mobile, str):
        return ""
    mobile = mobile.strip()
    digits = "".join(c for c in mobile if c.isdigit())
    if len(digits) >= 10:
        prefix = digits[:2] if len(digits) == 10 else digits[: len(digits) - 8]
        suffix = digits[-2:]
        return f"{prefix}******{suffix}"
    elif len(digits) > 4:
        return digits[:2] + "******" + digits[-2:]
    return "******"


@frappe.whitelist(allow_guest=True)
def get_owner_contact_status():
    """
    Publicly accessible endpoint (no login required) to check AoA contact details status.
    Returns three categorized lists of active owners with masked email/mobile:
      1. fully_updated: Both mobile and email registered
      2. missing_email: Mobile registered, but email is missing
      3. missing_mobile: Email registered, but mobile is missing
    """
    # Active Owners from Owners DocType
    owners = frappe.get_all(
        "Owners",
        filters={"active": 1},
        fields=["name", "flat", "owner_name", "email", "mobile_no"],
        order_by="flat asc, name asc",
    )

    fully_updated = []
    missing_email = []
    missing_mobile = []
    missing_both = []

    for o in owners:
        email = (o.get("email") or "").strip()
        mobile = (o.get("mobile_no") or "").strip()
        flat_no = o.get("flat") or o.get("name")
        owner_name = (o.get("owner_name") or "").strip()

        has_email = bool(email)
        has_mobile = bool(mobile)

        record = {
            "flat_no": flat_no,
            "owner_name": owner_name,
            "masked_email": mask_email(email) if has_email else "",
            "masked_mobile": mask_mobile(mobile) if has_mobile else "",
        }

        if has_email and has_mobile:
            fully_updated.append(record)
        elif has_mobile and not has_email:
            missing_email.append(record)
        elif has_email and not has_mobile:
            missing_mobile.append(record)
        else:
            missing_both.append(record)

    return {
        "fully_updated": fully_updated,
        "missing_email": missing_email,
        "missing_mobile": missing_mobile,
        "missing_both": missing_both,
        "counts": {
            "fully_updated": len(fully_updated),
            "missing_email": len(missing_email),
            "missing_mobile": len(missing_mobile),
            "missing_both": len(missing_both),
            "total": len(owners),
        },
    }
