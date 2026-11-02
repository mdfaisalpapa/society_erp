import frappe
from frappe import _
from frappe.utils import cint, flt
from frappe.model.document import Document


class VotingPoll(Document):
    """Voting Poll controller with server-side post-opening immutability."""

    IMMUTABLE_FIELDS_AFTER_OPEN = (
        "poll_title",
        "description",
        "poll_type",
        "start_datetime",
        "eligibility_notes",
        "enforce_eligibility",
        "allow_vote_change",
        "secret_ballot",
        "result_visibility",
        "publish_ballot_register",
    )

    IMMUTABLE_OPTION_FIELDS = (
        "option_label",
        "description",
        "display_order",
    )

    def validate(self):
        self.validate_poll_immutability()

    def validate_poll_immutability(self):
        if self.is_new():
            return

        old = self.get_doc_before_save()
        if not old:
            return

        old_status = old.status
        new_status = self.status

        # Once Open, a poll may remain Open or transition only to Closed.
        if old_status == "Open" and new_status not in ("Open", "Closed"):
            frappe.throw(
                _("An opened poll can only remain Open or be Closed.")
            )

        # A Closed poll is terminal and cannot be reopened or edited.
        if old_status == "Closed" and new_status != "Closed":
            frappe.throw(
                _("A closed poll cannot be reopened or its status changed.")
            )

        # While Open, the only permitted configuration change is a strictly
        # later end_datetime. The API records the reason and actor in timeline.
        if old_status == "Open" and new_status == "Open":
            old_end = old.end_datetime
            new_end = self.end_datetime
            if old_end != new_end:
                from frappe.utils import get_datetime, now_datetime
                if not new_end or get_datetime(new_end) <= get_datetime(old_end) or get_datetime(new_end) <= now_datetime():
                    frappe.throw(_("An open poll may only be extended to a future closing time later than its current closing time."))
        elif old_status in ("Open", "Closed") and old.end_datetime != self.end_datetime:
            frappe.throw(_("The closing time cannot be changed while closing or after closure."))

        # Lock fields on the save that opens the poll as well as every
        # subsequent save while Open or Closed.
        if new_status in ("Open", "Closed") or old_status in ("Open", "Closed"):
            for fieldname in self.IMMUTABLE_FIELDS_AFTER_OPEN:
                if self.get(fieldname) != old.get(fieldname):
                    frappe.throw(
                        _(
                            "Poll configuration cannot be changed after "
                            "voting has opened: {0}."
                        ).format(fieldname)
                    )

            old_options = [
                {field: row.get(field) for field in self.IMMUTABLE_OPTION_FIELDS}
                for row in old.options
            ]
            new_options = [
                {field: row.get(field) for field in self.IMMUTABLE_OPTION_FIELDS}
                for row in self.options
            ]

            if old_options != new_options:
                frappe.throw(
                    _("Voting options cannot be changed after voting has opened.")
                )


VERIFIED_OWNER_STATUSES = {
    "Verified by Bot",
    "Verified Physically",
    "Verified with CGEWHO Data",
}


def _group_by_flat(records):
    grouped = {}
    for row in records:
        grouped.setdefault(row.flat, []).append(row)
    return grouped


def _get_enabled_user(user_name):
    if not user_name or not frappe.db.exists("User", user_name):
        return False

    return bool(frappe.db.get_value("User", user_name, "enabled"))


def _build_eligibility_list(poll, only_flat=None):
    """Build eligible, pending, excluded and data-issue lists without inserting."""

    owner_filters = {"active": 1}
    tenant_filters = {"active": 1}

    if only_flat:
        owner_filters["flat"] = only_flat
        tenant_filters["flat"] = only_flat

    owners = frappe.get_all(
        "Owners",
        filters=owner_filters,
        fields=[
            "name", "flat", "owner_name",
            "linked_user", "registration_status", "is_aoa_member",
        ],
    )

    tenants = frappe.get_all(
        "Tenants",
        filters=tenant_filters,
        fields=[
            "name", "flat", "tenant_name", "linked_user",
        ],
    )

    owners_by_flat = _group_by_flat(owners)
    tenants_by_flat = _group_by_flat(tenants)

    entries = []
    pending = []
    excluded = []
    data_issues = []

    duplicate_flats = set()

    for flat, rows in owners_by_flat.items():
        if len(rows) > 1:
            duplicate_flats.add(flat)
            data_issues.append({
                "flat": flat,
                "reason": f"{len(rows)} active Owner records found",
            })

    if poll.poll_type == "Resident Poll":
        for flat, rows in tenants_by_flat.items():
            if len(rows) > 1:
                duplicate_flats.add(flat)
                data_issues.append({
                    "flat": flat,
                    "reason": f"{len(rows)} active Tenant records found",
                })

    if poll.poll_type == "Resident Poll":
        candidate_flats = set(owners_by_flat) | set(tenants_by_flat)
    else:
        candidate_flats = set(owners_by_flat)

    # Include flats marked as let out, even when no active Tenant
    # registration exists. These need attention for Resident Polls.
    if poll.poll_type == "Resident Poll":
        let_out_filters = {
            "custom_let_out_for_rent": 1,
            "disabled": 0,
        }
        if only_flat:
            let_out_filters["name"] = only_flat

        let_out_flats = frappe.get_all(
            "Customer",
            filters=let_out_filters,
            pluck="name",
        )
        candidate_flats.update(let_out_flats)

    for flat in sorted(candidate_flats):

        if flat in duplicate_flats:
            continue

        flat_data = frappe.db.get_value(
            "Customer",
            flat,
            [
                "custom_block",
                "custom_uds",
                "custom_let_out_for_rent",
                "disabled",
            ],
            as_dict=True,
        )

        if not flat_data:
            data_issues.append({
                "flat": flat,
                "reason": "Customer record not found",
            })
            continue

        if flat_data.disabled:
            excluded.append({
                "flat": flat,
                "reason": "Customer is disabled",
            })
            continue

        owner = owners_by_flat.get(flat, [])
        tenant = tenants_by_flat.get(flat, [])

        voter = None
        voter_type = None

        if poll.poll_type == "Association Voting":

            if not owner:
                excluded.append({
                    "flat": flat,
                    "reason": "No active Owner",
                })
                continue

            selected_owner = owner[0]

            if selected_owner.registration_status not in VERIFIED_OWNER_STATUSES:
                excluded.append({
                    "flat": flat,
                    "reason": "Owner is not verified",
                })
                continue

            voter = selected_owner.linked_user
            voter_type = "Owner"

        elif poll.poll_type == "Committee Voting":

            if not owner:
                excluded.append({
                    "flat": flat,
                    "reason": "No active Owner",
                })
                continue

            selected_owner = owner[0]

            if not cint(selected_owner.is_aoa_member):
                excluded.append({
                    "flat": flat,
                    "reason": "Owner is not an AoA member",
                })
                continue

            if selected_owner.registration_status not in VERIFIED_OWNER_STATUSES:
                excluded.append({
                    "flat": flat,
                    "reason": "Owner is not verified",
                })
                continue

            voter = selected_owner.linked_user
            voter_type = "Owner"

        elif poll.poll_type == "Resident Poll":

            # An active Tenant takes precedence over the Owner.
            if tenant:
                voter = tenant[0].linked_user
                voter_type = "Tenant"

            elif cint(flat_data.custom_let_out_for_rent):
                data_issues.append({
                    "flat": flat,
                    "reason": "Marked let out but no active Tenant is registered",
                })
                continue

            elif owner:
                voter = owner[0].linked_user
                voter_type = "Owner"

            else:
                excluded.append({
                    "flat": flat,
                    "reason": "No active Owner or Tenant",
                })
                continue

        else:
            frappe.throw(_("Invalid Poll Type."))

        # Missing or unusable accounts are pending, not fatal preview errors.
        if not voter:
            pending.append({
                "flat": flat,
                "voter_type": voter_type,
                "block": flat_data.custom_block,
                "reason": f"{voter_type} has no linked User account",
            })
            continue

        if not _get_enabled_user(voter):
            pending.append({
                "flat": flat,
                "voter_type": voter_type,
                "block": flat_data.custom_block,
                "reason": "Linked User account is missing or disabled",
            })
            continue

        if poll.poll_type == "Association Voting":

            weight = flt(flat_data.custom_uds)

            if not flat_data.custom_block:
                data_issues.append({
                    "flat": flat,
                    "reason": "Block is not assigned",
                })
                continue

            if weight <= 0:
                data_issues.append({
                    "flat": flat,
                    "reason": "UDS is missing or zero",
                })
                continue

        else:
            weight = 1.0

        entries.append({
            "poll": poll.name,
            "flat": flat,
            "voter_user": voter,
            "voter_type": voter_type,
            "block": flat_data.custom_block,
            "voting_weight": weight,
            "eligibility_status": "Eligible",
            "poll_flat_key": f"{poll.name}|{flat}",
        })

    return entries, pending, excluded, data_issues


def _validate_poll_for_eligibility(poll, require_enforcement=True):
    if poll.status not in ("Draft", "Scheduled"):
        frappe.throw(
            _("Eligibility can only be generated for Draft or Scheduled polls.")
        )

    if poll.eligibility_snapshot_created:
        frappe.throw(
            _("An eligibility snapshot has already been generated for this poll.")
        )

    if require_enforcement and not poll.enforce_eligibility:
        frappe.throw(
        _("Eligibility snapshots are disabled for this poll. Enable Enforce Eligibility to generate one.")
    )

    if poll.poll_type not in (
        "Association Voting",
        "Resident Poll",
        "Committee Voting",
    ):
        frappe.throw(_("Invalid Poll Type."))


def _make_preview_result(poll, entries, pending, excluded, data_issues):
    total_uds = (
        sum(entry["voting_weight"] for entry in entries)
        if poll.poll_type == "Association Voting"
        else 0
    )

    return {
        "preview": True,
        "poll": poll.name,
        "poll_type": poll.poll_type,
        "eligible_flats": len(entries),
        "total_eligible_uds": total_uds,
        "pending_account_setup_flats": len(pending),
        "pending_account_setup_details": pending,
        "data_issue_flats": len(data_issues),
        "data_issue_details": data_issues,
        "excluded_flats": len(excluded),
        "excluded_details": excluded,
        "eligible_details": [
            {
                "flat": entry["flat"],
                "voter_type": entry["voter_type"],
                "block": entry["block"],
                "voting_weight": entry["voting_weight"],
            }
            for entry in entries
        ],
    }


@frappe.whitelist()
def generate_eligibility(poll_name, preview_only=1):

    frappe.only_for("System Manager")
    preview_only = cint(preview_only)

    if not frappe.db.exists("Voting Poll", poll_name):
        frappe.throw(_("Voting Poll {0} does not exist").format(poll_name))

    poll = frappe.get_doc("Voting Poll", poll_name)
    _validate_poll_for_eligibility(poll, require_enforcement=not preview_only)

    existing = frappe.get_all(
        "Voting Eligibility",
        filters={"poll": poll_name},
        pluck="name",
        limit_page_length=1,
    )

    if existing:
        frappe.throw(
            _("Eligibility records already exist for this poll. "
              "Please investigate before proceeding.")
        )

    entries, pending, excluded, data_issues = _build_eligibility_list(poll)

    result = _make_preview_result(
        poll, entries, pending, excluded, data_issues
    )

    if preview_only:
        return result

    # Lock the poll before creating the snapshot.
    frappe.db.sql(
        """
        SELECT name
        FROM `tabVoting Poll`
        WHERE name = %s
        FOR UPDATE
        """,
        poll_name,
    )

    poll.reload()
    _validate_poll_for_eligibility(poll)

    if frappe.db.exists("Voting Eligibility", {"poll": poll_name}):
        frappe.throw(
            _("Eligibility records already exist for this poll.")
        )

    # Rebuild after locking so the snapshot uses the latest source data.
    entries, pending, excluded, data_issues = _build_eligibility_list(poll)

    result = _make_preview_result(
        poll, entries, pending, excluded, data_issues
    )

    if pending or data_issues:
        frappe.throw(
            _(
                "Snapshot not created. Resolve all pending account setup "
                "and data issues first. Pending accounts: {0}; "
                "Data issues: {1}."
            ).format(len(pending), len(data_issues))
        )

    if not entries:
        frappe.throw(_("No eligible voters were found."))

    for entry in entries:
        doc = frappe.get_doc({
            "doctype": "Voting Eligibility",
            **entry,
        })
        doc.insert(ignore_permissions=True)

    total_uds = (
        sum(entry["voting_weight"] for entry in entries)
        if poll.poll_type == "Association Voting"
        else 0
    )

    poll.eligibility_snapshot_created = 1
    poll.total_eligible_flats = len(entries)
    poll.total_eligible_uds = total_uds
    poll.save(ignore_permissions=True)

    result["preview"] = False
    result["created"] = len(entries)

    return result
