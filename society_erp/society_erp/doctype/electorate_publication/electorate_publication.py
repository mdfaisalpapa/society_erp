import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime


class ElectoratePublication(Document):
    def before_validate(self):
        if not self.status:
            self.status = "Draft"
        if not self.version:
            self.version = 1

    def validate(self):
        if self.dues_enforcement_enabled:
            if not self.dues_cutoff_date:
                frappe.throw(_("Dues Cutoff Date is required when Dues Enforcement is enabled."))
            if self.dues_threshold is None:
                frappe.throw(_("Dues Threshold is required when Dues Enforcement is enabled."))
        if self.status == "Approved" and not self.electorate_content_hash:
            frappe.throw(_("Approved electorate must have a certified electorate content hash."))

    def before_save(self):
        # Prevent modification if already Approved or Superceded
        if not self.is_new() and self.get_db_value("status") == "Approved":
            # Only allow status change to Superceded/Cancelled, not edits to data
            for field in ("dues_enforcement_enabled", "dues_cutoff_date", "dues_threshold",
                          "maintenance_receivable_accounts", "version", "electorate_content_hash"):
                if self.has_value_changed(field):
                    frappe.throw(_("Cannot modify field '{0}' on an approved electorate publication.").format(field))


@frappe.whitelist()
def generate_draft(publication_name):
    from society_erp.voting.electorate import generate_draft_electorate
    return generate_draft_electorate(publication_name)


@frappe.whitelist()
def publish(publication_name):
    from society_erp.voting.electorate import publish_electorate
    return publish_electorate(publication_name)


@frappe.whitelist()
def close_objections(publication_name):
    from society_erp.voting.electorate import close_objections_submission
    return close_objections_submission(publication_name)


@frappe.whitelist()
def approve(publication_name, certified_by=None, notes=None):
    from society_erp.voting.electorate import approve_electorate
    return approve_electorate(publication_name, certified_by=certified_by, notes=notes)
