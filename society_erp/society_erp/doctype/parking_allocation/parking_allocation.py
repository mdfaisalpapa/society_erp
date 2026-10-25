
import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today


class ParkingAllocation(Document):
    def on_update(self):
        """Synchronise the slot with its effective allocation."""
        if self.parking_slot:
            sync_parking_slot(self.parking_slot)


def sync_parking_slot(slot_name):
    """Set occupant/status from the allocation effective today.

    The original owner remains in Parking Slot.owned_by.
    An expired historical allocation must never overwrite a newer one.
    """
    slot = frappe.db.get_value(
        "Parking Slot",
        slot_name,
        ["name", "ownership_status", "owned_by"],
        as_dict=True,
    )
    if not slot:
        return

    current_date = getdate(today())
    allocations = frappe.get_all(
        "Parking Allocation",
        filters={"parking_slot": slot_name, "status": "Active"},
        fields=[
            "name", "occupied_by", "allocation_type",
            "start_date", "end_date",
        ],
        order_by="start_date desc, creation desc",
        limit_page_length=500,
    )

    effective = []
    for allocation in allocations:
        if not allocation.start_date:
            continue
        start = getdate(allocation.start_date)
        end = getdate(allocation.end_date) if allocation.end_date else None
        if start <= current_date and (end is None or end >= current_date):
            effective.append(allocation)

    if len(effective) > 1:
        frappe.log_error(
            title="Overlapping parking allocations",
            message=(
                f"Slot: {slot_name}\n"
                f"Effective allocations: "
                f"{', '.join(row.name for row in effective)}"
            ),
        )
        # Fail closed: do not silently choose between conflicting occupants.
        return

    if effective:
        allocation = effective[0]
        if allocation.allocation_type == "Self-Occupied":
            status = "Self-Occupied"
        else:
            status = "Rented to Neighbor"

        frappe.db.set_value(
            "Parking Slot",
            slot_name,
            {
                "currently_occupied_by": allocation.occupied_by,
                "current_status": status,
            },
        )
        return

    # Do not assume every slot belongs to an individual resident.
    if slot.ownership_status == "Stilt" and slot.owned_by:
        frappe.db.set_value(
            "Parking Slot",
            slot_name,
            {
                "currently_occupied_by": slot.owned_by,
                "current_status": "Self-Occupied",
            },
        )
    else:
        frappe.db.set_value(
            "Parking Slot",
            slot_name,
            {
                "currently_occupied_by": None,
                "current_status": "Available",
            },
        )
