
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

