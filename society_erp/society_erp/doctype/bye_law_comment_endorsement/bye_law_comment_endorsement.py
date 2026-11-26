# Copyright (c) 2026, Society ERP and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from society_erp.society_erp.doctype.bye_law_clause_comment.bye_law_clause_comment import (
    _get_active_residential_flat,
)


class ByeLawCommentEndorsement(Document):
    def before_insert(self):
        self.user = frappe.session.user

    def validate(self):
        if not self.user:
            self.user = frappe.session.user

        existing = frappe.db.exists(
            "Bye-Law Comment Endorsement",
            {"comment": self.comment, "user": self.user, "name": ["!=", self.name or ""]},
        )
        if existing:
            frappe.throw(
                _("You have already endorsed this comment."),
                frappe.ValidationError,
            )

        is_sys_mgr = "System Manager" in frappe.get_roles(frappe.session.user)
        if not is_sys_mgr:
            flat_unit = _get_active_residential_flat(self.user)
            if not flat_unit:
                frappe.throw(
                    _("Only active residential owners may endorse comments."),
                    frappe.ValidationError,
                )
            self.flat_unit = flat_unit
