
import frappe


def get_context(context):
    # 1. Require authentication
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    user = frappe.session.user
    user_email = user.strip().lower()

    # 2. Identify the logged-in resident.
    # Check active tenants first, matching the resident dashboard logic.
    tenant_records = frappe.get_all(
        "Tenants",
        filters={"active": 1},
        fields=[
            "name", "flat", "tenant_name", "mobile_no",
            "email", "start_date", "end_date"
        ],
        order_by="flat asc",
    )

    tenant = next(
        (
            record for record in tenant_records
            if record.email
            and record.email.strip().lower() == user_email
        ),
        None,
    )

    owner = None

    if not tenant:
        # Preserve support for existing owner logins.
        owner_records = frappe.get_all(
            "Owners",
            filters={"active": 1},
            fields=[
                "name", "flat", "owner_name",
                "mobile_no", "email"
            ],
            order_by="flat asc",
        )

        owner = next(
            (
                record for record in owner_records
                if (
                    record.email
                    and record.email.strip().lower() == user_email
                )
                or record.name == user
            ),
            None,
        )

    resident = tenant or owner

    if not resident or not resident.flat:
        context.not_a_resident = True
        return context

    # 3. Common resident context
    flat_id = resident.flat
    context.flat_number = flat_id
    context.resident_type = "Tenant" if tenant else "Owner"
    context.resident_name = (
        tenant.tenant_name if tenant else owner.owner_name
    )
    context.is_tenant = bool(tenant)
    context.is_owner = bool(owner)
    context.not_a_resident = False

    # 4. Fetch registered owner details for this flat.
    registered_owner = frappe.db.get_value(
        "Owners",
        {"flat": flat_id, "active": 1},
        ["owner_name", "mobile_no", "email"],
        as_dict=True,
    )

    # Keep the template functional even if no active owner
    # record is available for this flat.
    context.owner_details = registered_owner or frappe._dict({
        "owner_name": "Not available",
        "mobile_no": None,
        "email": None,
    })

    # 5. Fetch permanent flat details from Customer.
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
            "corpus_fund": flat_doc.get("corpus_fund_contribution"),
        }

    return context

