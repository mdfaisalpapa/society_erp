import frappe
from frappe import _
from frappe.utils import getdate, today, add_days

from society_erp.resident_portal import get_verified_owner_records


def _owner_for_flat(flat):
    owners = get_verified_owner_records()
    owner = next((row for row in owners if row.flat == flat), None)
    if not owner:
        frappe.throw(_("You are not authorised to act for this flat."), frappe.PermissionError)
    return owner


def _get_offer(name):
    return frappe.get_doc("Parking Rental Offer", name)


def _lock_offer_for_update(name):
    """Serialize bid submission, selection, and confirmation for one offer."""
    rows = frappe.db.sql(
        "SELECT name FROM `tabParking Rental Offer` WHERE name = %s FOR UPDATE",
        name,
        as_dict=True,
    )
    if not rows:
        frappe.throw(_("Parking rental offer not found."))
    return frappe.get_doc("Parking Rental Offer", name)


def _lock_slot_for_update(slot_name):
    """Serialize offer creation and confirmation for a parking slot."""
    rows = frappe.db.sql(
        "SELECT name FROM `tabParking Slot` WHERE name = %s FOR UPDATE",
        slot_name,
        as_dict=True,
    )
    if not rows:
        frappe.throw(_("Parking slot not found."))
    return rows[0]["name"]


def _slot_owner(slot_name, flat):
    slot = frappe.db.get_value(
        "Parking Slot", slot_name,
        ["name", "slot_number", "slot_type", "ownership_status",
         "owned_by", "currently_occupied_by", "current_status"],
        as_dict=True,
    )
    if not slot:
        frappe.throw(_("Parking slot not found."))
    if slot.slot_type != "Car" or slot.ownership_status != "Stilt":
        frappe.throw(_("Only numbered stilt car parking slots can be offered."))
    if slot.owned_by != flat:
        frappe.throw(_("You can offer only a parking slot allotted to your own flat."),
                     frappe.PermissionError)
    return slot


def _validate_date_range(start_date, end_date):
    start = getdate(start_date)
    end = getdate(end_date) if end_date else None
    if start < getdate(today()):
        frappe.throw(_("The rental start date cannot be in the past."))
    if end and end < start:
        frappe.throw(_("The end date cannot be earlier than the start date."))
    return start, end



def _check_no_overlapping_rental(slot_name, start_date, end_date, exclude=None):
    """Reject overlaps with other active allocations, not historical records."""
    rows = frappe.get_all(
        "Parking Allocation",
        filters={"parking_slot": slot_name, "status": "Active"},
        fields=["name", "start_date", "end_date"],
        limit_page_length=1000,
    )

    start = getdate(start_date)
    end = getdate(end_date) if end_date else None

    for row in rows:
        if exclude and row.name == exclude:
            continue
        if not row.start_date:
            continue

        old_start = getdate(row.start_date)
        old_end = getdate(row.end_date) if row.end_date else None

        overlaps = (
            (end is None or old_start <= end)
            and (old_end is None or old_end >= start)
        )
        if overlaps:
            frappe.throw(
                _("The selected slot already has an active allocation "
                  "overlapping the proposed rental dates.")
            )



@frappe.whitelist()
def get_parking_rental_offers():
    """List open offers with asking rent and highest bid, without bidder identities."""
    owners = get_verified_owner_records()
    flats = sorted({row.flat for row in owners if row.flat})
    offers = frappe.get_all(
        "Parking Rental Offer",
        filters={"status": ["in", ["Open", "Under Selection"]]},
        fields=["name", "parking_slot", "slot_number", "offered_by_flat",
                "asking_monthly_rent", "available_from", "available_until",
                "status", "creation"],
        order_by="creation desc",
        limit_page_length=200,
    )
    result = []
    for offer in offers:
        highest = frappe.db.sql(
            """select max(bid_monthly_rent) from `tabParking Rental Bid`
               where offer = %s and status in ('Submitted', 'Selected - Awaiting Confirmation')""",
            offer.name,
        )[0][0]
        my_bid = frappe.db.get_value(
            "Parking Rental Bid",
            {"offer": offer.name, "bidder_flat": ["in", flats],
             "status": ["in", ["Submitted", "Selected - Awaiting Confirmation"]]},
            ["name", "bid_monthly_rent", "status"],
            as_dict=True,
        )
        result.append({
            **offer,
            "highest_bid": highest,
            "my_bid": my_bid,
            "is_my_offer": offer.offered_by_flat in flats,
        })
    return {"offers": result}


@frappe.whitelist()
def create_parking_rental_offer(flat, parking_slot, asking_monthly_rent,
                                available_from, available_until=None, description=None):
    """Publish an offer for a verified owner's allotted stilt car slot."""
    owner = _owner_for_flat(flat)
    _lock_slot_for_update(parking_slot)
    slot = _slot_owner(parking_slot, owner.flat)
    start, end = _validate_date_range(available_from, available_until)
    if start != getdate(today()):
        frappe.throw(_("Offers must start today in this version."))

    if float(asking_monthly_rent or 0) <= 0:
        frappe.throw(_("Asking monthly rent must be greater than zero."))
    if slot.current_status == "Rented to Neighbor":
        frappe.throw(_("This slot is already rented to a neighbour."))
    if slot.current_status not in ("Self-Occupied", "Available"):
        frappe.throw(_("This slot is not currently available to offer."))

    # Only one live offer per slot. Historical offers are retained.
    if frappe.db.exists("Parking Rental Offer", {
        "parking_slot": parking_slot, "status": ["in", ["Open", "Under Selection"]]
    }):
        frappe.throw(_("There is already an open offer for this parking slot."))

    doc = frappe.get_doc({
        "doctype": "Parking Rental Offer",
        "parking_slot": parking_slot,
        "slot_number": slot.slot_number,
        "offered_by_flat": owner.flat,
        "owner_reference": owner.name,
        "asking_monthly_rent": float(asking_monthly_rent),
        "available_from": str(start),
        "available_until": str(end) if end else None,
        "description": (description or "").strip() or None,
        "status": "Open",
    })
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def submit_parking_rental_bid(offer_name, flat, bid_monthly_rent,
                              proposed_start_date, proposed_end_date=None, remarks=None):
    """Submit/update a resident's bid; other bidders' identities and amounts stay private."""
    bidder = _owner_for_flat(flat)
    # Submission and selection use the same row lock so a bid cannot slip in
    # after the owner has begun selecting a winner.
    offer = _lock_offer_for_update(offer_name)
    if offer.status != "Open":
        frappe.throw(_("This offer is no longer accepting bids."))
    if offer.offered_by_flat == bidder.flat:
        frappe.throw(_("You cannot bid on your own parking offer."))
    start, end = _validate_date_range(proposed_start_date, proposed_end_date)
    if start != getdate(today()):
        frappe.throw(_("Bids must start today in this version."))
    offer_start = getdate(offer.available_from)
    offer_end = getdate(offer.available_until) if offer.available_until else None
    if start < offer_start or (offer_end and (not end or end > offer_end)) or (offer_end and start > offer_end):
        frappe.throw(_("Your proposed dates must fall within the dates offered by the owner."))
    if float(bid_monthly_rent or 0) < float(offer.asking_monthly_rent or 0):
        frappe.throw(_("Your bid must be at least the asking rent."))

    existing = frappe.db.get_value(
        "Parking Rental Bid",
        {"offer": offer.name, "bidder_flat": bidder.flat,
         "status": ["in", ["Submitted", "Selected - Awaiting Confirmation"]]},
        "name",
    )
    if existing:
        doc = frappe.get_doc("Parking Rental Bid", existing)
        doc.bid_monthly_rent = float(bid_monthly_rent)
        doc.proposed_start_date = str(start)
        doc.proposed_end_date = str(end) if end else None
        doc.remarks = (remarks or "").strip() or None
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc({
            "doctype": "Parking Rental Bid",
            "offer": offer.name,
            "bidder_flat": bidder.flat,
            "bidder_reference": bidder.name,
            "bid_monthly_rent": float(bid_monthly_rent),
            "proposed_start_date": str(start),
            "proposed_end_date": str(end) if end else None,
            "remarks": (remarks or "").strip() or None,
            "status": "Submitted",
        })
        doc.insert(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def get_my_parking_rental_bids(offer_name):
    """Return all bids only to the verified owner of the offered slot."""
    offer = _get_offer(offer_name)
    _owner_for_flat(offer.offered_by_flat)
    bids = frappe.get_all(
        "Parking Rental Bid",
        filters={"offer": offer.name},
        fields=["name", "bidder_flat", "bidder_reference", "bid_monthly_rent",
                "proposed_start_date", "proposed_end_date", "remarks", "status", "creation"],
        order_by="bid_monthly_rent desc, creation asc",
        limit_page_length=500,
    )
    return {"offer": offer.name, "bids": bids}


@frappe.whitelist()
def select_parking_rental_bid(offer_name, bid_name):
    """Owner selects one bid; the offer stops accepting bids."""
    # Serialize selection against bid submissions and other selections.
    offer = _lock_offer_for_update(offer_name)
    _owner_for_flat(offer.offered_by_flat)
    if offer.status != "Open":
        frappe.throw(_("This offer is no longer open for selection."))
    bid = frappe.get_doc("Parking Rental Bid", bid_name)
    if bid.offer != offer.name or bid.status != "Submitted":
        frappe.throw(_("This bid cannot be selected."))
    if bid.bidder_flat == offer.offered_by_flat:
        frappe.throw(_("The owner cannot select their own flat as renter."))

    # Close competing bids without deleting their history.
    other_bids = frappe.get_all(
        "Parking Rental Bid",
        filters={"offer": offer.name, "name": ["!=", bid.name], "status": "Submitted"},
        pluck="name",
    )
    for name in other_bids:
        frappe.db.set_value("Parking Rental Bid", name, "status", "Not Selected")
    bid.status = "Selected - Awaiting Confirmation"
    bid.save(ignore_permissions=True)
    offer.status = "Under Selection"
    offer.selected_bid = bid.name
    offer.save(ignore_permissions=True)
    return {"offer": offer.name, "selected_bid": bid.name, "status": bid.status}



@frappe.whitelist()
def confirm_selected_parking_rental_bid(bid_name):
    """Confirm a selected bid and create the rental allocation atomically."""
    owners = get_verified_owner_records()
    owner_by_flat = {row.flat: row for row in owners}

    # Resolve the offer, then lock in a consistent order: offer, bid, slot.
    offer_name = frappe.db.get_value("Parking Rental Bid", bid_name, "offer")
    if not offer_name:
        frappe.throw(_("Parking rental bid not found."))
    offer = _lock_offer_for_update(offer_name)
    locked_bid = frappe.db.sql(
        "SELECT name FROM `tabParking Rental Bid` WHERE name = %s FOR UPDATE",
        bid_name,
        as_dict=True,
    )
    if not locked_bid:
        frappe.throw(_("Parking rental bid not found."))
    bid = frappe.get_doc("Parking Rental Bid", bid_name)
    if bid.offer != offer.name:
        frappe.throw(_("The selected bid no longer belongs to this offer."))
    if (
        bid.bidder_flat not in owner_by_flat
        or bid.bidder_reference != owner_by_flat[bid.bidder_flat].name
    ):
        frappe.throw(
            _("You are not authorised to confirm this bid."),
            frappe.PermissionError,
        )
    if bid.status != "Selected - Awaiting Confirmation":
        frappe.throw(_("This bid is not awaiting confirmation."))

    if offer.status != "Under Selection" or offer.selected_bid != bid.name:
        frappe.throw(_("This offer is no longer awaiting this confirmation."))

    start, end = _validate_date_range(
        bid.proposed_start_date, bid.proposed_end_date
    )
    if start != getdate(today()):
        frappe.throw(_("Rental confirmation must start today in this version."))

    savepoint = "confirm_parking_rental"
    frappe.db.savepoint(savepoint)

    try:
        # Lock the slot row so two confirmations cannot proceed together.
        slot_rows = frappe.db.sql(
            """
            SELECT name, owned_by, ownership_status, current_status
            FROM `tabParking Slot`
            WHERE name = %s
            FOR UPDATE
            """,
            offer.parking_slot,
            as_dict=True,
        )
        if not slot_rows:
            frappe.throw(_("The parking slot no longer exists."))
        slot = slot_rows[0]

        if (
            slot.owned_by != offer.offered_by_flat
            or slot.ownership_status != "Stilt"
            or slot.current_status == "Rented to Neighbor"
        ):
            frappe.throw(_("The parking slot is no longer eligible for rental."))

        current = frappe.get_all(
            "Parking Allocation",
            filters={
                "parking_slot": slot.name,
                "status": "Active",
            },
            fields=[
                "name", "occupied_by", "allocation_type",
                "start_date", "end_date",
            ],
            limit_page_length=20,
        )
        if (
            len(current) != 1
            or current[0].allocation_type != "Self-Occupied"
            or current[0].occupied_by != offer.offered_by_flat
        ):
            frappe.throw(
                _("The slot does not have the expected active "
                  "self-occupation allocation. Please contact the association office.")
            )

        _check_no_overlapping_rental(
            slot.name, start, end, exclude=current[0].name
        )

        # Preserve the owner's allocation as history. If it began today,
        # mark it Cancelled rather than giving it an end date before its start.
        owner_allocation = current[0]
        if getdate(owner_allocation.start_date) < start:
            frappe.db.set_value(
                "Parking Allocation",
                owner_allocation.name,
                {"end_date": add_days(start, -1), "status": "Expired"},
            )
        else:
            frappe.db.set_value(
                "Parking Allocation",
                owner_allocation.name,
                {"status": "Cancelled"},
            )

        allocation = frappe.get_doc({
            "doctype": "Parking Allocation",
            "parking_slot": slot.name,
            "occupied_by": bid.bidder_flat,
            "allocation_type": "Private Neighbor Rental",
            "start_date": str(start),
            "end_date": str(end) if end else None,
            "status": "Active",
            "monthly_rent": bid.bid_monthly_rent,
        })
        allocation.insert(ignore_permissions=True)

        bid.status = "Confirmed"
        bid.save(ignore_permissions=True)

        offer.status = "Closed"
        offer.save(ignore_permissions=True)

        # The allocation controller also synchronises the slot. Set it
        # explicitly here to make the confirmation outcome unambiguous.
        frappe.db.set_value(
            "Parking Slot",
            slot.name,
            {
                "currently_occupied_by": bid.bidder_flat,
                "current_status": "Rented to Neighbor",
            },
        )

        return {
            "offer": offer.name,
            "bid": bid.name,
            "allocation": allocation.name,
            "parking_slot": slot.name,
            "status": "Confirmed",
        }

    except Exception:
        frappe.db.rollback(save_point=savepoint)
        raise





def _expire_one_parking_rental(rental_name, current_date):
    """Expire one due rental and restore the slot safely.

    Returns True when a rental was expired, False when it was no longer due.
    Raises on conflicts or failed restoration so the caller can roll back.
    """
    from society_erp.society_erp.doctype.parking_allocation.parking_allocation import (
        sync_parking_slot,
    )

    current_date = getdate(current_date)

    # Find the slot, then lock it before touching allocations.
    slot_name = frappe.db.get_value(
        "Parking Allocation", rental_name, "parking_slot"
    )
    if not slot_name:
        return False

    slot_rows = frappe.db.sql(
        """
        SELECT name, ownership_status, owned_by
        FROM `tabParking Slot`
        WHERE name = %s
        FOR UPDATE
        """,
        slot_name,
        as_dict=True,
    )
    if not slot_rows:
        raise frappe.ValidationError(
            f"Parking slot {slot_name} does not exist."
        )
    slot = slot_rows[0]

    rental_rows = frappe.db.sql(
        """
        SELECT name, parking_slot, end_date, status, allocation_type
        FROM `tabParking Allocation`
        WHERE name = %s
        FOR UPDATE
        """,
        rental_name,
        as_dict=True,
    )
    if not rental_rows:
        return False

    rental = rental_rows[0]
    if (
        rental.status != "Active"
        or rental.allocation_type != "Private Neighbor Rental"
        or not rental.end_date
        or getdate(rental.end_date) >= current_date
    ):
        return False

    active = frappe.get_all(
        "Parking Allocation",
        filters={
            "parking_slot": slot_name,
            "status": "Active",
            "name": ["!=", rental_name],
            "start_date": ["<=", str(current_date)],
        },
        fields=[
            "name", "occupied_by", "allocation_type",
            "start_date", "end_date",
        ],
        limit_page_length=500,
    )

    effective = [
        allocation for allocation in active
        if not allocation.end_date
        or getdate(allocation.end_date) >= current_date
    ]

    if len(effective) > 1:
        raise frappe.ValidationError(
            f"Multiple effective allocations exist for slot {slot_name}."
        )

    # Expire the rental only after checking the other effective allocations.
    frappe.db.set_value(
        "Parking Allocation", rental_name, "status", "Expired"
    )

    if not effective and slot.ownership_status == "Stilt" and slot.owned_by:
        future = frappe.get_all(
            "Parking Allocation",
            filters={
                "parking_slot": slot_name,
                "status": "Active",
                "start_date": [">", str(current_date)],
                "name": ["!=", rental_name],
            },
            fields=["start_date"],
            order_by="start_date asc",
            limit_page_length=1,
        )

        owner_end = (
            add_days(getdate(future[0].start_date), -1)
            if future else None
        )

        if owner_end and owner_end < current_date:
            raise frappe.ValidationError(
                f"Future allocation conflicts with owner restoration for slot {slot_name}."
            )

        owner_allocation = frappe.get_doc({
            "doctype": "Parking Allocation",
            "parking_slot": slot_name,
            "occupied_by": slot.owned_by,
            "allocation_type": "Self-Occupied",
            "start_date": str(current_date),
            "end_date": str(owner_end) if owner_end else None,
            "status": "Active",
            "monthly_rent": 0,
        })
        owner_allocation.insert(ignore_permissions=True)

    sync_parking_slot(slot_name)
    return True



def expire_due_parking_rentals():
    """Scheduled wrapper to process due private-neighbour rentals."""
    current_date = getdate(today())

    due = frappe.get_all(
        "Parking Allocation",
        filters={
            "allocation_type": "Private Neighbor Rental",
            "status": "Active",
            "end_date": ["<", str(current_date)],
        },
        fields=["name"],
        order_by="end_date asc",
        limit_page_length=1000,
    )

    processed = 0
    errors = 0

    for index, row in enumerate(due):
        savepoint = f"expire_rental_{index}"
        frappe.db.savepoint(savepoint)

        try:
            if _expire_one_parking_rental(row.name, current_date):
                processed += 1
        except Exception:
            frappe.db.rollback(save_point=savepoint)
            errors += 1
            frappe.log_error(
                title=f"Parking rental expiry failed: {row.name}",
                message=frappe.get_traceback(),
            )

    return {
        "processed": processed,
        "errors": errors,
        "due_found": len(due),
    }

