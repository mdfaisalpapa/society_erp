"""Resident Portal API for Voting Engine Status, Provisional Electorate and Objections."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime


@frappe.whitelist()
def get_voting_status():
    """Return whether Legacy Voting or Consensus is active."""
    settings = frappe.get_single("Society ERP Settings")
    engine = getattr(settings, "voting_engine_active", "Legacy Voting")
    return {
        "voting_engine_active": engine,
        "is_consensus": engine == "Consensus",
    }


@frappe.whitelist()
def get_provisional_electorates():
    """List provisional or approved electorate publications available for resident inspection."""
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Please log in to continue."), frappe.PermissionError)

    pubs = frappe.get_all(
        "Electorate Publication",
        filters={"status": ["in", ["Published", "Objections Closed", "Approved"]]},
        fields=[
            "name", "title", "status", "version", "published_on",
            "objection_submission_deadline", "objection_resolution_deadline",
            "dues_enforcement_enabled", "dues_cutoff_date", "dues_threshold",
            "eligible_count", "excluded_count", "total_flats_evaluated",
            "electorate_content_hash",
        ],
        order_by="published_on desc, creation desc",
    )
    return pubs


@frappe.whitelist()
def get_electorate_details(publication_name: str):
    """Return self-view with full details for logged-in user, and masked community directory."""
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Please log in to continue."), frappe.PermissionError)

    if not publication_name or not frappe.db.exists("Electorate Publication", publication_name):
        frappe.throw(_("Publication not found."))

    pub = frappe.get_doc("Electorate Publication", publication_name)
    if pub.status not in ("Published", "Objections Closed", "Approved"):
        frappe.throw(_("Publication is not publicly viewable."))

    # 1. Self-view: flats linked to logged-in user
    # Find all flats where user is voter_user or where user is linked to the flat's Owner record
    my_flats = frappe.get_all(
        "Owners",
        filters={"linked_user": user, "active": 1},
        fields=["flat"],
    )
    flat_names = {row.flat for row in my_flats if row.flat}

    my_members = frappe.get_all(
        "Provisional Electorate Member",
        filters={
            "publication": pub.name,
            "voter_user": user,
        },
        fields=[
            "name", "flat_no", "block", "uds", "owner_name", "voter_email", "voter_phone",
            "voting_weight", "eligibility_status", "exclusion_reason", "outstanding_dues", "notes",
        ],
    )
    already_flat_nos = {m.flat_no for m in my_members}
    # Add any flat owned by user that was excluded or had a different voter_user
    remaining_flats = flat_names - already_flat_nos
    if remaining_flats:
        extra_members = frappe.get_all(
            "Provisional Electorate Member",
            filters={
                "publication": pub.name,
                "flat_no": ["in", list(remaining_flats)],
            },
            fields=[
                "name", "flat_no", "block", "uds", "owner_name", "voter_email", "voter_phone",
                "voting_weight", "eligibility_status", "exclusion_reason", "outstanding_dues", "notes",
            ],
        )
        my_members.extend(extra_members)

    # 2. My objections for this publication
    my_objections = frappe.get_all(
        "Electorate Objection",
        filters={"publication": pub.name, "applicant_user": user},
        fields=[
            "name", "flat_no", "status", "objection_type", "details",
            "evidence_request_details", "officer_comments", "applied_correction", "creation",
        ],
        order_by="creation desc",
    )

    # 3. Minimal community directory (Masked) - minimal info only: flat_no, masked name, block, status
    directory = frappe.get_all(
        "Provisional Electorate Member",
        filters={"publication": pub.name},
        fields=[
            "flat_no", "masked_voter_name", "block", "eligibility_status",
        ],
        order_by="flat_no asc",
    )

    can_submit_objection = (
        pub.status == "Published"
        and (not pub.objection_submission_deadline or now_datetime() <= get_datetime(pub.objection_submission_deadline))
    )

    return {
        "publication": {
            "name": pub.name,
            "title": pub.title,
            "status": pub.status,
            "version": pub.version,
            "published_on": pub.published_on,
            "objection_submission_deadline": pub.objection_submission_deadline,
            "objection_resolution_deadline": pub.objection_resolution_deadline,
            "dues_enforcement_enabled": pub.dues_enforcement_enabled,
            "dues_cutoff_date": pub.dues_cutoff_date,
            "dues_threshold": pub.dues_threshold,
            "eligible_count": pub.eligible_count,
            "excluded_count": pub.excluded_count,
            "total_flats_evaluated": pub.total_flats_evaluated,
            "electorate_content_hash": pub.electorate_content_hash,
            "can_submit_objection": can_submit_objection,
        },
        "self_records": my_members,
        "my_objections": my_objections,
        "directory": directory,
    }


@frappe.whitelist(methods=["POST"])
def submit_objection(
    publication_name: str,
    flat_no: str,
    objection_type: str,
    details: str,
    supporting_document: str | None = None,
):
    """Submit an objection to the provisional electorate list."""
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Please log in to submit an objection."), frappe.PermissionError)

    if not publication_name or not flat_no or not objection_type or not details:
        frappe.throw(_("Publication, flat number, objection type, and details are required."))

    pub = frappe.get_doc("Electorate Publication", publication_name)
    if pub.status != "Published":
        frappe.throw(_("Objections can only be submitted for published provisional electorates."))

    if pub.objection_submission_deadline and now_datetime() > get_datetime(pub.objection_submission_deadline):
        frappe.throw(_("The objection submission deadline for this publication has passed."))

    user_fullname = frappe.db.get_value("User", user, "full_name") or user
    user_contact = frappe.db.get_value("User", user, "mobile_no") or frappe.db.get_value("User", user, "email")

    obj = frappe.get_doc({
        "doctype": "Electorate Objection",
        "publication": pub.name,
        "flat_no": flat_no,
        "applicant_user": user,
        "applicant_name": user_fullname,
        "applicant_contact": user_contact,
        "objection_type": objection_type,
        "details": details,
        "supporting_document": supporting_document,
        "status": "Submitted",
    })
    obj.insert(ignore_permissions=True)
    return {"success": True, "objection": obj.name, "status": obj.status}


@frappe.whitelist(methods=["POST"])
def submit_additional_evidence(objection_name: str, evidence_file: str):
    """Submit additional evidence requested by the election officer."""
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Please log in to continue."), frappe.PermissionError)

    obj = frappe.get_doc("Electorate Objection", objection_name)
    is_officer = bool(set(frappe.get_roles(user)) & {"System Manager", "Society Committee Member"})
    if obj.applicant_user != user and not is_officer:
        frappe.throw(_("Permission denied."), frappe.PermissionError)

    obj.additional_evidence = evidence_file
    obj.status = "Under Review"
    obj.flags.submitting_evidence = True
    obj.save(ignore_permissions=True)
    return {"success": True, "status": obj.status}
