# Copyright (c) 2026, Society ERP and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint


def execute(filters=None):
    filters = frappe._dict(filters or {})
    columns = get_columns()
    data = get_data(filters)
    report_summary = get_report_summary(data)
    return columns, data, None, None, report_summary


def get_columns():
    return [
        {"fieldname": "chapter", "label": _("Chapter"), "fieldtype": "Data", "width": 160},
        {"fieldname": "clause_number", "label": _("Clause No"), "fieldtype": "Data", "width": 90},
        {"fieldname": "clause_title", "label": _("Clause Title"), "fieldtype": "Data", "width": 200},
        {"fieldname": "clause", "label": _("Clause"), "fieldtype": "Link", "options": "Bye-Law Clause", "width": 120},
        {"fieldname": "comment", "label": _("Comment"), "fieldtype": "Link", "options": "Bye-Law Clause Comment", "width": 120},
        {"fieldname": "flat_unit", "label": _("Flat Unit"), "fieldtype": "Data", "width": 100},
        {"fieldname": "submitted_by_user", "label": _("Submitted By"), "fieldtype": "Link", "options": "User", "width": 160},
        {"fieldname": "comment_type", "label": _("Type"), "fieldtype": "Data", "width": 110},
        {"fieldname": "endorsement_count", "label": _("Endorsements"), "fieldtype": "Int", "width": 105},
        {"fieldname": "comment_text", "label": _("Comment Text"), "fieldtype": "Data", "width": 260},
        {"fieldname": "proposed_wording", "label": _("Proposed Wording"), "fieldtype": "Data", "width": 220},
        {"fieldname": "disposition_status", "label": _("Disposition Status"), "fieldtype": "Data", "width": 140},
        {"fieldname": "committee_response", "label": _("Committee Response"), "fieldtype": "Data", "width": 220},
        {"fieldname": "clause_disposition", "label": _("Clause Disposition"), "fieldtype": "Data", "width": 150},
        {"fieldname": "reviewed_by", "label": _("Reviewed By"), "fieldtype": "Link", "options": "User", "width": 150},
        {"fieldname": "reviewed_on", "label": _("Reviewed On"), "fieldtype": "Datetime", "width": 150},
    ]


def get_data(filters):
    conditions = []
    values = {}

    if filters.get("consultation"):
        conditions.append("cm.consultation = %(consultation)s")
        values["consultation"] = filters.consultation

    if filters.get("chapter"):
        conditions.append("cl.chapter LIKE %(chapter)s")
        values["chapter"] = f"%{filters.chapter}%"

    if filters.get("comment_type"):
        conditions.append("cm.comment_type = %(comment_type)s")
        values["comment_type"] = filters.comment_type

    if filters.get("disposition_status"):
        conditions.append("cm.disposition_status = %(disposition_status)s")
        values["disposition_status"] = filters.disposition_status

    if filters.get("clause_disposition"):
        conditions.append("cl.disposition_outcome = %(clause_disposition)s")
        values["clause_disposition"] = filters.clause_disposition

    only_visible = 1 if filters.get("only_visible") is None else cint(filters.only_visible)
    if only_visible:
        conditions.append("cm.is_visible = 1")

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    return frappe.db.sql(
        f"""
        SELECT
            cl.chapter,
            cl.clause_number,
            cl.clause_title,
            cm.clause,
            cm.name AS comment,
            cm.flat_unit,
            cm.submitted_by_user,
            cm.comment_type,
            COUNT(e.name) AS endorsement_count,
            cm.comment_text,
            cm.proposed_wording,
            cm.disposition_status,
            cm.committee_response,
            cl.disposition_outcome AS clause_disposition,
            cm.reviewed_by,
            cm.reviewed_on
        FROM `tabBye-Law Clause Comment` cm
        INNER JOIN `tabBye-Law Clause` cl ON cl.name = cm.clause
        LEFT JOIN `tabBye-Law Comment Endorsement` e ON e.comment = cm.name
        {where_clause}
        GROUP BY cm.name
        ORDER BY cl.sequence_no ASC, endorsement_count DESC, cm.creation ASC
        """,
        values,
        as_dict=True,
    )


def get_report_summary(data):
    total_comments = len(data)
    pending_review = sum(1 for r in data if (r.get("disposition_status") or "Pending") == "Pending")
    accepted = sum(1 for r in data if r.get("disposition_status") in ("Accepted", "Partially Accepted"))
    rejected_noted = sum(1 for r in data if r.get("disposition_status") in ("Rejected", "Noted"))
    total_endorsements = sum(cint(r.get("endorsement_count") or 0) for r in data)

    return [
        {"value": total_comments, "label": _("Total Comments"), "datatype": "Int"},
        {"value": pending_review, "label": _("Pending Review"), "datatype": "Int", "indicator": "Orange"},
        {"value": accepted, "label": _("Accepted / Partially Accepted"), "datatype": "Int", "indicator": "Green"},
        {"value": rejected_noted, "label": _("Rejected / Noted"), "datatype": "Int", "indicator": "Red"},
        {"value": total_endorsements, "label": _("Total Endorsements"), "datatype": "Int", "indicator": "Blue"},
    ]
