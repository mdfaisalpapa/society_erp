from collections import defaultdict
import frappe


def get_context(context):
    # Public landing page: intentionally does not require login.
    context.no_cache = 1
    context.title = "Kendriya Vihar Chennai Phase III Apartment Owners’ Association"
    context.show_sidebar = False
    return context


def mask_name(name):
    """
    Mask individual name for privacy preserving initials and outline.
    e.g. 'USHA T' -> 'U**A T*'
         'MAHENDRAKAR VASUNDHARA' -> 'MA********R VA*******A'
         'G ARCHANA' -> 'G* AR****A'
    """
    if not name or not isinstance(name, str):
        return ""
    parts = name.strip().split()
    if not parts:
        return ""
    masked_parts = []
    for p in parts:
        if len(p) <= 2:
            masked_parts.append(p[0] + "*")
        elif len(p) <= 4:
            masked_parts.append(p[0] + "*" * (len(p) - 2) + p[-1])
        else:
            masked_parts.append(p[:2] + "*" * (len(p) - 3) + p[-1])
    return " ".join(masked_parts)


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
    Excludes owners who have already logged into the portal (email already confirmed).
    Masks owner names, emails, and mobile numbers for privacy.
    Returns categorized lists:
      1. fully_updated: Both mobile and email registered (unconfirmed/not yet logged in)
      2. missing_email: Mobile registered, but email is missing
      3. missing_mobile: Email registered, but mobile is missing
      4. missing_both: Both email and mobile are missing
      5. duplicate_contact: Active owners sharing the same mobile or email across multiple flats
    """
    # 1. Fetch set of users who have already logged in (last_login or last_active is set)
    logged_in_users = frappe.db.sql(
        """
        SELECT name, email
        FROM `tabUser`
        WHERE (last_login IS NOT NULL AND last_login != '')
           OR last_active IS NOT NULL
        """,
        as_dict=True,
    )
    logged_in_identifiers = set()
    for u in logged_in_users:
        if u.name:
            logged_in_identifiers.add(u.name.strip().lower())
        if u.email:
            logged_in_identifiers.add(u.email.strip().lower())

    # 2. Active Owners from Owners DocType
    all_owners = frappe.get_all(
        "Owners",
        filters={"active": 1},
        fields=["name", "flat", "owner_name", "email", "mobile_no", "linked_user"],
        order_by="flat asc, name asc",
    )

    # Filter out owners who have already logged in (their contact is already verified)
    owners = []
    already_logged_in_count = 0
    for o in all_owners:
        user_key = (o.get("linked_user") or "").strip().lower()
        email_key = (o.get("email") or "").strip().lower()

        if (user_key and user_key in logged_in_identifiers) or (
            email_key and email_key in logged_in_identifiers
        ):
            already_logged_in_count += 1
            continue
        owners.append(o)

    fully_updated = []
    missing_email = []
    missing_mobile = []
    missing_both = []

    # Maps for finding contacts shared across multiple distinct flats
    email_flat_map = defaultdict(list)
    mobile_flat_map = defaultdict(list)

    for o in owners:
        email = (o.get("email") or "").strip()
        raw_mobile = (o.get("mobile_no") or "").strip()
        flat_no = o.get("flat") or o.get("name")
        owner_name = (o.get("owner_name") or "").strip()

        has_email = bool(email)
        has_mobile = bool(raw_mobile)

        record = {
            "name": o.get("name"),
            "flat_no": flat_no,
            "owner_name": mask_name(owner_name) if owner_name else "",
            "masked_email": mask_email(email) if has_email else "",
            "masked_mobile": mask_mobile(raw_mobile) if has_mobile else "",
        }

        if has_email and has_mobile:
            fully_updated.append(record)
        elif has_mobile and not has_email:
            missing_email.append(record)
        elif has_email and not has_mobile:
            missing_mobile.append(record)
        else:
            missing_both.append(record)

        # Index normalized email
        if has_email:
            norm_email = email.lower()
            email_flat_map[norm_email].append(o)

        # Index normalized mobile (last 10 digits)
        if has_mobile:
            digits = "".join(c for c in raw_mobile if c.isdigit())
            norm_mobile = digits[-10:] if len(digits) >= 10 else digits
            if norm_mobile:
                mobile_flat_map[norm_mobile].append(o)

    # Detect duplicate/shared contacts across distinct flats
    duplicate_contact_map = defaultdict(
        lambda: {"reasons": [], "shared_flats": set(), "owner": None}
    )

    for norm_email, list_o in email_flat_map.items():
        flats = set(x["flat"] for x in list_o)
        if len(flats) > 1:
            for x in list_o:
                key = x["name"]
                duplicate_contact_map[key]["owner"] = x
                if "Same Email" not in duplicate_contact_map[key]["reasons"]:
                    duplicate_contact_map[key]["reasons"].append("Same Email")
                for other in list_o:
                    if other["flat"] != x["flat"]:
                        duplicate_contact_map[key]["shared_flats"].add(other["flat"])

    for norm_mobile, list_o in mobile_flat_map.items():
        flats = set(x["flat"] for x in list_o)
        if len(flats) > 1:
            for x in list_o:
                key = x["name"]
                duplicate_contact_map[key]["owner"] = x
                if "Same Mobile" not in duplicate_contact_map[key]["reasons"]:
                    duplicate_contact_map[key]["reasons"].append("Same Mobile")
                for other in list_o:
                    if other["flat"] != x["flat"]:
                        duplicate_contact_map[key]["shared_flats"].add(other["flat"])

    duplicate_contact = []
    for key, val in duplicate_contact_map.items():
        o = val["owner"]
        email = (o.get("email") or "").strip()
        raw_mobile = (o.get("mobile_no") or "").strip()
        flat_no = o.get("flat") or o.get("name")
        owner_name = (o.get("owner_name") or "").strip()

        duplicate_contact.append(
            {
                "name": o.get("name"),
                "flat_no": flat_no,
                "owner_name": mask_name(owner_name) if owner_name else "",
                "masked_email": mask_email(email) if email else "",
                "masked_mobile": mask_mobile(raw_mobile) if raw_mobile else "",
                "shared_flats": sorted(list(val["shared_flats"])),
                "duplicate_type": ", ".join(val["reasons"]),
            }
        )

    duplicate_contact.sort(key=lambda x: (x["flat_no"], x["owner_name"]))

    return {
        "fully_updated": fully_updated,
        "missing_email": missing_email,
        "missing_mobile": missing_mobile,
        "missing_both": missing_both,
        "duplicate_contact": duplicate_contact,
        "counts": {
            "fully_updated": len(fully_updated),
            "missing_email": len(missing_email),
            "missing_mobile": len(missing_mobile),
            "missing_both": len(missing_both),
            "duplicate_contact": len(duplicate_contact),
            "already_logged_in": already_logged_in_count,
            "total_pending": len(owners),
            "total": len(all_owners),
        },
    }
