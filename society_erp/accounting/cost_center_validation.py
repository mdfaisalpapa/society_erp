import frappe


def validate_required_cost_center(doc, method=None):
    """
    Require a Cost Center on GL Entries where the linked Account
    has 'Require Cost Center' enabled.
    """

    if not doc.account:
        return

    requires_cost_center = frappe.db.get_value(
        "Account",
        doc.account,
        "custom_require_cost_center",
    )

    if requires_cost_center and not doc.cost_center:
        frappe.throw(
            f"Cost Center is mandatory for Account: {doc.account}"
        )