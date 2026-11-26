# Copyright (c) 2026, Society ERP and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime


def _get_active_residential_flat(user: str) -> str | None:
    """Return the active residential flat for a user, excluding tenants and commercial units."""
    user_email = frappe.db.get_value("User", user, "email")
    or_filters = [{"linked_user": user}]
    if user_email:
        or_filters.append({"email": user_email})

    owners = frappe.get_all(
        "Owners",
        filters={"active": 1},
        or_filters=or_filters,
        fields=["flat"],
        order_by="creation asc",
    )
    for owner in owners:
        if not owner.flat:
            continue
        customer_group = frappe.db.get_value("Customer", owner.flat, "customer_group")
        if customer_group != "Commercial":
            return owner.flat
    return None


class ByeLawClauseComment(Document):
    def before_insert(self):
        self.submitted_by_user = frappe.session.user

    def validate(self):
        if not self.clause:
            frappe.throw(_("Clause is required."), frappe.ValidationError)

        clause_info = frappe.db.get_value(
            "Bye-Law Clause",
            self.clause,
            ["consultation", "is_readonly"],
            as_dict=True,
        )
        if not clause_info:
            frappe.throw(_("Referenced Bye-Law Clause does not exist."), frappe.ValidationError)

        self.consultation = clause_info.consultation

        if clause_info.is_readonly:
            frappe.throw(_("Comments are not allowed on a read-only clause."), frappe.ValidationError)

        consultation_info = frappe.db.get_value(
            "Bye-Law Consultation",
            self.consultation,
            ["status", "consultation_start", "consultation_end"],
            as_dict=True,
        )
        if not consultation_info or consultation_info.status != "Consultation Open":
            frappe.throw(_("Consultation is not currently open for comments."), frappe.ValidationError)

        now = now_datetime()
        if consultation_info.consultation_start and now < get_datetime(consultation_info.consultation_start):
            frappe.throw(_("Consultation has not started yet."), frappe.ValidationError)
        if consultation_info.consultation_end and now > get_datetime(consultation_info.consultation_end):
            frappe.throw(_("Consultation period has ended."), frappe.ValidationError)

        if not self.submitted_by_user:
            self.submitted_by_user = frappe.session.user

        is_sys_mgr = "System Manager" in frappe.get_roles(frappe.session.user)
        if not is_sys_mgr:
            flat_unit = _get_active_residential_flat(self.submitted_by_user)
            if not flat_unit:
                frappe.throw(
                    _("Only active residential owners may submit or edit comments."),
                    frappe.ValidationError,
                )
            self.flat_unit = flat_unit

            if self.is_new():
                existing_count = frappe.db.count(
                    "Bye-Law Clause Comment",
                    filters={"clause": self.clause, "submitted_by_user": self.submitted_by_user},
                )
                if existing_count >= 3:
                    frappe.throw(
                        _("Maximum of 3 comments per clause per user reached."),
                        frappe.ValidationError,
                    )
            else:
                prev_status = frappe.db.get_value("Bye-Law Clause Comment", self.name, "disposition_status")
                if prev_status and prev_status != "Pending":
                    frappe.throw(
                        _("Cannot edit comment after disposition status is no longer Pending."),
                        frappe.ValidationError,
                    )
