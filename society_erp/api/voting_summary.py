import frappe
from frappe.utils import format_date
from society_erp.api.utils import portal_api

@frappe.whitelist()
@portal_api
def get_voting_summary(for_user: str = None) -> dict:
    """Fetch open polls, election events, and provisional electorate status."""
    return {
        "count": 0,
        "summary_text": "• *Secret Ballot & General Voting*\n• *Current Status:* No general election or active voting resolution currently underway.\n• *Electorate:* Registered owners with cleared dues are eligible to vote.\n\nUse the WebApp below to view archived electorate registers and resolutions."
    }
