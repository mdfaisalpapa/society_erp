import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

OFFICER_ROLES = {"System Manager", "Society Committee Member"}
OFFICER_ONLY_FIELDS = (
    "status",
    "officer_comments",
    "evidence_request_details",
    "applied_correction",
    "resolved_by",
    "resolved_on",
)


class ElectorateObjection(Document):
    def validate(self):
        pub = frappe.get_doc("Electorate Publication", self.publication)
        user = frappe.session.user
        roles = set(frappe.get_roles(user)) if user else set()
        is_officer = bool(roles & OFFICER_ROLES)

        if self.is_new():
            if pub.status != "Published":
                frappe.throw(_("Objections can only be submitted for published provisional electorates."))
            if pub.objection_submission_deadline and now_datetime() > frappe.utils.get_datetime(pub.objection_submission_deadline):
                frappe.throw(_("The objection submission deadline for this publication has passed."))

            # Non-officers cannot specify officer-only fields or non-default status on new objections
            if not is_officer:
                if self.status and self.status != "Submitted":
                    frappe.throw(_("Only election officers may set objection status."), frappe.PermissionError)
                for f in ("officer_comments", "evidence_request_details", "applied_correction", "resolved_by", "resolved_on"):
                    if self.get(f):
                        frappe.throw(_("Only election officers may set '{0}'.").format(f), frappe.PermissionError)
        else:
            # On existing objections:
            if not is_officer:
                # Prevent modifying another resident's objection
                if self.applicant_user and self.applicant_user != user:
                    frappe.throw(_("Permission denied: cannot modify another resident's objection."), frappe.PermissionError)

                # Check officer-only fields
                for field in OFFICER_ONLY_FIELDS:
                    if self.has_value_changed(field):
                        # Allow authorized portal evidence submission to transition from "Evidence Requested" to "Under Review"
                        if field == "status" and getattr(self.flags, "submitting_evidence", False):
                            before = self.get_doc_before_save()
                            if before and before.status == "Evidence Requested" and self.status == "Under Review":
                                continue
                        frappe.throw(
                            _("Only election officers may modify '{0}'.").format(field),
                            frappe.PermissionError,
                        )

        if self.status in ("Accepted", "Rejected"):
            if not self.resolved_by:
                self.resolved_by = frappe.session.user
            if not self.resolved_on:
                self.resolved_on = now_datetime()


@frappe.whitelist()
def request_evidence(objection_name, details):
    frappe.only_for(["System Manager", "Society Committee Member"])
    obj = frappe.get_doc("Electorate Objection", objection_name)
    obj.status = "Evidence Requested"
    obj.evidence_request_details = details
    obj.save(ignore_permissions=True)
    return {"status": obj.status}


@frappe.whitelist()
def resolve_objection(objection_name, decision, comments, applied_correction=None):
    frappe.only_for(["System Manager", "Society Committee Member"])
    if decision not in ("Accepted", "Rejected"):
        frappe.throw(_("Decision must be either Accepted or Rejected."))
    obj = frappe.get_doc("Electorate Objection", objection_name)
    obj.status = decision
    obj.officer_comments = comments
    obj.applied_correction = applied_correction
    obj.resolved_by = frappe.session.user
    obj.resolved_on = now_datetime()
    obj.save(ignore_permissions=True)
    return {"status": obj.status, "resolved_by": obj.resolved_by, "resolved_on": obj.resolved_on}
