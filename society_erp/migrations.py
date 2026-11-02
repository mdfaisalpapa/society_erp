
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

