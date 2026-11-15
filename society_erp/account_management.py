# Copyright (c) 2026, Mohammed Faisal and contributors
# Shared User-account provisioning for Owners and Tenants.

import frappe
from frappe import _
from frappe.utils import validate_email_address


def normalize_email(value):
    """Return a validated, lowercase email address."""
    if not value:
        return None

    email = value.strip().lower()
    validated = validate_email_address(email, throw=False)
    if not validated:
        frappe.throw(_("Please enter a valid email address: {0}").format(email))

    return str(validated).strip().lower()


def _find_user_by_email(email):
    """Find exactly one User by email; reject ambiguous matches."""
    users = frappe.get_all(
        "User",
        filters={"email": email},
        pluck="name",
        limit_page_length=2,
    )

    if len(users) > 1:
        frappe.throw(
            _("More than one User account uses {0}. Please resolve this before linking.")
            .format(email)
        )

    return users[0] if users else None


def ensure_resident_user(email, first_name, role):
    """
    Create or reuse a User account and ensure the requested resident role.

    New resident accounts are Website Users. Existing accounts are not
    converted between Website User and System User.
    """
    email = normalize_email(email)
    if not email:
        return None

    user_name = _find_user_by_email(email)

    if not user_name:
        user = frappe.new_doc("User")
        user.email = email
        user.first_name = first_name or email.split("@", 1)[0]
        user.enabled = 1
        user.user_type = "Website User"
        user.send_welcome_email = 1
        user.append("roles", {"role": role})
        user.insert(ignore_permissions=True)
        return user.name

    user = frappe.get_doc("User", user_name)
    user.enabled = 1

    existing_roles = {row.role for row in user.roles}
    if role not in existing_roles:
        user.append("roles", {"role": role})

    user.save(ignore_permissions=True)
    return user.name


def ensure_linked_resident_account(doc, role, display_name):
    """
    Provision/link the account for an active Owner or Tenant document.

    The Owner/Tenant document is inserted first. This function then creates
    or finds the User and writes linked_user back to the already-existing row.
    """
    if not doc.email:
        return None

    email = normalize_email(doc.email)
    doc.email = email

    old_user_to_check = None

    # Handle linked user email updates
    if doc.linked_user:
        linked_email = frappe.db.get_value("User", doc.linked_user, "email")
        if not linked_email:
            # Linked user was deleted or invalid; allow re-linking
            doc.linked_user = None
        elif linked_email.strip().lower() != email:
            # Check if user has permission to update email (Desk manager or programmatic bypass)
            is_manager = False
            if frappe.flags.allow_email_relink or getattr(doc, "flags", {}).get("allow_email_relink"):
                is_manager = True
            elif frappe.session and frappe.session.user:
                current_roles = frappe.get_roles(frappe.session.user)
                if any(r in current_roles for r in ("System Manager", "Administrator", "Estate Manager", "Society Manager")):
                    is_manager = True

            if is_manager:
                old_user_to_check = doc.linked_user
                doc.linked_user = None
            else:
                frappe.throw(
                    _("The email does not match the linked User account. "
                      "Update the User email or have an Administrator correct the link first.")
                )

    user_name = ensure_resident_user(
        email=email,
        first_name=display_name or doc.flat,
        role=role,
    )

    if user_name and doc.linked_user != user_name:
        frappe.db.set_value(
            doc.doctype,
            doc.name,
            "linked_user",
            user_name,
            update_modified=False,
        )
        doc.linked_user = user_name

    # If the user account changed, check if old user account should be deactivated
    if old_user_to_check and old_user_to_check != user_name:
        dummy_doc = frappe._dict({"name": doc.name, "linked_user": old_user_to_check, "email": None})
        deactivate_user_if_unused(dummy_doc)

    return user_name


def deactivate_user_if_unused(doc):
    """
    Disable a resident Website User only when no other active Owner/Tenant
    record references the same User/email.

    System Users and accounts with roles beyond the resident roles are never
    disabled automatically.
    """
    user_name = doc.linked_user
    if not user_name and doc.email:
        email = normalize_email(doc.email)
        user_name = _find_user_by_email(email) if email else None

    if not user_name or not frappe.db.exists("User", user_name):
        return

    other_owner = frappe.db.exists(
        "Owners",
        {
            "linked_user": user_name,
            "active": 1,
            "name": ["!=", doc.name],
        },
    )
    other_tenant = frappe.db.exists(
        "Tenants",
        {
            "linked_user": user_name,
            "active": 1,
            "name": ["!=", doc.name],
        },
    )

    # Compatibility with older records that have not yet been linked.
    user_email = frappe.db.get_value("User", user_name, "email")
    if user_email:
        if not other_owner:
            other_owner = frappe.db.exists(
                "Owners",
                {
                    "email": user_email,
                    "active": 1,
                    "name": ["!=", doc.name],
                },
            )
        if not other_tenant:
            other_tenant = frappe.db.exists(
                "Tenants",
                {
                    "email": user_email,
                    "active": 1,
                    "name": ["!=", doc.name],
                },
            )

    if other_owner or other_tenant:
        return

    user = frappe.get_doc("User", user_name)
    if user.user_type != "Website User":
        return

    roles = {row.role for row in user.roles}
    resident_roles = {"Flat Owner", "Flat Tenant"}

    # Do not disable an account that also has non-resident roles.
    if roles and roles.issubset(resident_roles):
        if user.enabled:
            user.enabled = 0
            user.save(ignore_permissions=True)


def on_session_creation(login_manager=None):
    """
    Auto-verify email on successful web portal session creation.
    When a user logs in via web, their email is considered verified.
    """
    user = frappe.session.user
    if not user or user in ("Guest", "Administrator"):
        return

    now = frappe.utils.now_datetime()
    user_email = frappe.db.get_value("User", user, "email") or user

    # Mark Owners records as verified
    owners = frappe.get_all(
        "Owners",
        filters=[
            ["active", "=", 1],
            ["is_email_verified", "=", 0],
            ["email", "=", user_email]
        ],
        pluck="name"
    )
    for o_name in owners:
        frappe.db.set_value("Owners", o_name, {
            "is_email_verified": 1,
            "email_verified_on": now
        }, update_modified=False)

    # Mark Tenants records as verified
    tenants = frappe.get_all(
        "Tenants",
        filters=[
            ["active", "=", 1],
            ["is_email_verified", "=", 0],
            ["email", "=", user_email]
        ],
        pluck="name"
    )
    for t_name in tenants:
        frappe.db.set_value("Tenants", t_name, {
            "is_email_verified": 1,
            "email_verified_on": now
        }, update_modified=False)

    if owners or tenants:
        frappe.db.commit()


def mark_mobile_verified(mobile_no):
    """
    Mark mobile number as verified across active Owners and Tenants.
    Called when a user sends a message or completes OTP via WhatsApp or Telegram.
    """
    if not mobile_no:
        return

    # Clean mobile number
    clean_mobile = "".join(filter(str.isdigit, str(mobile_no)))
    if len(clean_mobile) > 10:
        clean_mobile = clean_mobile[-10:]

    if not clean_mobile:
        return

    now = frappe.utils.now_datetime()

    # Search for matching Owners
    matching_owners = frappe.db.sql("""
        SELECT name FROM `tabOwners`
        WHERE active = 1 AND is_mobile_verified = 0
          AND (RIGHT(REGEXP_REPLACE(mobile_no, '[^0-9]', ''), 10) = %s)
    """, (clean_mobile,), as_dict=True)

    for row in matching_owners:
        frappe.db.set_value("Owners", row.name, {
            "is_mobile_verified": 1,
            "mobile_verified_on": now
        }, update_modified=False)

    # Search for matching Tenants
    matching_tenants = frappe.db.sql("""
        SELECT name FROM `tabTenants`
        WHERE active = 1 AND is_mobile_verified = 0
          AND (RIGHT(REGEXP_REPLACE(mobile_no, '[^0-9]', ''), 10) = %s)
    """, (clean_mobile,), as_dict=True)

    for row in matching_tenants:
        frappe.db.set_value("Tenants", row.name, {
            "is_mobile_verified": 1,
            "mobile_verified_on": now
        }, update_modified=False)

    if matching_owners or matching_tenants:
        frappe.db.commit()

