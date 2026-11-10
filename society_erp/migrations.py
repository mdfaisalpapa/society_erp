
import frappe


def ensure_voting_participation_unique_index():
    """Prevent more than one participation per flat in a poll."""

    duplicates = frappe.db.sql(
        """
        SELECT poll, flat, COUNT(*) AS records
        FROM `tabVoting Participation`
        GROUP BY poll, flat
        HAVING COUNT(*) > 1
        LIMIT 1
        """
    )

    if duplicates:
        frappe.throw(
            "Cannot create unique voting index: duplicate poll/flat "
            "participation records exist."
        )

    frappe.db.add_unique(
        "Voting Participation",
        ["poll", "flat"],
        "unique_poll_flat",
    )


def ensure_provisional_electorate_unique_index():
    """Ensure flat number is unique within each electorate publication."""
    if frappe.db.exists("DocType", "Provisional Electorate Member"):
        frappe.db.add_unique(
            "Provisional Electorate Member",
            ["publication", "flat_no"],
            "uniq_prov_member_pub_flat",
        )


def ensure_push_subscription_endpoint_index():
    """Ensure endpoint has a unique prefix index to prevent duplicate subscriptions per device."""
    if frappe.db.exists("DocType", "Push Subscription"):
        indexes = frappe.db.sql(
            "SHOW INDEX FROM `tabPush Subscription` WHERE Key_name = 'idx_push_subscription_endpoint'",
            as_dict=True,
        )
        if not indexes:
            try:
                frappe.db.sql(
                    "CREATE UNIQUE INDEX idx_push_subscription_endpoint ON `tabPush Subscription` (endpoint(255))"
                )
            except Exception as e:
                frappe.log_error("Error creating endpoint index on Push Subscription", str(e))


