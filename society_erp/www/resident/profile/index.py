
import frappe


def get_context(context):
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

    return context

