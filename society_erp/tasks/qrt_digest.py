import frappe
from society_erp.api.qrt_maintenance import post_unassigned_tickets_summary


def morning_unassigned_tickets_digest():
    """Daily 08:00 morning digest of unassigned tickets sent to QRT Telegram group."""
    post_unassigned_tickets_summary(time_of_day="Morning (08:00)")


def evening_unassigned_tickets_digest():
    """Daily 18:00 evening digest of unassigned tickets sent to QRT Telegram group."""
    post_unassigned_tickets_summary(time_of_day="Evening (18:00)")
