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


def _require_committee_access() -> str:
    user = _require_logged_in()
    from society_erp.www.resident.committee.index import check_committee_access

    has_access, _info = check_committee_access(user)
    if not has_access:
        frappe.throw(_("Committee access required."), frappe.PermissionError)
    return user


@frappe.whitelist()
def committee_list_consultations() -> list[dict]:
    _require_committee_access()
    consultations = frappe.get_all(
        "Bye-Law Consultation",
        fields=["name", "title", "status", "consultation_start", "consultation_end"],
        order_by="creation desc",
        ignore_permissions=True,
    )
    for c in consultations:
        clauses = frappe.get_all(
            "Bye-Law Clause",
            filters={"consultation": c.name},
            fields=["is_readonly"],
            ignore_permissions=True,
        )
        c["total_clauses"] = len(clauses)
        c["locked_clauses"] = sum(1 for cl in clauses if cl.is_readonly)
        c["open_clauses"] = c["total_clauses"] - c["locked_clauses"]

        comments = frappe.get_all(
            "Bye-Law Clause Comment",
            filters={"consultation": c.name},
            fields=["disposition_status"],
            ignore_permissions=True,
        )
        c["total_comments"] = len(comments)
        c["pending_comments"] = sum(1 for cm in comments if (cm.disposition_status or "Pending") == "Pending")
        c["accepted_comments"] = sum(
            1 for cm in comments if cm.disposition_status in ("Accepted", "Partially Accepted")
        )
        c["rejected_comments"] = sum(
            1 for cm in comments if cm.disposition_status in ("Rejected", "Noted")
        )
    return consultations


@frappe.whitelist()
def committee_save_consultation(
    name: str | None = None,
    title: str | None = None,
    status: str | None = None,
    consultation_start: str | None = None,
    consultation_end: str | None = None,
    description: str | None = None,
) -> dict:
    _require_committee_access()
    if name:
        doc = frappe.get_doc("Bye-Law Consultation", name)
    else:
        if not title:
            frappe.throw(_("Title is required."), frappe.ValidationError)
        doc = frappe.new_doc("Bye-Law Consultation")

    if title is not None:
        doc.title = title
    if status is not None:
        doc.status = status
    if consultation_start is not None:
        doc.consultation_start = consultation_start or None
    if consultation_end is not None:
        doc.consultation_end = consultation_end or None

    doc.save(ignore_permissions=True)
    return {
        "name": doc.name,
        "title": doc.title,
        "status": doc.status,
        "consultation_start": str(doc.consultation_start) if doc.consultation_start else None,
        "consultation_end": str(doc.consultation_end) if doc.consultation_end else None,
    }


@frappe.whitelist()
def committee_get_clauses(consultation: str) -> list[dict]:
    _require_committee_access()
    clauses = frappe.get_all(
        "Bye-Law Clause",
        filters={"consultation": consultation},
        fields=[
            "name",
            "sequence_no",
            "chapter",
            "clause_number",
            "clause_title",
            "is_readonly",
            "readonly_reason",
            "disposition_outcome AS clause_disposition",
        ],
        order_by="sequence_no asc, creation asc",
        ignore_permissions=True,
    )
    comment_counts = {}
    for cm in frappe.get_all(
        "Bye-Law Clause Comment",
        filters={"consultation": consultation},
        fields=["clause"],
        ignore_permissions=True,
    ):
        comment_counts[cm.clause] = comment_counts.get(cm.clause, 0) + 1

    for cl in clauses:
        cl["comment_count"] = comment_counts.get(cl.name, 0)
    return clauses


@frappe.whitelist()
def committee_update_clause(
    clause_name: str,
    is_readonly: int | None = None,
    readonly_reason: str | None = None,
    clause_disposition: str | None = None,
) -> dict:
    _require_committee_access()
    doc = frappe.get_doc("Bye-Law Clause", clause_name)
    if is_readonly is not None:
        doc.is_readonly = frappe.utils.cint(is_readonly)
    if readonly_reason is not None:
        doc.readonly_reason = readonly_reason
    if clause_disposition is not None:
        doc.disposition_outcome = clause_disposition
    doc.save(ignore_permissions=True)
    return {
        "name": doc.name,
        "is_readonly": doc.is_readonly,
        "readonly_reason": doc.readonly_reason,
        "clause_disposition": doc.disposition_outcome,
    }


@frappe.whitelist()
def committee_import_clauses_upload(
    consultation: str,
    filename: str,
    file_content_b64: str,
    lock_unmodified: int = 1,
    replace_existing: int = 0,
    readonly_clauses: str | None = None,
    readonly_reason: str | None = None,
) -> dict:
    import base64
    from society_erp.byelaws_importer import import_clauses_from_file

    _require_committee_access()
    if "," in file_content_b64:
        file_content_b64 = file_content_b64.split(",", 1)[1]
    raw_bytes = base64.b64decode(file_content_b64)

    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": filename,
            "attached_to_doctype": "Bye-Law Consultation",
            "attached_to_name": consultation,
            "is_private": 1,
            "content": raw_bytes,
        }
    ).insert(ignore_permissions=True)

    return import_clauses_from_file(
        consultation=consultation,
        file_url=file_doc.file_url,
        replace_existing=replace_existing,
        readonly_clauses=readonly_clauses,
        readonly_reason=readonly_reason,
        lock_unmodified=lock_unmodified,
    )


@frappe.whitelist()
def committee_get_disposition_matrix(
    consultation: str | None = None,
    chapter: str | None = None,
    comment_type: str | None = None,
    disposition_status: str | None = None,
    clause_disposition: str | None = None,
) -> dict:
    from society_erp.society_erp.report.bye_law_disposition_matrix.bye_law_disposition_matrix import (
        get_data,
        get_report_summary,
    )

    _require_committee_access()
    filters = frappe._dict(
        {
            "consultation": consultation,
            "chapter": chapter,
            "comment_type": comment_type,
            "disposition_status": disposition_status,
            "clause_disposition": clause_disposition,
            "only_visible": 1,
        }
    )
    rows = get_data(filters)
    summary_list = get_report_summary(rows)
    summary = {s["label"]: s["value"] for s in summary_list}
    return {"summary": summary, "rows": rows}


@frappe.whitelist()
def committee_review_comment(
    comment_name: str,
    disposition_status: str,
    committee_response: str | None = None,
    clause_disposition: str | None = None,
) -> dict:
    user = _require_committee_access()
    doc = frappe.get_doc("Bye-Law Clause Comment", comment_name)
    doc.disposition_status = disposition_status
    if committee_response is not None:
        doc.committee_response = committee_response
    doc.reviewed_by = user
    doc.reviewed_on = now_datetime()
    doc.flags.ignore_validate = True
    doc.save(ignore_permissions=True)

    if clause_disposition:
        clause_doc = frappe.get_doc("Bye-Law Clause", doc.clause)
        clause_doc.disposition_outcome = clause_disposition
        clause_doc.save(ignore_permissions=True)

    return {
        "name": doc.name,
        "disposition_status": doc.disposition_status,
        "committee_response": doc.committee_response,
        "reviewed_by": doc.reviewed_by,
        "reviewed_on": str(doc.reviewed_on),
    }


def _assert_consultation_closed_for_polling(consultation_doc, starts_at=None):
    if consultation_doc.status in ("Draft", "Consultation Open"):
        frappe.throw(
            _("Polling cannot start while consultation is still in Draft or Consultation Open status. Close the consultation first."),
            frappe.ValidationError,
        )
    if consultation_doc.consultation_end and now_datetime() < get_datetime(consultation_doc.consultation_end):
        frappe.throw(
            _("Polling cannot start before the consultation end time."),
            frappe.ValidationError,
        )
    if starts_at and consultation_doc.consultation_end and get_datetime(starts_at) < get_datetime(consultation_doc.consultation_end):
        frappe.throw(
            _("Poll start time must be after the consultation end time."),
            frappe.ValidationError,
        )


def _create_consensus_poll_draft(
    title: str,
    poll_type: str,
    starts_at: str,
    ends_at: str,
    electorate_pub_doc,
    options_spec: list[tuple[str, str]],
    description: str | None = None,
) -> str:
    if electorate_pub_doc.status != "Approved" or not electorate_pub_doc.electorate_content_hash:
        frappe.throw(
            _("An Approved Electorate Publication with a valid content hash is required."),
            frappe.ValidationError,
        )
    if not starts_at or not ends_at or get_datetime(ends_at) <= get_datetime(starts_at):
        frappe.throw(_("Poll end time must be after start time."), frappe.ValidationError)

    poll_doc = frappe.get_doc(
        {
            "doctype": "Consensus Poll",
            "title": title[:140],
            "poll_type": poll_type,
            "status": "Draft",
            "starts_at": starts_at,
            "ends_at": ends_at,
            "description": description or "",
            "approved_publication_id": electorate_pub_doc.name,
            "approved_publication_version": electorate_pub_doc.version or 1,
            "approved_electorate_content_hash": electorate_pub_doc.electorate_content_hash,
            "scope_selections": [
                {
                    "scope_type": "publication",
                    "entity_ref": electorate_pub_doc.name,
                    "inclusion": "Include",
                }
            ],
        }
    ).insert(ignore_permissions=True)

    for idx, (opt_key, opt_label) in enumerate(options_spec, start=1):
        frappe.get_doc(
            {
                "doctype": "Consensus Poll Option",
                "poll": poll_doc.name,
                "option_key": opt_key,
                "option_label": opt_label,
                "display_order": idx,
                "enabled": 1,
            }
        ).insert(ignore_permissions=True)

    return poll_doc.name


@frappe.whitelist()
def committee_get_polling_readiness(consultation: str) -> dict:
    _require_committee_access()
    doc = frappe.get_doc("Bye-Law Consultation", consultation)

    consultation_closed = doc.status not in ("Draft", "Consultation Open")
    end_time_passed = (
        not doc.consultation_end or now_datetime() >= get_datetime(doc.consultation_end)
    )

    electorate_approved = False
    if doc.electorate_publication:
        pub_status = frappe.db.get_value("Electorate Publication", doc.electorate_publication, "status")
        electorate_approved = pub_status == "Approved"

    final_pdf_hashed = bool(doc.final_pdf and doc.final_pdf_sha256)

    contested_clauses = frappe.get_all(
        "Bye-Law Clause",
        filters={"consultation": doc.name, "disposition_outcome": "Contested - Poll Required"},
        fields=["name", "clause_number", "clause_title", "linked_consensus_poll"],
        order_by="sequence_no asc",
        ignore_permissions=True,
    )
    for cl in contested_clauses:
        cl["poll_status"] = (
            frappe.db.get_value("Consensus Poll", cl.linked_consensus_poll, "status")
            if cl.linked_consensus_poll
            else None
        )

    final_poll_status = (
        frappe.db.get_value("Consensus Poll", doc.final_adoption_poll, "status")
        if doc.final_adoption_poll
        else None
    )

    approved_publications = frappe.get_all(
        "Electorate Publication",
        filters={"status": "Approved"},
        fields=["name", "title", "version"],
        order_by="creation desc",
        ignore_permissions=True,
    )
    poll_types = frappe.get_all(
        "Consensus Poll Type",
        filters={"enabled": 1},
        fields=["name", "label"],
        order_by="name asc",
        ignore_permissions=True,
    )

    consensus_enabled = False
    if frappe.db.exists("DocType", "Voting Integration Settings"):
        consensus_enabled = bool(frappe.utils.cint(frappe.db.get_single_value("Voting Integration Settings", "enabled")))

    return {
        "consensus_enabled": consensus_enabled,
        "consultation_closed": consultation_closed,
        "end_time_passed": end_time_passed,
        "electorate_approved": electorate_approved,
        "electorate_publication": doc.electorate_publication,
        "final_pdf_hashed": final_pdf_hashed,
        "final_pdf_sha256": doc.final_pdf_sha256,
        "contested_clauses": contested_clauses,
        "final_adoption_poll": doc.final_adoption_poll,
        "final_poll_status": final_poll_status,
        "approved_publications": approved_publications,
        "poll_types": poll_types,
    }


@frappe.whitelist()
def committee_save_polling_config(consultation: str, electorate_publication: str | None = None) -> dict:
    _require_committee_access()
    doc = frappe.get_doc("Bye-Law Consultation", consultation)
    if electorate_publication:
        pub_status = frappe.db.get_value("Electorate Publication", electorate_publication, "status")
        if pub_status != "Approved":
            frappe.throw(_("Only an Approved Electorate Publication can be linked."), frappe.ValidationError)
    doc.electorate_publication = electorate_publication or None
    doc.save(ignore_permissions=True)
    return {"electorate_publication": doc.electorate_publication}


@frappe.whitelist()
def committee_generate_contested_clause_polls(
    consultation: str,
    poll_type: str,
    starts_at: str,
    ends_at: str,
) -> dict:
    _require_committee_access()
    doc = frappe.get_doc("Bye-Law Consultation", consultation)
    _assert_consultation_closed_for_polling(doc, starts_at=starts_at)

    if not doc.electorate_publication:
        frappe.throw(_("Please link an Approved Electorate Publication first."), frappe.ValidationError)
    pub_doc = frappe.get_doc("Electorate Publication", doc.electorate_publication)

    clauses = frappe.get_all(
        "Bye-Law Clause",
        filters={
            "consultation": doc.name,
            "disposition_outcome": "Contested - Poll Required",
            "linked_consensus_poll": ["in", ["", None]],
        },
        fields=["name", "clause_number", "clause_title"],
        order_by="sequence_no asc",
        ignore_permissions=True,
    )

    created_polls = []
    options_spec = [
        ("approve_proposed", "Approve Proposed Clause"),
        ("retain_model", "Retain TN Model / Reject"),
        ("abstain", "Abstain"),
    ]
    for cl in clauses:
        poll_title = f"{doc.title} — Clause {cl.clause_number}: {cl.clause_title}"
        poll_name = _create_consensus_poll_draft(
            title=poll_title,
            poll_type=poll_type,
            starts_at=starts_at,
            ends_at=ends_at,
            electorate_pub_doc=pub_doc,
            options_spec=options_spec,
        )
        frappe.db.set_value("Bye-Law Clause", cl.name, "linked_consensus_poll", poll_name)
        created_polls.append({"clause": cl.name, "poll": poll_name})

    if doc.status == "Under Review":
        doc.status = "Finalized for Voting"
        doc.save(ignore_permissions=True)

    return {"created_polls": created_polls}


@frappe.whitelist()
def committee_generate_final_adoption_poll(
    consultation: str,
    poll_type: str,
    starts_at: str,
    ends_at: str,
) -> dict:
    _require_committee_access()
    doc = frappe.get_doc("Bye-Law Consultation", consultation)
    _assert_consultation_closed_for_polling(doc, starts_at=starts_at)

    if doc.final_adoption_poll:
        frappe.throw(_("Final adoption poll already exists for this consultation."), frappe.ValidationError)
    if not doc.final_pdf or not doc.final_pdf_sha256:
        frappe.throw(_("Final PDF and its SHA-256 hash are required before generating the final adoption poll."), frappe.ValidationError)
    if not doc.electorate_publication:
        frappe.throw(_("Please link an Approved Electorate Publication first."), frappe.ValidationError)

    pub_doc = frappe.get_doc("Electorate Publication", doc.electorate_publication)
    sha_short = doc.final_pdf_sha256[:12]
    poll_title = f"{doc.title} — Final Adoption (SHA-256: {sha_short})"
    options_spec = [
        ("approve_final", "Approve Final Bye-Laws"),
        ("reject_final", "Reject Final Bye-Laws"),
        ("abstain", "Abstain"),
    ]
    poll_name = _create_consensus_poll_draft(
        title=poll_title,
        poll_type=poll_type,
        starts_at=starts_at,
        ends_at=ends_at,
        electorate_pub_doc=pub_doc,
        options_spec=options_spec,
        description=f"Final PDF SHA-256: {doc.final_pdf_sha256}",
    )
    doc.final_adoption_poll = poll_name
    doc.status = "Finalized for Voting"
    doc.save(ignore_permissions=True)

    return {"poll": poll_name, "final_pdf_sha256": doc.final_pdf_sha256}
