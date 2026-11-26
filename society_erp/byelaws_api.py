from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from society_erp.society_erp.doctype.bye_law_clause_comment.bye_law_clause_comment import (
    _get_active_residential_flat,
)

ADMIN_ROLES = {"System Manager", "Society Committee Member"}


def _require_logged_in() -> str:
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Please log in to access Bye-Law Consultations."), frappe.PermissionError)
    return user


def _is_admin(user: str) -> bool:
    return bool(ADMIN_ROLES.intersection(set(frappe.get_roles(user))))


def _get_user_flat_units(user: str) -> list[str]:
    flat = _get_active_residential_flat(user)
    return [flat] if flat else []


@frappe.whitelist()
def get_consultation_data(consultation: str | None = None) -> dict:
    user = _require_logged_in()
    is_admin = _is_admin(user)
    flat_units = _get_user_flat_units(user)

    if not flat_units and not is_admin:
        return {
            "authorized": False,
            "message": "Only verified residential flat owners can access Bye-Law Consultations.",
        }

    filters = {} if is_admin else {"status": ["!=", "Draft"]}
    consultations = frappe.get_all(
        "Bye-Law Consultation",
        filters=filters,
        fields=["name", "title", "status"],
        order_by="creation desc",
    )

    if not consultations:
        return {
            "authorized": True,
            "is_admin": is_admin,
            "flat_units": flat_units,
            "consultations": [],
            "consultation": None,
            "clauses": [],
        }

    target_name = consultation or consultations[0].name
    if not any(c.name == target_name for c in consultations):
        target_name = consultations[0].name

    doc = frappe.get_doc("Bye-Law Consultation", target_name)
    consultation_meta = {
        "name": doc.name,
        "title": doc.title,
        "status": doc.status,
        "consultation_start": str(doc.consultation_start) if doc.consultation_start else None,
        "consultation_end": str(doc.consultation_end) if doc.consultation_end else None,
        "draft_pdf": doc.draft_pdf,
        "final_pdf": doc.final_pdf,
        "final_pdf_sha256": doc.final_pdf_sha256,
        "final_adoption_poll": doc.final_adoption_poll,
    }

    clauses = frappe.get_all(
        "Bye-Law Clause",
        filters={"consultation": doc.name},
        fields=[
            "name",
            "sequence_no",
            "chapter",
            "clause_number",
            "clause_title",
            "draft_text",
            "final_text",
            "is_readonly",
            "readonly_reason",
            "disposition_outcome",
            "linked_consensus_poll",
        ],
        order_by="sequence_no asc, creation asc",
    )

    comments = frappe.get_all(
        "Bye-Law Clause Comment",
        filters={"consultation": doc.name, "is_visible": 1},
        fields=[
            "name",
            "clause",
            "comment_type",
            "comment_text",
            "proposed_wording",
            "flat_unit",
            "disposition_status",
            "committee_response",
            "creation",
        ],
        order_by="creation asc",
    )

    comment_names = [c.name for c in comments]
    endorsement_counts: dict[str, int] = {}
    endorsed_by_me: set[str] = set()
    if comment_names:
        endorsements = frappe.get_all(
            "Bye-Law Comment Endorsement",
            filters={"comment": ["in", comment_names]},
            fields=["comment", "user"],
        )
        for e in endorsements:
            endorsement_counts[e.comment] = endorsement_counts.get(e.comment, 0) + 1
            if e.user == user:
                endorsed_by_me.add(e.comment)

    comments_by_clause: dict[str, list[dict]] = {}
    for c in comments:
        c_dict = {
            "name": c.name,
            "clause": c.clause,
            "comment_type": c.comment_type,
            "comment_text": c.comment_text,
            "proposed_wording": c.proposed_wording,
            "flat_unit": c.flat_unit,
            "disposition_status": c.disposition_status,
            "committee_response": c.committee_response,
            "creation": str(c.creation),
            "endorsement_count": endorsement_counts.get(c.name, 0),
            "endorsed_by_me": c.name in endorsed_by_me,
        }
        comments_by_clause.setdefault(c.clause, []).append(c_dict)

    for cl in clauses:
        cl["comments"] = comments_by_clause.get(cl.name, [])

    return {
        "authorized": True,
        "is_admin": is_admin,
        "flat_units": flat_units,
        "consultations": consultations,
        "consultation": consultation_meta,
        "clauses": clauses,
    }


@frappe.whitelist()
def submit_clause_comment(
    clause: str,
    comment_type: str,
    comment_text: str,
    proposed_wording: str | None = None,
) -> dict:
    _require_logged_in()
    doc = frappe.get_doc(
        {
            "doctype": "Bye-Law Clause Comment",
            "clause": clause,
            "comment_type": comment_type,
            "comment_text": comment_text,
            "proposed_wording": proposed_wording or "",
        }
    ).insert()

    return {
        "name": doc.name,
        "clause": doc.clause,
        "comment_type": doc.comment_type,
        "comment_text": doc.comment_text,
        "proposed_wording": doc.proposed_wording,
        "flat_unit": doc.flat_unit,
        "disposition_status": doc.disposition_status,
        "committee_response": doc.committee_response,
        "creation": str(doc.creation),
        "endorsement_count": 0,
        "endorsed_by_me": False,
    }


@frappe.whitelist()
def toggle_comment_endorsement(comment: str) -> dict:
    user = _require_logged_in()
    is_admin = _is_admin(user)
    if not is_admin and not _get_user_flat_units(user):
        frappe.throw(
            _("Only active residential owners may endorse comments."),
            frappe.ValidationError,
        )

    consultation_name = frappe.db.get_value("Bye-Law Clause Comment", comment, "consultation")
    if not consultation_name:
        frappe.throw(_("Comment not found."), frappe.ValidationError)

    c_info = frappe.db.get_value(
        "Bye-Law Consultation",
        consultation_name,
        ["status", "consultation_start", "consultation_end"],
        as_dict=True,
    )
    if not c_info or c_info.status != "Consultation Open":
        frappe.throw(_("Endorsements are only allowed while consultation is open."), frappe.ValidationError)

    now = now_datetime()
    if c_info.consultation_start and now < get_datetime(c_info.consultation_start):
        frappe.throw(_("Consultation has not started yet."), frappe.ValidationError)
    if c_info.consultation_end and now > get_datetime(c_info.consultation_end):
        frappe.throw(_("Consultation period has ended."), frappe.ValidationError)

    existing = frappe.db.get_value(
        "Bye-Law Comment Endorsement",
        {"comment": comment, "user": user},
        "name",
    )
    if existing:
        frappe.delete_doc("Bye-Law Comment Endorsement", existing, ignore_permissions=True)
        endorsed = False
    else:
        frappe.get_doc(
            {
                "doctype": "Bye-Law Comment Endorsement",
                "comment": comment,
            }
        ).insert()
        endorsed = True

    count = frappe.db.count("Bye-Law Comment Endorsement", {"comment": comment})
    return {"endorsed": endorsed, "endorsement_count": count}
