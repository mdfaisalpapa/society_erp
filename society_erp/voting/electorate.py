"""Provisional Electorate Generation, Publication, Objection Review and Certification."""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

import frappe
from consensus.security.crypto import canonical_json_bytes
from frappe import _
from frappe.utils import get_datetime, getdate, now_datetime

# Poll types that use unit weight (1.000 per allocation) instead of UDS
_UNIT_WEIGHT_POLL_TYPES = ("Committee Voting", "Resident Poll")


def _parse_accounts(accounts_val: Any) -> list[str]:
    if not accounts_val:
        return []
    if isinstance(accounts_val, list):
        return [str(a).strip() for a in accounts_val if str(a).strip()]
    raw = str(accounts_val).strip()
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(a).strip() for a in parsed if str(a).strip()]
        except Exception:
            pass
    return [a.strip() for a in raw.split(",") if a.strip()]


def calculate_flat_maintenance_dues(flat: str, cutoff_date: str, accounts: list[str]) -> Decimal:
    """Calculate outstanding dues using Decimal precision against explicitly configured accounts.

    Capital/Corpus receivables are excluded by querying ONLY the configured accounts.
    """
    if not cutoff_date:
        frappe.throw(_("Eligibility cutoff date is required when dues enforcement is enabled."))
    if not accounts:
        frappe.throw(_("At least one maintenance receivable account must be configured."))

    res = frappe.db.sql(
        """
        SELECT COALESCE(SUM(gle.debit - gle.credit), 0)
        FROM `tabGL Entry` gle
        WHERE gle.party_type = 'Customer'
          AND gle.party = %s
          AND gle.posting_date <= %s
          AND gle.docstatus = 1
          AND IFNULL(gle.is_cancelled, 0) = 0
          AND gle.account IN %s
        """,
        (flat, getdate(cutoff_date), tuple(accounts)),
    )
    raw_bal = res[0][0] if res else 0
    return Decimal(str(raw_bal)).quantize(Decimal("0.01"))


def _resolve_voting_weight(
    uds: float,
    poll_type: str | None,
) -> tuple[Decimal, str | None]:
    """Resolve voting weight and optional exclusion reason for an eligible flat.

    Returns (weight, exclusion_reason_or_None).
    - Association Voting (default when poll_type is None or not in _UNIT_WEIGHT_POLL_TYPES):
        weight = authoritative flat UDS (3 decimal places).
        If UDS <= 0: returns (0.000, "Invalid or Zero UDS") – caller marks flat Excluded.
    - Committee Voting / Resident Poll:
        weight = 1.000 always.
    """
    if poll_type in _UNIT_WEIGHT_POLL_TYPES:
        return Decimal("1.000"), None

    # Association Voting: use UDS
    uds_dec = Decimal(str(uds)).quantize(Decimal("0.001"))
    if uds_dec <= Decimal("0.000"):
        return Decimal("0.000"), "Invalid or Zero UDS"
    return uds_dec, None


def generate_draft_electorate(publication_name: str) -> dict[str, Any]:
    """Evaluate all residential flats, apply owner-only and dues policies, and create provisional members.

    Voting weight policy:
    - Association Voting: voting_weight = authoritative flat UDS (Customer.custom_uds), quantized to 3 d.p.
      Flats with UDS <= 0 are Excluded with reason "Invalid or Zero UDS".
    - Committee Voting / Resident Poll: voting_weight = 1.000 per eligible allocation.
    """
    frappe.only_for(["System Manager", "Society Committee Member"])
    pub = frappe.get_doc("Electorate Publication", publication_name)
    if pub.status != "Draft":
        frappe.throw(_("Can only generate draft electorate when publication is in Draft status."))

    # Clear previous provisional members
    frappe.db.delete("Provisional Electorate Member", {"publication": pub.name})

    # Prepare dues accounts if enabled
    accounts = []
    threshold = Decimal("0.00")
    if pub.dues_enforcement_enabled:
        accounts = _parse_accounts(pub.maintenance_receivable_accounts)
        if not accounts:
            settings = frappe.get_single("Society ERP Settings")
            accounts = _parse_accounts(settings.default_maintenance_accounts)
        if not accounts:
            frappe.throw(_("Maintenance receivable accounts must be explicitly configured."))
        threshold = Decimal(str(pub.dues_threshold or 0)).quantize(Decimal("0.01"))

    poll_type = pub.poll_type or None  # None → Association Voting (UDS weights)

    # Fetch residential flats from Customer
    # Exclude commercial customers (e.g. CGEWHO developer account)
    flats = frappe.get_all(
        "Customer",
        filters={"customer_group": ["!=", "Commercial"]},
        fields=["name", "customer_name", "custom_block", "custom_uds", "custom_let_out_for_rent"],
        order_by="name asc",
    )

    eligible_count = 0
    excluded_count = 0
    total_voting_weight = Decimal("0.000")

    for flat in flats:
        flat_no = flat.name
        block = flat.custom_block or ""
        uds = float(flat.custom_uds or 0.0)

        # Check active owners for this residential flat
        active_owners = frappe.get_all(
            "Owners",
            filters={"flat": flat_no, "active": 1},
            fields=["name", "owner_name", "linked_user", "email", "mobile_no"],
            order_by="creation asc",
        )

        owner_doc = None
        owner_name = ""
        voter_user = None
        voter_email = ""
        voter_phone = ""
        outstanding_dues = Decimal("0.00")
        weight = Decimal("0.000")
        status = "Excluded"
        reason = "None"
        notes = ""

        if len(active_owners) == 0:
            status = "Excluded"
            reason = "No Active Owner"
            notes = "No active owner registered for residential flat."
        elif len(active_owners) > 1:
            # Joint ownership policy: Never silently choose! Exclude until nomination/objection resolved.
            status = "Excluded"
            reason = "Multiple Active Owners"
            owner_name = ", ".join(o.owner_name for o in active_owners if o.owner_name)
            notes = "Multiple active owners registered. Explicit nomination required."
        else:
            # Exactly one active owner
            owner = active_owners[0]
            owner_doc = owner.name
            owner_name = owner.owner_name or ""
            voter_email = owner.email or ""
            voter_phone = owner.mobile_no or ""
            voter_user = owner.linked_user

            # If no linked_user set directly on Owners, look up by email
            if not voter_user and voter_email:
                user_match = frappe.db.get_value("User", {"email": voter_email, "enabled": 1}, "name")
                if user_match:
                    voter_user = user_match

            if not voter_user:
                status = "Excluded"
                reason = "Missing Contact User"
                notes = "Owner has no active linked Frappe user account."
            else:
                # Check dues if enforcement enabled
                if pub.dues_enforcement_enabled:
                    outstanding_dues = calculate_flat_maintenance_dues(
                        flat_no, pub.dues_cutoff_date, accounts
                    )
                    if outstanding_dues > threshold:
                        status = "Excluded"
                        reason = "Unreconciled Dues Above Threshold"
                        notes = f"Outstanding dues {outstanding_dues} exceed threshold {threshold}."
                    else:
                        # Resolve voting weight; may still exclude if UDS invalid
                        resolved_weight, uds_exclusion_reason = _resolve_voting_weight(uds, poll_type)
                        if uds_exclusion_reason:
                            status = "Excluded"
                            reason = uds_exclusion_reason
                            notes = f"UDS value {uds} is invalid or zero; cannot assign voting weight."
                        else:
                            status = "Eligible"
                            reason = "None"
                            weight = resolved_weight
                else:
                    # Resolve voting weight; may still exclude if UDS invalid (Association Voting only)
                    resolved_weight, uds_exclusion_reason = _resolve_voting_weight(uds, poll_type)
                    if uds_exclusion_reason:
                        status = "Excluded"
                        reason = uds_exclusion_reason
                        notes = f"UDS value {uds} is invalid or zero; cannot assign voting weight."
                    else:
                        status = "Eligible"
                        reason = "None"
                        weight = resolved_weight

        if status == "Eligible":
            eligible_count += 1
            total_voting_weight += weight
        else:
            excluded_count += 1

        frappe.get_doc({
            "doctype": "Provisional Electorate Member",
            "publication": pub.name,
            "flat_no": flat_no,
            "block": block,
            "uds": uds,
            "owner_doc": owner_doc,
            "owner_name": owner_name,
            "voter_user": voter_user,
            "voter_email": voter_email,
            "voter_phone": voter_phone,
            "eligibility_status": status,
            "exclusion_reason": reason,
            "voting_weight": float(weight),
            "outstanding_dues": float(outstanding_dues),
            "notes": notes,
        }).insert(ignore_permissions=True)

    pub.total_flats_evaluated = len(flats)
    pub.eligible_count = eligible_count
    pub.excluded_count = excluded_count
    pub.total_voting_weight = float(total_voting_weight)
    pub.save(ignore_permissions=True)

    return {
        "publication": pub.name,
        "total_flats_evaluated": pub.total_flats_evaluated,
        "eligible_count": pub.eligible_count,
        "excluded_count": pub.excluded_count,
        "total_voting_weight": pub.total_voting_weight,
    }


def publish_electorate(publication_name: str) -> dict[str, Any]:
    """Publish draft electorate for resident inspection and objection submission."""
    frappe.only_for(["System Manager", "Society Committee Member"])
    pub = frappe.get_doc("Electorate Publication", publication_name)
    if pub.status != "Draft":
        frappe.throw(_("Can only publish an electorate that is currently in Draft."))
    if not pub.total_flats_evaluated:
        frappe.throw(_("Please generate the draft electorate before publishing."))

    now = now_datetime()
    pub.status = "Published"
    pub.published_on = now
    if not pub.objection_submission_deadline:
        from datetime import timedelta
        pub.objection_submission_deadline = now + timedelta(days=pub.dues_reconciliation_gap_days or 7)
    pub.save(ignore_permissions=True)
    return {"publication": pub.name, "status": pub.status, "published_on": pub.published_on}


def close_objections_submission(publication_name: str) -> dict[str, Any]:
    """Close the objection submission window. New objections are rejected while officer review continues."""
    frappe.only_for(["System Manager", "Society Committee Member"])
    pub = frappe.get_doc("Electorate Publication", publication_name)
    if pub.status != "Published":
        frappe.throw(_("Can only close objections for a Published electorate."))
    pub.status = "Objections Closed"
    pub.save(ignore_permissions=True)
    return {"publication": pub.name, "status": pub.status}


def compute_electorate_manifest(publication_name: str) -> tuple[dict[str, Any], str]:
    """Compute the canonical electorate manifest and SHA-256 content hash."""
    pub = frappe.get_doc("Electorate Publication", publication_name)
    members = frappe.get_all(
        "Provisional Electorate Member",
        filters={"publication": pub.name},
        fields=[
            "flat_no",
            "owner_name",
            "voter_user",
            "voting_weight",
            "eligibility_status",
            "exclusion_reason",
            "outstanding_dues",
            "block",
            "uds",
        ],
        order_by="flat_no asc",
    )

    accounts = _parse_accounts(pub.maintenance_receivable_accounts)
    threshold = Decimal(str(pub.dues_threshold or 0)).quantize(Decimal("0.01"))
    total_weight = Decimal(str(pub.total_voting_weight or 0)).quantize(Decimal("0.001"))

    canonical_payload: dict[str, Any] = {
        "publication_id": pub.name,
        "version": int(pub.version),
        "poll_type": pub.poll_type or "Association Voting",
        "dues_enforcement_enabled": bool(pub.dues_enforcement_enabled),
        "dues_cutoff_date": str(pub.dues_cutoff_date) if pub.dues_cutoff_date else None,
        "dues_reconciliation_gap_days": int(pub.dues_reconciliation_gap_days or 0),
        "dues_threshold": f"{threshold:.2f}",
        "accounts": sorted(accounts),
        "total_flats_evaluated": int(pub.total_flats_evaluated or 0),
        "eligible_count": int(pub.eligible_count or 0),
        "excluded_count": int(pub.excluded_count or 0),
        "total_voting_weight": f"{total_weight:.3f}",
        "records": [
            {
                "flat_no": m.flat_no,
                "owner_name": m.owner_name or "",
                "voter_user": m.voter_user or "",
                "voting_weight": f"{Decimal(str(m.voting_weight or 0)).quantize(Decimal('0.001')):.3f}",
                "eligibility_status": m.eligibility_status,
                "exclusion_reason": m.exclusion_reason or "None",
            }
            for m in members
        ],
    }

    content_hash = hashlib.sha256(canonical_json_bytes(canonical_payload)).hexdigest()
    return canonical_payload, content_hash


def approve_electorate(publication_name: str, certified_by: str | None = None, notes: str | None = None) -> dict[str, Any]:
    """Final officer certification. All objections must be resolved. Computes canonical content hash."""
    frappe.only_for(["System Manager", "Society Committee Member"])
    pub = frappe.get_doc("Electorate Publication", publication_name)
    if pub.status not in ("Published", "Objections Closed"):
        frappe.throw(_("Can only approve an electorate in Published or Objections Closed status."))

    # Block approval if any unresolved objections exist
    unresolved_count = frappe.db.count(
        "Electorate Objection",
        {"publication": pub.name, "status": ["in", ["Submitted", "Under Review", "Evidence Requested"]]},
    )
    if unresolved_count > 0:
        frappe.throw(
            _("Cannot approve electorate: {0} objection(s) are still under review or awaiting evidence. "
              "All objections must be Accepted or Rejected before final certification.").format(unresolved_count)
        )

    _canonical_payload, content_hash = compute_electorate_manifest(pub.name)

    pub.status = "Approved"
    pub.electorate_content_hash = content_hash
    pub.approval_certified_by = certified_by or frappe.session.user
    pub.approval_certified_on = now_datetime()
    if notes:
        pub.approval_notes = notes
    pub.save(ignore_permissions=True)

    return {
        "publication": pub.name,
        "status": pub.status,
        "electorate_content_hash": content_hash,
        "approval_certified_by": pub.approval_certified_by,
        "approval_certified_on": pub.approval_certified_on,
    }
