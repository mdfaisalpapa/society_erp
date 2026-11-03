
import hashlib
import json
import re
import secrets
import time

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime


def _ballot_hash(poll_name, receipt_code, selected_option, option_label, weight, cast_time):
    """Hash only the anonymous ballot details, never voter or flat identity."""
    payload = {
        "poll": poll_name,
        "receipt_code": receipt_code,
        "selected_option": selected_option,
        "option_label": option_label,
        "voting_weight": f"{float(weight):.3f}",
        "cast_on": str(cast_time),
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# -----------------------------------------------------------------------------
# Email OTP for optional poll-level step-up verification
# -----------------------------------------------------------------------------

_OTP_TTL_SECONDS = 300
_OTP_RESEND_SECONDS = 60
_OTP_MAX_ATTEMPTS = 5
_OTP_MAX_SENDS_PER_WINDOW = 5
_OTP_SEND_WINDOW_SECONDS = 900
_OTP_AUTH_TTL_SECONDS = 600


def _otp_cache_key(kind, user, poll_name, flat):
    raw = "\0".join([str(kind), str(user), str(poll_name), str(flat)])
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"society_erp:voting_otp:{digest}"


def _otp_secret():
    secret = frappe.conf.get("encryption_key")
    if not secret:
        frappe.throw(_("The site encryption key is not configured."))
    return str(secret).encode("utf-8")


def _otp_digest(user, poll_name, flat, otp):
    import hmac
    message = "\0".join([str(user), str(poll_name), str(flat), str(otp)])
    return hmac.new(_otp_secret(), message.encode("utf-8"), hashlib.sha256).hexdigest()


def _assert_otp_voting_access(poll_name, flat, user):
    if not frappe.db.exists("Voting Poll", poll_name):
        frappe.throw(_("Voting Poll does not exist."))
    poll = frappe.get_doc("Voting Poll", poll_name)
    now = now_datetime()
    if poll.status != "Open" or now < get_datetime(poll.start_datetime) or now > get_datetime(poll.end_datetime):
        frappe.throw(_("This poll is not currently open for voting."))
    entries = _get_resident_eligible_entries(poll, user)
    if not any(row.get("flat") == flat for row in entries):
        frappe.throw(_("You are not eligible to vote for this flat."), frappe.PermissionError)
    if frappe.db.exists("Voting Participation", {"poll": poll.name, "flat": flat}):
        frappe.throw(_("A vote has already been recorded for this flat."))
    return poll


def _assert_voting_otp_authorization(user, poll_name, flat):
    key = _otp_cache_key("verified", user, poll_name, flat)
    if not frappe.cache().get_value(key):
        frappe.throw(_("Please complete email OTP verification before casting your vote."), frappe.PermissionError)


def _consume_voting_otp_authorization(user, poll_name, flat):
    frappe.cache().delete_value(_otp_cache_key("verified", user, poll_name, flat))


@frappe.whitelist(methods=["POST"])
def send_voting_otp(poll_name, flat):
    """Send a short-lived OTP to the logged-in voter's registered email."""
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Please log in to continue."), frappe.PermissionError)

    poll = _assert_otp_voting_access(poll_name, flat, user)
    if not poll.require_email_otp:
        return {"success": True, "otp_required": False}

    user_data = frappe.db.get_value("User", user, ["email", "enabled"], as_dict=True)
    email = (user_data.email or "").strip() if user_data else ""
    if not email or not user_data.enabled:
        frappe.throw(_("Your account does not have an active registered email address. Contact the Association."))

    cache = frappe.cache()
    cooldown_key = _otp_cache_key("cooldown", user, poll_name, flat)
    if cache.get_value(cooldown_key):
        frappe.throw(_("Please wait before requesting another OTP."))

    count_key = _otp_cache_key("send_count", user, poll_name, flat)
    send_count = int(cache.get_value(count_key) or 0)
    if send_count >= _OTP_MAX_SENDS_PER_WINDOW:
        frappe.throw(_("OTP request limit reached. Please try again later."))

    otp = f"{secrets.randbelow(1_000_000):06d}"
    challenge = {"digest": _otp_digest(user, poll_name, flat, otp), "attempts": 0, "expires_at": time.time() + _OTP_TTL_SECONDS}
    cache.set_value(_otp_cache_key("challenge", user, poll_name, flat), frappe.as_json(challenge), expires_in_sec=_OTP_TTL_SECONDS)
    cache.set_value(cooldown_key, "1", expires_in_sec=_OTP_RESEND_SECONDS)
    cache.set_value(count_key, send_count + 1, expires_in_sec=_OTP_SEND_WINDOW_SECONDS)
    cache.delete_value(_otp_cache_key("verified", user, poll_name, flat))

    frappe.sendmail(
        recipients=[email],
        subject=_("Your voting verification OTP"),
        message=(
            f"<p>Your OTP for <b>{frappe.utils.escape_html(poll.poll_title or poll.name)}</b> "
            f"and flat <b>{frappe.utils.escape_html(flat)}</b> is:</p>"
            f"<p style='font-size:24px;font-weight:bold;letter-spacing:4px'>{otp}</p>"
            f"<p>This OTP expires in 5 minutes. Do not share it with anyone.</p>"
        ),
        delayed=False,
    )
    return {"success": True, "otp_required": True, "message": _("An OTP has been sent to your registered email address.")}


@frappe.whitelist(methods=["POST"])
def verify_voting_otp(poll_name, flat, otp):
    """Verify a one-time email OTP and authorise one vote for this user, poll and flat."""
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Please log in to continue."), frappe.PermissionError)
    poll = _assert_otp_voting_access(poll_name, flat, user)
    if not poll.require_email_otp:
        return {"success": True, "otp_required": False}
    if not re.fullmatch(r"\d{6}", str(otp or "")):
        frappe.throw(_("Enter the six-digit OTP."))

    cache = frappe.cache()
    challenge_key = _otp_cache_key("challenge", user, poll_name, flat)
    raw = cache.get_value(challenge_key)
    if not raw:
        frappe.throw(_("The OTP has expired or was not requested. Please request a new OTP."))
    challenge = json.loads(raw)
    remaining_ttl = int(challenge.get("expires_at", 0) - time.time())
    if remaining_ttl <= 0:
        cache.delete_value(challenge_key)
        frappe.throw(_("The OTP has expired. Please request a new OTP."))
    if int(challenge.get("attempts", 0)) >= _OTP_MAX_ATTEMPTS:
        cache.delete_value(challenge_key)
        frappe.throw(_("Maximum OTP attempts exceeded. Please request a new OTP."))

    import hmac
    expected = challenge.get("digest", "")
    supplied = _otp_digest(user, poll_name, flat, str(otp))
    if not hmac.compare_digest(expected, supplied):
        challenge["attempts"] = int(challenge.get("attempts", 0)) + 1
        if challenge["attempts"] >= _OTP_MAX_ATTEMPTS:
            cache.delete_value(challenge_key)
        else:
            # Preserve the original five-minute expiry across failed attempts.
            cache.set_value(
                challenge_key,
                frappe.as_json(challenge),
                expires_in_sec=max(1, remaining_ttl),
            )
        frappe.throw(_("Incorrect OTP. Please try again."))

    cache.delete_value(challenge_key)
    cache.set_value(_otp_cache_key("verified", user, poll_name, flat), "1", expires_in_sec=_OTP_AUTH_TTL_SECONDS)
    return {"success": True, "message": _("Email verified. You may now cast your vote.")}


def _receipt_response(poll, flat, ballot, recovered=False):
    option_label = frappe.db.get_value("Voting Option", ballot.selected_option, "option_label") or ballot.selected_option
    return {
        "success": True,
        "recovered": recovered,
        "message": _("Your previously recorded vote was recovered.") if recovered else _("Your vote has been recorded."),
        "poll_name": poll.name,
        "poll_title": poll.poll_title or poll.name,
        "flat": flat,
        "selected_option": ballot.selected_option,
        "selected_option_label": option_label,
        "voting_weight": ballot.voting_weight,
        "receipt_code": ballot.receipt_code,
        "ballot_hash": ballot.ballot_hash,
        "cast_on": ballot.cast_on,
    }


@frappe.whitelist(methods=["POST"])
def cast_vote(poll_name, flat, selected_option, idempotency_key):
    """Cast one vote per flat and safely recover a lost vote response."""

    user = frappe.session.user

    if not user or user == "Guest":
        frappe.throw(_("Please log in to cast your vote."), frappe.PermissionError)

    if not poll_name or not flat or not selected_option or not idempotency_key:
        frappe.throw(
            _("Poll, flat, selected option and idempotency key are required.")
        )

    # Accept a high-entropy URL-safe key, including crypto.randomUUID().
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", idempotency_key):
        frappe.throw(_("Invalid idempotency key."))

    # Scope the key to this poll and flat. The same browser key can safely
    # be reused for another flat without colliding with this ballot.
    key_material = "\0".join([poll_name, flat, idempotency_key])
    key_hash = hashlib.sha256(key_material.encode("utf-8")).hexdigest()

    # Serialize all submissions for this poll.
    frappe.db.sql(
        """
        SELECT name
        FROM `tabVoting Poll`
        WHERE name = %s
        FOR UPDATE
        """,
        poll_name,
    )

    if not frappe.db.exists("Voting Poll", poll_name):
        frappe.throw(_("Voting Poll does not exist."))

    poll = frappe.get_doc("Voting Poll", poll_name)

    # ---------------------------------------------------------
    # RETRY / RECEIPT RECOVERY
    # This check deliberately precedes poll status and date
    # checks, so a genuine retry can recover a receipt even
    # after the poll has closed.
    # ---------------------------------------------------------
    existing = frappe.db.get_value(
        "Voting Participation",
        {"poll": poll.name, "flat": flat},
        ["name", "voter_user"],
        as_dict=True,
    )

    if existing:
        # Never reveal a receipt to a different account.
        if existing.voter_user != user:
            frappe.throw(
                _("A vote has already been recorded for this flat.")
            )

        # The raw key is never stored. Only its SHA-256 hash
        # is used to locate the original anonymous ballot.
        ballot = frappe.db.get_value(
            "Voting Ballot",
            {
                "poll": poll.name,
                "idempotency_key_hash": key_hash,
            },
            [
                "name",
                "receipt_code",
                "selected_option",
                "voting_weight",
                "ballot_hash",
                "cast_on",
            ],
            as_dict=True,
        )

        if not ballot:
            frappe.throw(
                _(
                    "A vote already exists, but this request cannot "
                    "recover its receipt. Please contact the election "
                    "administrator."
                )
            )

        # Do not allow a changed request payload to recover a receipt.
        if ballot.selected_option != selected_option:
            frappe.throw(
                _(
                    "This retry does not match the original vote. "
                    "The selected option must remain unchanged."
                )
            )

        return _receipt_response(poll, flat, ballot, recovered=True)

    # Prevent reuse of the same idempotency key for another vote.
    if frappe.db.exists(
        "Voting Ballot",
        {"idempotency_key_hash": key_hash},
    ):
        frappe.throw(_("This idempotency key has already been used."))

    # ---------------------------------------------------------
    # NEW VOTE
    # ---------------------------------------------------------
    if poll.status != "Open":
        frappe.throw(_("This poll is not open for voting."))

    now = now_datetime()

    if now < get_datetime(poll.start_datetime):
        frappe.throw(_("Voting has not started yet."))

    if now > get_datetime(poll.end_datetime):
        frappe.throw(_("The voting period has ended."))

    if poll.poll_type not in (
        "Association Voting",
        "Resident Poll",
        "Committee Voting",
    ):
        frappe.throw(_("Invalid poll type."))

    valid_options = {row.name for row in poll.options}

    if selected_option not in valid_options:
        frappe.throw(
            _("The selected option does not belong to this poll.")
        )

    eligibility_name = None
    if not poll.eligibility_snapshot_created:
        frappe.throw(_("The flat eligibility snapshot has not been generated."))

    eligibility = frappe.db.get_value(
        "Voting Eligibility",
        {"poll": poll.name, "flat": flat, "eligibility_status": "Eligible"},
        ["name", "voter_user", "voter_type", "voting_weight"],
        as_dict=True,
    )
    if not eligibility:
        frappe.throw(_("This flat is not eligible to vote in this poll."))

    if poll.poll_type == "Committee Voting" or (
        poll.poll_type in ("Association Voting", "Resident Poll") and int(poll.enforce_eligibility or 0)
    ):
        if eligibility.voter_user != user:
            frappe.throw(_("You are not allocated to vote for this flat in this poll."), frappe.PermissionError)
        voter_type = eligibility.voter_type
    else:
        live_entries = _get_resident_eligible_entries(poll, user)
        live_entry = next((row for row in live_entries if row.get("flat") == flat), None)
        if not live_entry:
            frappe.throw(_("Your current account is not allocated to vote for this flat."), frappe.PermissionError)
        voter_type = live_entry["voter_type"]

    eligibility_name = eligibility.name
    weight = eligibility.voting_weight

    receipt_code = secrets.token_urlsafe(24)
    cast_time = now_datetime()
    option_label = frappe.db.get_value("Voting Option", selected_option, "option_label") or selected_option
    ballot_hash = _ballot_hash(
        poll.name, receipt_code, selected_option, option_label, weight, cast_time
    )

    if poll.require_email_otp:
        _assert_voting_otp_authorization(user, poll.name, flat)

    participation = frappe.get_doc({
        "doctype": "Voting Participation",
        "poll": poll.name,
        "eligibility": eligibility_name,
        "flat": flat,
        "voter_user": user,
        "voter_type": voter_type,
        "voted_on": cast_time,
    })
    participation.insert(ignore_permissions=True)

    ballot = frappe.get_doc({
        "doctype": "Voting Ballot",
        "poll": poll.name,
        "receipt_code": receipt_code,
        "idempotency_key_hash": key_hash,
        "selected_option": selected_option,
        "voting_weight": weight,
        "cast_on": cast_time,
        "ballot_hash": ballot_hash,
    })
    ballot.insert(ignore_permissions=True)

    if poll.require_email_otp:
        _consume_voting_otp_authorization(user, poll.name, flat)

    if eligibility_name:
        frappe.db.set_value(
            "Voting Eligibility",
            eligibility_name,
            {
                "eligibility_status": "Voted",
                "voted_on": cast_time,
            },
            update_modified=False,
        )

    return _receipt_response(
        poll,
        flat,
        frappe._dict({
            "receipt_code": receipt_code,
            "selected_option": selected_option,
            "voting_weight": weight,
            "ballot_hash": ballot_hash,
            "cast_on": cast_time,
        }),
        recovered=False,
    )



# -----------------------------------------------------------------------------
# Poll administration: early closure, extension and scheduled closure
# -----------------------------------------------------------------------------

def _add_poll_audit_comment(poll, action, details):
    """Add a timeline audit entry for administrative poll actions."""
    content = (
        f"<b>{frappe.utils.escape_html(action)}</b><br>"
        f"{frappe.utils.escape_html(details)}<br>"
        f"Performed by: {frappe.utils.escape_html(frappe.session.user)}<br>"
        f"At: {frappe.utils.escape_html(str(now_datetime()))}"
    )
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Comment",
        "reference_doctype": "Voting Poll",
        "reference_name": poll.name,
        "content": content,
    }).insert(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def end_poll(poll_name, reason=None):
    """Close an open poll immediately. The action is irreversible."""
    frappe.only_for("System Manager")
    if not poll_name:
        frappe.throw(_("Poll is required."))
    frappe.db.sql("SELECT name FROM `tabVoting Poll` WHERE name=%s FOR UPDATE", poll_name)
    poll = frappe.get_doc("Voting Poll", poll_name)
    if poll.status != "Open":
        frappe.throw(_("Only an open poll can be ended."))
    poll.status = "Closed"
    poll.save(ignore_permissions=True)
    _add_poll_audit_comment(poll, "Poll ended early", reason or "No reason supplied")
    return {"success": True, "status": poll.status, "closed_on": now_datetime()}


@frappe.whitelist(methods=["POST"])
def extend_poll(poll_name, new_end_datetime, reason):
    """Extend an open poll; only a later closing time is accepted."""
    frappe.only_for("System Manager")
    if not poll_name or not new_end_datetime or not (reason or "").strip():
        frappe.throw(_("Poll, revised closing time and reason are required."))
    frappe.db.sql("SELECT name FROM `tabVoting Poll` WHERE name=%s FOR UPDATE", poll_name)
    poll = frappe.get_doc("Voting Poll", poll_name)
    if poll.status != "Open":
        frappe.throw(_("Only an open poll can be extended."))
    old_end = get_datetime(poll.end_datetime)
    revised_end = get_datetime(new_end_datetime)
    now = now_datetime()
    if revised_end <= old_end or revised_end <= now:
        frappe.throw(_("The revised closing time must be later than both the current closing time and now."))
    poll.end_datetime = revised_end
    poll.save(ignore_permissions=True)
    _add_poll_audit_comment(
        poll, "Poll closing time extended",
        f"Previous closing time: {old_end}; revised closing time: {revised_end}; reason: {reason.strip()}"
    )
    return {"success": True, "old_end_datetime": old_end, "new_end_datetime": revised_end}


def close_expired_polls():
    """Scheduler task: transition polls whose closing time has passed to Closed."""
    # Internal scheduler method; deliberately not whitelisted.
    now = now_datetime()
    names = frappe.get_all(
        "Voting Poll", filters={"status": "Open", "end_datetime": ["<=", now]},
        pluck="name"
    )
    closed = []
    for name in names:
        frappe.db.sql("SELECT name FROM `tabVoting Poll` WHERE name=%s FOR UPDATE", name)
        poll = frappe.get_doc("Voting Poll", name)
        if poll.status == "Open" and get_datetime(poll.end_datetime) <= now_datetime():
            poll.status = "Closed"
            poll.save(ignore_permissions=True)
            _add_poll_audit_comment(poll, "Poll automatically closed", "Scheduled closing time reached")
            closed.append(name)
    return closed


# -----------------------------------------------------------------------------
# Resident portal read APIs
# -----------------------------------------------------------------------------

def _natural_flat_key(flat):
    return tuple(int(part) if part.isdigit() else part.lower()
                 for part in re.split(r"(\d+)", str(flat)))


def _get_resident_eligible_entries(poll, user):
    """Return this user's eligible flats, using live mapping when dues are not frozen."""
    if not poll.eligibility_snapshot_created:
        return []

    snapshot = frappe.get_all(
        "Voting Eligibility",
        filters={"poll": poll.name, "eligibility_status": ["in", ["Eligible", "Voted"]]},
        fields=["name", "flat", "voter_user", "voter_type", "voting_weight", "eligibility_status"],
    )

    # Committee membership is always a poll-time snapshot. For Association and
    # Resident polls with dues enforcement, both flat eligibility and account
    # mapping are frozen (mapping can be corrected by the audited admin API).
    if poll.poll_type == "Committee Voting" or (
        poll.poll_type in ("Association Voting", "Resident Poll") and int(poll.enforce_eligibility or 0)
    ):
        return [
            row for row in snapshot
            if row.voter_user == user and row.eligibility_status in ("Eligible", "Voted")
        ]

    # With dues enforcement OFF, keep the flat/weight denominator snapshot but
    # resolve the authentication mapping from current active Owner/Tenant data.
    candidates = []
    for row in snapshot:
        flat = row.flat
        if poll.poll_type == "Association Voting":
            records = frappe.get_all(
                "Owners", filters={"flat": flat, "active": 1},
                fields=["linked_user"], limit_page_length=2,
            )
            if len(records) != 1:
                continue
            current_user, voter_type = records[0].linked_user, "Owner"
        elif poll.poll_type == "Resident Poll":
            let_out = frappe.db.get_value("Customer", flat, "custom_let_out_for_rent")
            if let_out:
                records = frappe.get_all(
                    "Tenants", filters={"flat": flat, "active": 1},
                    fields=["linked_user"], limit_page_length=2,
                )
                if len(records) != 1:
                    continue
                current_user, voter_type = records[0].linked_user, "Tenant"
            else:
                records = frappe.get_all(
                    "Owners", filters={"flat": flat, "active": 1},
                    fields=["linked_user"], limit_page_length=2,
                )
                if len(records) != 1:
                    continue
                current_user, voter_type = records[0].linked_user, "Owner"
        else:
            continue
        if not current_user or not frappe.db.exists("User", current_user):
            continue
        if not frappe.db.get_value("User", current_user, "enabled"):
            continue
        candidates.append({
            "name": row.name, "flat": flat, "voter_user": current_user,
            "voter_type": voter_type, "voting_weight": row.voting_weight,
            "eligibility_status": row.eligibility_status,
        })

    by_user = {}
    for row in candidates:
        by_user.setdefault(row["voter_user"], []).append(row)
    allocated = []
    for mapped_user, rows in by_user.items():
        if poll.poll_type == "Association Voting":
            winner = sorted(rows, key=lambda r: (-float(r["voting_weight"] or 0), _natural_flat_key(r["flat"])))[0]
        else:
            winner = sorted(rows, key=lambda r: _natural_flat_key(r["flat"]))[0]
        if mapped_user == user:
            allocated.append(winner)
    return allocated


def _get_public_turnout(poll):
    """Return aggregate turnout only; never return option-wise or voter-level data."""
    if not poll.eligibility_snapshot_created:
        return {"available": False, "reason": "Eligibility snapshot is not available for this poll."}

    eligible_voters = int(poll.total_eligible_flats or 0)
    eligible_weight = (
        float(poll.total_eligible_uds or 0)
        if poll.poll_type == "Association Voting"
        else float(eligible_voters)
    )
    totals = frappe.db.sql(
        """
        SELECT
            (SELECT COUNT(DISTINCT flat) FROM `tabVoting Participation` WHERE poll = %s) AS voters_voted,
            (SELECT COALESCE(SUM(voting_weight), 0) FROM `tabVoting Ballot` WHERE poll = %s) AS weight_voted
        """,
        (poll.name, poll.name), as_dict=True,
    )[0]
    voters_voted = int(totals.voters_voted or 0)
    weight_voted = float(totals.weight_voted or 0)
    result = {
        "available": eligible_voters > 0,
        "voters_voted": voters_voted,
        "eligible_voters": eligible_voters,
        # Compatibility keys retained for the existing resident UI.
        "flats_voted": voters_voted,
        "eligible_flats": eligible_voters,
        "flat_turnout_percentage": round(voters_voted / eligible_voters * 100, 1) if eligible_voters else 0.0,
        "weight_voted": round(weight_voted, 3),
        "eligible_weight": round(eligible_weight, 3),
    }
    if poll.poll_type == "Association Voting":
        result["weight_turnout_percentage"] = round(weight_voted / eligible_weight * 100, 1) if eligible_weight > 0 else 0.0
        result["weight_label"] = "UDS"
    else:
        result["weight_turnout_percentage"] = None
        result["weight_label"] = None
    return result


def _resident_poll_response(poll, user, entries):
    flats = [row["flat"] for row in entries]
    participations = frappe.get_all(
        "Voting Participation",
        filters={
            "poll": poll.name,
            "flat": ["in", flats],
        },
        fields=["flat"],
    )
    voted_flats = {row["flat"] for row in participations}
    options = sorted(
        poll.options,
        key=lambda row: (row.display_order or row.idx, row.idx),
    )

    return {
        "name": poll.name,
        "title": poll.get("poll_title") or poll.name,
        "description": poll.get("description") or "",
        "poll_type": poll.poll_type,
        "start_datetime": poll.start_datetime,
        "end_datetime": poll.end_datetime,
        "status": poll.status,
        "require_email_otp": bool(poll.get("require_email_otp")),
        "turnout": _get_public_turnout(poll),
        "options": [
            {
                "name": option.name,
                "label": option.option_label,
                "description": option.description or "",
                "display_order": option.display_order,
            }
            for option in options
        ],
        "eligible_flats": [
            {
                "flat": row["flat"],
                "voter_type": row["voter_type"],
                "voting_weight": row["voting_weight"],
                "has_voted": row["flat"] in voted_flats,
            }
            for row in entries
        ],
    }


@frappe.whitelist()
def get_resident_polls():
    """List currently open polls for which the logged-in user is eligible."""
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Please log in to view voting polls."), frappe.PermissionError)

    now = now_datetime()
    polls = frappe.get_all(
        "Voting Poll",
        filters={"status": "Open"},
        fields=["name"],
        order_by="start_datetime asc",
    )

    results = []
    for row in polls:
        poll = frappe.get_doc("Voting Poll", row.name)
        if not poll.start_datetime or not poll.end_datetime:
            continue
        if now < get_datetime(poll.start_datetime):
            continue
        if now > get_datetime(poll.end_datetime):
            continue

        entries = _get_resident_eligible_entries(poll, user)
        if not entries:
            continue

        response = _resident_poll_response(poll, user, entries)
        results.append({
            "name": response["name"],
            "title": response["title"],
            "description": response["description"],
            "poll_type": response["poll_type"],
            "start_datetime": response["start_datetime"],
            "end_datetime": response["end_datetime"],
            "eligible_flat_count": (response["turnout"].get("eligible_flats") if response["turnout"].get("available") else None),
            "voted_flat_count": (response["turnout"].get("flats_voted") if response["turnout"].get("available") else None),
            "turnout": response["turnout"],
        })

    return results


@frappe.whitelist()
def get_resident_poll_details(poll_name):
    """Return poll options and only the logged-in user's eligible flats."""
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Please log in to view this poll."), frappe.PermissionError)
    if not poll_name:
        frappe.throw(_("Poll is required."))
    if not frappe.db.exists("Voting Poll", poll_name):
        frappe.throw(_("Voting Poll does not exist."))

    poll = frappe.get_doc("Voting Poll", poll_name)
    if poll.status != "Open":
        frappe.throw(_("This poll is not currently open."))

    now = now_datetime()
    if (
        not poll.start_datetime
        or not poll.end_datetime
        or now < get_datetime(poll.start_datetime)
        or now > get_datetime(poll.end_datetime)
    ):
        frappe.throw(_("This poll is outside its voting period."))

    entries = _get_resident_eligible_entries(poll, user)
    if not entries:
        frappe.throw(
            _("You are not eligible to vote in this poll."),
            frappe.PermissionError,
        )

    return _resident_poll_response(poll, user, entries)


# -----------------------------------------------------------------------------
# Receipt PDF and published anonymous ballot register
# -----------------------------------------------------------------------------

def _get_public_ballot_rows(poll_name):
    ballots = frappe.get_all(
        "Voting Ballot",
        filters={"poll": poll_name},
        fields=["receipt_code", "selected_option", "voting_weight", "ballot_hash"],
        order_by="receipt_code asc",
    )
    rows = []
    for ballot in ballots:
        rows.append({
            "receipt_code": ballot.receipt_code,
            "selected_option": ballot.selected_option,
            "selected_option_label": frappe.db.get_value("Voting Option", ballot.selected_option, "option_label") or ballot.selected_option,
            "voting_weight": float(ballot.voting_weight or 0),
            "ballot_hash": ballot.ballot_hash,
        })
    return rows


def _register_hash(rows):
    canonical = json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@frappe.whitelist()
def publish_ballot_register(poll_name):
    'Freeze the anonymous register hash after a poll is closed.'
    frappe.only_for("System Manager")
    poll = frappe.get_doc("Voting Poll", poll_name)
    if poll.status != "Closed":
        frappe.throw(_("The ballot register can only be published after the poll is closed."))
    if not poll.publish_ballot_register:
        frappe.throw(_("Enable Publish Anonymous Ballot Register on the poll first."))
    if poll.ballot_register_published:
        frappe.throw(_("The ballot register has already been published."))

    rows = _get_public_ballot_rows(poll_name)
    digest = _register_hash(rows)
    poll.ballot_register_hash = digest
    poll.ballot_register_published = 1
    poll.published_on = now_datetime()
    poll.save(ignore_permissions=True)
    return {"success": True, "poll": poll_name, "published_ballots": len(rows), "register_hash": digest}


@frappe.whitelist(allow_guest=True)
def get_published_ballot_register(poll_name):
    'Return the published anonymous register only if its hash still matches.'
    if not frappe.db.exists("Voting Poll", poll_name):
        frappe.throw(_("Voting Poll does not exist."))
    poll = frappe.get_doc("Voting Poll", poll_name)
    if poll.status != "Closed" or not poll.ballot_register_published:
        frappe.throw(_("The ballot register has not been published."))

    rows = _get_public_ballot_rows(poll_name)
    current_hash = _register_hash(rows)
    if not poll.ballot_register_hash or current_hash != poll.ballot_register_hash:
        frappe.throw(_("The published ballot register failed its integrity check. Please contact the election administrator."))

    return {
        "poll": poll.name,
        "poll_title": poll.poll_title,
        "published_on": poll.published_on,
        "ballot_count": len(rows),
        "register_hash": poll.ballot_register_hash,
        "ballots": rows,
    }


@frappe.whitelist(allow_guest=True)
def download_published_ballot_register(poll_name):
    """Download the integrity-checked anonymous ballot register as CSV."""
    data = get_published_ballot_register(poll_name)
    import csv
    from io import StringIO
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Receipt Code", "Selected Option", "Voting Weight", "SHA-256 Ballot Hash"])
    for row in data["ballots"]:
        writer.writerow([row["receipt_code"], row["selected_option_label"], f"{row['voting_weight']:.3f}", row["ballot_hash"]])
    frappe.response["filename"] = f"{poll_name}-published-ballot-register.csv"
    frappe.response["filecontent"] = output.getvalue()
    frappe.response["type"] = "download"


@frappe.whitelist(allow_guest=True)
def get_published_ballot_registers():
    """List published registers for residents without exposing voter identity."""
    polls = frappe.get_all(
        "Voting Poll",
        filters={"status": "Closed", "ballot_register_published": 1},
        fields=["name", "poll_title", "published_on", "ballot_register_hash"],
        order_by="published_on desc",
    )
    results = []
    for poll in polls:
        count = frappe.db.count("Voting Ballot", {"poll": poll.name})
        results.append({
            "name": poll.name, "poll_title": poll.poll_title or poll.name,
            "published_on": poll.published_on, "ballot_count": count,
            "register_hash": poll.ballot_register_hash,
        })
    return results


@frappe.whitelist()
def get_poll_audit_summary(poll_name):
    """System Manager audit summary: turnout, option counts and weighted totals."""
    frappe.only_for("System Manager")
    poll = frappe.get_doc("Voting Poll", poll_name)
    if poll.status != "Closed":
        frappe.throw(_("Audit summary is available only after poll closure."))
    ballots = frappe.get_all(
        "Voting Ballot", filters={"poll": poll.name},
        fields=["selected_option", "voting_weight", "receipt_code", "ballot_hash"]
    )
    participations = frappe.db.count("Voting Participation", {"poll": poll.name})
    option_totals = {}
    for option in poll.options:
        option_totals[option.name] = {
            "option": option.option_label, "votes": 0, "weighted_total": 0.0
        }
    for ballot in ballots:
        row = option_totals.setdefault(ballot.selected_option, {
            "option": frappe.db.get_value("Voting Option", ballot.selected_option, "option_label") or ballot.selected_option,
            "votes": 0, "weighted_total": 0.0
        })
        row["votes"] += 1
        row["weighted_total"] += float(ballot.voting_weight or 0)
    return {
        "poll": poll.name, "poll_title": poll.poll_title, "status": poll.status,
        "participation_count": participations, "ballot_count": len(ballots),
        "participation_ballot_match": participations == len(ballots),
        "option_totals": list(option_totals.values()),
        "published": bool(poll.ballot_register_published),
        "register_hash": poll.ballot_register_hash or None,
    }


@frappe.whitelist(allow_guest=True)
def download_published_ballot_register_pdf(poll_name):
    """Download the verified anonymous ballot register as a PDF."""
    data = get_published_ballot_register(poll_name)
    esc = frappe.utils.escape_html
    rows = []
    for item in data["ballots"]:
        rows.append(
            "<tr>"
            f"<td>{esc(item['receipt_code'])}</td>"
            f"<td>{esc(item['selected_option_label'])}</td>"
            f"<td style='text-align:right'>{float(item['voting_weight']):.3f}</td>"
            f"<td style='font-size:8px;word-break:break-all'>{esc(item['ballot_hash'])}</td>"
            "</tr>"
        )
    html = f"""
    <html><head><style>
      body {{ font-family: sans-serif; font-size: 9px; }}
      h2 {{ text-align:center; }}
      table {{ width:100%; border-collapse:collapse; }}
      th,td {{ border:1px solid #777; padding:5px; vertical-align:top; }}
      th {{ background:#eee; }}
      .hash {{ word-break:break-all; }}
    </style></head><body>
      <h2>Published Anonymous Ballot Register</h2>
      <p><b>Poll:</b> {esc(data['poll'])} &nbsp; <b>Title:</b> {esc(data['poll_title'] or data['poll'])}</p>
      <p><b>Published:</b> {esc(str(data['published_on']))} &nbsp; <b>Ballots:</b> {data['ballot_count']}</p>
      <table><thead><tr><th>Receipt Code</th><th>Selected Option</th><th>Weight</th><th>SHA-256 Ballot Hash</th></tr></thead>
      <tbody>{''.join(rows)}</tbody></table>
      <p><b>Register SHA-256:</b> {esc(data['register_hash'])}</p>
      <p>This register contains no flat number or voter identity. Its integrity was checked before download.</p>
    </body></html>"""
    from frappe.utils.pdf import get_pdf
    frappe.response["filename"] = f"{poll_name}-published-ballot-register.pdf"
    frappe.response["filecontent"] = get_pdf(html)
    frappe.response["type"] = "download"

