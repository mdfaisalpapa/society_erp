import frappe
import re
from frappe import _
from frappe.utils import cint, flt, get_datetime, getdate, now_datetime
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
        "eligibility_cutoff_date",
        "allow_vote_change",
        "secret_ballot",
        "result_visibility",
        "publish_ballot_register",
        "require_email_otp",
    )

    IMMUTABLE_OPTION_FIELDS = (
        "option_label",
        "description",
        "display_order",
    )

    def validate(self):
        self.validate_poll_immutability()
        self.validate_eligibility_snapshot()

    def validate_eligibility_snapshot(self):
        old = self.get_doc_before_save() if not self.is_new() else None

        # Eligibility cutoff cannot change after the snapshot is created.
        if old and old.eligibility_snapshot_created:
            old_cutoff = (
                getdate(old.eligibility_cutoff_date)
                if old.eligibility_cutoff_date else None
            )
            current_cutoff = (
                getdate(self.eligibility_cutoff_date)
                if self.eligibility_cutoff_date else None
            )
            if old_cutoff != current_cutoff:
                frappe.throw(
                    _("Eligibility Cutoff Date cannot be changed after the snapshot is created.")
                )

        # Every poll must have a complete frozen snapshot before opening.
        if self.status == "Open":
            if not self.eligibility_snapshot_created:
                frappe.throw(
                    _("Generate the eligibility snapshot before opening this poll.")
                )

            if not self.name:
                frappe.throw(_("Save the poll before opening it."))

            snapshot_count = frappe.db.count(
                "Voting Eligibility",
                filters={"poll": self.name},
            )
            expected_count = cint(self.total_eligible_flats)

            if snapshot_count == 0 or snapshot_count != expected_count:
                frappe.throw(
                    _(
                        "Eligibility snapshot is missing or incomplete. "
                        "Expected {0} records but found {1}. "
                        "Investigate the snapshot before opening this poll."
                    ).format(expected_count, snapshot_count)
                )

        # Cutoff date is mandatory when dues enforcement is enabled.
        if (
            self.poll_type in ("Association Voting", "Resident Poll")
            and cint(self.enforce_eligibility)
            and not self.eligibility_cutoff_date
        ):
            frappe.throw(
                _("Eligibility Cutoff Date is required when Enforce Eligibility is enabled.")
            )

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
                if not new_end or get_datetime(new_end) <= get_datetime(old_end) or get_datetime(new_end) <= now_datetime():
                    frappe.throw(_("An open poll may only be extended to a future closing time later than its current closing time."))
        elif old_status in ("Open", "Closed") and old.end_datetime != self.end_datetime:
            frappe.throw(_("The closing time cannot be changed while closing or after closure."))

        # Lock fields on the save that opens the poll as well as every
        # subsequent save while Open or Closed.
        if new_status in ("Open", "Closed") or old_status in ("Open", "Closed"):
            for fieldname in self.IMMUTABLE_FIELDS_AFTER_OPEN:
                current_value = self.get(fieldname)
                old_value = old.get(fieldname)

                if fieldname == "start_datetime":
                    current_value = get_datetime(current_value) if current_value else None
                    old_value = get_datetime(old_value) if old_value else None
                elif fieldname == "eligibility_cutoff_date":
                    current_value = getdate(current_value) if current_value else None
                    old_value = getdate(old_value) if old_value else None

                if current_value != old_value:
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




def _group_by_flat(records):
    grouped = {}
    for row in records:
        grouped.setdefault(row.flat, []).append(row)
    return grouped


def _get_enabled_user(user_name):
    if not user_name or not frappe.db.exists("User", user_name):
        return False

    return bool(frappe.db.get_value("User", user_name, "enabled"))


def _get_maintenance_outstanding_as_of(flat, cutoff_date):
    """Return historical receivable balance for a flat through cutoff_date.

    All outstanding Sales Invoices against a flat are treated as maintenance
    dues. GL Entries are used so payments/adjustments after invoice posting but
    on or before the cutoff date are reflected in the historical balance.
    """
    if not cutoff_date:
        frappe.throw(_("Eligibility cutoff date is required when dues enforcement is enabled."))

    balance = frappe.db.sql(
        """
        SELECT COALESCE(SUM(gle.debit - gle.credit), 0)
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE gle.party_type = 'Customer'
  AND gle.party = %s
  AND gle.posting_date <= %s
  AND gle.docstatus = 1
  AND IFNULL(gle.is_cancelled, 0) = 0
  AND acc.account_type = 'Receivable'
        """,
        (flat, getdate(cutoff_date)),
    )[0][0]
    return flt(balance)


def _natural_flat_key(flat):
    """Natural sort key so TA1-708 sorts before TA1-908."""
    return tuple(int(part) if part.isdigit() else part.lower()
                 for part in re.split(r"(\d+)", str(flat)))


def _build_eligibility_list(poll, only_flat=None):
    """Build one flat-level eligibility row per qualifying flat.

    Flat eligibility/weight is independent of whether a User account exists.
    voter_user is only the current authentication allocation.
    """
    owner_filters = {"active": 1}
    tenant_filters = {"active": 1}
    if only_flat:
        owner_filters["flat"] = only_flat
        tenant_filters["flat"] = only_flat

    owners = frappe.get_all(
        "Owners", filters=owner_filters,
        fields=["name", "flat", "owner_name", "linked_user", "is_aoa_member"],
    )
    tenants = frappe.get_all(
        "Tenants", filters=tenant_filters,
        fields=["name", "flat", "tenant_name", "linked_user"],
    )
    owners_by_flat = _group_by_flat(owners)
    tenants_by_flat = _group_by_flat(tenants)

    entries, pending, excluded, data_issues = [], [], [], []
    duplicate_flats = set()

    for flat, rows in owners_by_flat.items():
        if len(rows) > 1:
            duplicate_flats.add(flat)
            data_issues.append({"flat": flat, "reason": f"{len(rows)} active Owner records found"})
    if poll.poll_type == "Resident Poll":
        for flat, rows in tenants_by_flat.items():
            if len(rows) > 1:
                duplicate_flats.add(flat)
                data_issues.append({"flat": flat, "reason": f"{len(rows)} active Tenant records found"})

    candidate_flats = set(owners_by_flat)
    if poll.poll_type == "Resident Poll":
        candidate_flats |= set(tenants_by_flat)
        let_out_filters = {"custom_let_out_for_rent": 1, "disabled": 0}
        if only_flat:
            let_out_filters["name"] = only_flat
        candidate_flats.update(frappe.get_all("Customer", filters=let_out_filters, pluck="name"))

    for flat in sorted(candidate_flats, key=_natural_flat_key):
        if flat in duplicate_flats:
            continue
        flat_data = frappe.db.get_value(
            "Customer", flat,
            ["custom_block", "custom_uds", "custom_let_out_for_rent", "disabled"],
            as_dict=True,
        )
        if not flat_data:
            data_issues.append({"flat": flat, "reason": "Customer record not found"})
            continue
        if flat_data.disabled:
            excluded.append({"flat": flat, "reason": "Customer is disabled"})
            continue

        owner = owners_by_flat.get(flat, [])
        tenant = tenants_by_flat.get(flat, [])
        voter = None
        voter_type = None

        if poll.poll_type == "Association Voting":
            if not owner:
                excluded.append({"flat": flat, "reason": "No active Owner"})
                continue
            voter, voter_type = owner[0].linked_user, "Owner"
        elif poll.poll_type == "Committee Voting":
            if not owner:
                excluded.append({"flat": flat, "reason": "No active Owner"})
                continue
            if not cint(owner[0].is_aoa_member):
                excluded.append({"flat": flat, "reason": "Owner is not an AoA member"})
                continue
            voter, voter_type = owner[0].linked_user, "Owner"
        elif poll.poll_type == "Resident Poll":
            if cint(flat_data.custom_let_out_for_rent):
                if not tenant:
                    data_issues.append({"flat": flat, "reason": "Marked let out but no active Tenant is registered"})
                    continue
                voter, voter_type = tenant[0].linked_user, "Tenant"
            elif owner:
                voter, voter_type = owner[0].linked_user, "Owner"
            else:
                excluded.append({"flat": flat, "reason": "No active Owner for a flat not marked let out"})
                continue
        else:
            frappe.throw(_("Invalid Poll Type."))

        if poll.poll_type == "Association Voting":
            weight = flt(flat_data.custom_uds)
            if not flat_data.custom_block:
                data_issues.append({"flat": flat, "reason": "Block is not assigned"})
                continue
            if weight <= 0:
                data_issues.append({"flat": flat, "reason": "UDS is missing or zero"})
                continue
        else:
            weight = 1.0

        if (poll.poll_type in ("Association Voting", "Resident Poll")
                and cint(poll.enforce_eligibility)):
            outstanding = _get_maintenance_outstanding_as_of(flat, poll.eligibility_cutoff_date)
            if outstanding > 0.005:
                excluded.append({
                    "flat": flat,
                    "reason": f"Outstanding maintenance dues as of {poll.eligibility_cutoff_date}: {outstanding:.2f}",
                })
                continue

        entry = {
            "poll": poll.name, "flat": flat, "voter_user": None,
            "voter_type": voter_type, "block": flat_data.custom_block,
            "voting_weight": weight, "eligibility_status": "Eligible",
            "poll_flat_key": f"{poll.name}|{flat}",
        }
        # Keep the flat eligible even if account is absent/disabled. Allocate
        # each enabled User to only one flat after all flat rows are assembled.
        if voter and _get_enabled_user(voter):
            entry["voter_user"] = voter
        else:
            pending.append({
                "flat": flat, "voter_type": voter_type,
                "block": flat_data.custom_block,
                "reason": "No linked enabled User account",
            })
            # Committee turnout denominator is the currently authenticated
            # committee electorate; unlinked members are pending for a future poll.
            if poll.poll_type == "Committee Voting":
                continue
        entries.append(entry)

    # Resolve duplicate User mappings deterministically without deleting
    # flat eligibility. Losing rows remain eligible but unallocated.
    by_user = {}
    for entry in entries:
        if entry.get("voter_user"):
            by_user.setdefault(entry["voter_user"], []).append(entry)
    for user, rows in by_user.items():
        if len(rows) < 2:
            continue
        if poll.poll_type == "Association Voting":
            winner = sorted(rows, key=lambda r: (-flt(r["voting_weight"]), _natural_flat_key(r["flat"])))[0]
        else:
            winner = sorted(rows, key=lambda r: _natural_flat_key(r["flat"]))[0]
        for row in rows:
            if row is winner:
                continue
            row["voter_user"] = None
            pending.append({
                "flat": row["flat"], "voter_type": row["voter_type"],
                "block": row["block"],
                "reason": f"User account {user} is allocated to {winner['flat']}; use a separate account per flat",
            })

    return entries, pending, excluded, data_issues


def _validate_poll_for_eligibility(poll, require_enforcement=False):
    if poll.status not in ("Draft", "Scheduled"):
        frappe.throw(
            _("Eligibility can only be generated for Draft or Scheduled polls.")
        )

    if poll.eligibility_snapshot_created:
        frappe.throw(
            _("An eligibility snapshot has already been generated for this poll.")
        )

    if poll.poll_type not in (
        "Association Voting",
        "Resident Poll",
        "Committee Voting",
    ):
        frappe.throw(_("Invalid Poll Type."))

    # Dues enforcement applies only to Association and Resident polls.
    if (
        poll.poll_type in ("Association Voting", "Resident Poll")
        and cint(poll.enforce_eligibility)
        and not poll.eligibility_cutoff_date
    ):
        frappe.throw(_("Set the Eligibility Cutoff Date before generating the snapshot."))


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
        "eligible_voters": len(entries),
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


@frappe.whitelist(methods=["POST"])
def correct_voter_mapping(poll_name, flat, new_user, reason):
    """Audibly correct the authentication account on a flat's frozen eligibility row."""
    frappe.only_for("System Manager")
    if not all([poll_name, flat, new_user, (reason or "").strip()]):
        frappe.throw(_("Poll, flat, new User and reason are required."))
    poll = frappe.get_doc("Voting Poll", poll_name)
    if poll.status not in ("Draft", "Scheduled", "Open"):
        frappe.throw(_("Voter mapping cannot be changed after the poll is closed."))
    eligibility = frappe.db.get_value(
        "Voting Eligibility",
        {"poll": poll_name, "flat": flat},
        ["name", "voter_user", "eligibility_status"],
        as_dict=True,
    )
    if not eligibility:
        frappe.throw(_("No flat eligibility record exists for this poll and flat."))
    if eligibility.eligibility_status == "Voted" or frappe.db.exists(
        "Voting Participation", {"poll": poll_name, "flat": flat}
    ):
        frappe.throw(_("The flat has already voted; its voter mapping cannot be changed."))
    if new_user and not _get_enabled_user(new_user):
        frappe.throw(_("The selected User account does not exist or is disabled."))
    if new_user and frappe.db.exists(
        "Voting Eligibility",
        {"poll": poll_name, "voter_user": new_user, "eligibility_status": ["in", ["Eligible", "Voted"]], "name": ["!=", eligibility.name]},
    ):
        frappe.throw(_("This User is already allocated to another flat in this poll."))
    old_user = eligibility.voter_user or "(unassigned)"
    frappe.db.set_value("Voting Eligibility", eligibility.name, "voter_user", new_user or None, update_modified=False)
    details = (
        f"Flat: {flat}; previous User: {old_user}; new User: {new_user or '(unassigned)'}; "
        f"reason: {reason.strip()}; performed by: {frappe.session.user}; at: {now_datetime()}"
    )
    frappe.get_doc({
        "doctype": "Comment", "comment_type": "Comment",
        "reference_doctype": "Voting Poll", "reference_name": poll_name,
        "content": f"<b>Voter account mapping corrected</b><br>{frappe.utils.escape_html(details)}",
    }).insert(ignore_permissions=True)
    return {"success": True, "flat": flat, "previous_user": old_user, "new_user": new_user or None}


@frappe.whitelist()
def generate_eligibility(poll_name, preview_only=1):

    frappe.only_for("System Manager")
    preview_only = cint(preview_only)

    if not frappe.db.exists("Voting Poll", poll_name):
        frappe.throw(_("Voting Poll {0} does not exist").format(poll_name))

    poll = frappe.get_doc("Voting Poll", poll_name)
    _validate_poll_for_eligibility(poll)

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

    # Missing accounts and duplicate mappings do not erase flat eligibility.
    # Data-integrity issues still block the snapshot because voter identity
    # cannot be determined safely for those flats.
    if data_issues:
        frappe.throw(
            _("Snapshot not created. Resolve data issues first. Data issues: {0}.")
            .format(len(data_issues))
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
