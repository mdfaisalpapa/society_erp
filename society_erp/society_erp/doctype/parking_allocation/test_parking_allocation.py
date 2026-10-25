
import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from society_erp.society_erp.doctype.parking_allocation.parking_allocation import (
    sync_parking_slot,
)


class IntegrationTestParkingAllocation(IntegrationTestCase):
    def _make_customer(self, suffix):
        customer_group = frappe.db.get_value("Customer Group", {}, "name")
        territory = frappe.db.get_value("Territory", {}, "name")

        self.assertTrue(customer_group, "A Customer Group is required for this test.")
        self.assertTrue(territory, "A Territory is required for this test.")

        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": f"Parking Test {suffix}",
            "customer_type": "Individual",
            "customer_group": customer_group,
            "territory": territory,
        })
        customer.insert(ignore_permissions=True)
        return customer.name

    def _make_slot(self, owner):
        slot = frappe.get_doc({
            "doctype": "Parking Slot",
            "slot_number": f"TEST-{frappe.generate_hash(length=8)}",
            "slot_type": "Car",
            "ownership_status": "Stilt",
            "owned_by": owner,
            "currently_occupied_by": owner,
            "current_status": "Self-Occupied",
        })
        slot.insert(ignore_permissions=True)
        return slot

    def _make_allocation(
        self, slot, occupant, allocation_type="Self-Occupied",
        start_date=None, end_date=None, status="Active"
    ):
        allocation = frappe.get_doc({
            "doctype": "Parking Allocation",
            "parking_slot": slot.name,
            "occupied_by": occupant,
            "allocation_type": allocation_type,
            "start_date": str(start_date or today()),
            "end_date": str(end_date) if end_date else None,
            "status": status,
            "monthly_rent": 0,
        })
        allocation.insert(ignore_permissions=True)
        return allocation

    def test_active_self_allocation_sets_owner_as_occupant(self):
        owner = self._make_customer("Owner")
        slot = self._make_slot(owner)
        self._make_allocation(slot, owner)

        sync_parking_slot(slot.name)

        self.assertEqual(
            frappe.db.get_value(
                "Parking Slot", slot.name, "currently_occupied_by"
            ),
            owner,
        )
        self.assertEqual(
            frappe.db.get_value("Parking Slot", slot.name, "current_status"),
            "Self-Occupied",
        )

    def test_active_private_rental_sets_renter_as_occupant(self):
        owner = self._make_customer("Rental Owner")
        renter = self._make_customer("Renter")
        slot = self._make_slot(owner)

        # Give the owner allocation a historical end date before creating
        # the renter allocation.
        owner_allocation = self._make_allocation(slot, owner)
        frappe.db.set_value(
            "Parking Allocation",
            owner_allocation.name,
            {
                "status": "Expired",
                "end_date": str(add_days(today(), -1)),
            },
        )

        self._make_allocation(
            slot,
            renter,
            allocation_type="Private Neighbor Rental",
        )
        sync_parking_slot(slot.name)

        self.assertEqual(
            frappe.db.get_value(
                "Parking Slot", slot.name, "currently_occupied_by"
            ),
            renter,
        )
        self.assertEqual(
            frappe.db.get_value("Parking Slot", slot.name, "current_status"),
            "Rented to Neighbor",
        )

    def test_historical_allocation_does_not_overwrite_current_occupant(self):
        owner = self._make_customer("History Owner")
        renter = self._make_customer("History Renter")
        slot = self._make_slot(owner)

        historical = self._make_allocation(
            slot,
            owner,
            start_date=add_days(today(), -30),
            end_date=add_days(today(), -1),
            status="Expired",
        )
        current = self._make_allocation(
            slot,
            renter,
            allocation_type="Private Neighbor Rental",
            start_date=today(),
        )

        sync_parking_slot(slot.name)

        self.assertEqual(
            frappe.db.get_value(
                "Parking Slot", slot.name, "currently_occupied_by"
            ),
            renter,
        )
        self.assertEqual(
            frappe.db.get_value("Parking Allocation", historical.name, "status"),
            "Expired",
        )
        self.assertEqual(
            frappe.db.get_value("Parking Allocation", current.name, "status"),
            "Active",
        )

    def test_expiry_bounds_owner_allocation_before_future_allocation(self):
        from society_erp.parking_rental import _expire_one_parking_rental

        owner = self._make_customer("Future Owner")
        renter = self._make_customer("Future Renter")
        next_renter = self._make_customer("Next Renter")
        slot = self._make_slot(owner)

        self._make_allocation(
            slot,
            owner,
            start_date=add_days(today(), -30),
            end_date=add_days(today(), -11),
            status="Expired",
        )
        rental = self._make_allocation(
            slot,
            renter,
            allocation_type="Private Neighbor Rental",
            start_date=add_days(today(), -10),
            end_date=add_days(today(), -1),
            status="Active",
        )
        future = self._make_allocation(
            slot,
            next_renter,
            allocation_type="Private Neighbor Rental",
            start_date=add_days(today(), 5),
            end_date=add_days(today(), 10),
            status="Active",
        )

        self.assertTrue(_expire_one_parking_rental(rental.name, getdate(today())))

        owner_rows = frappe.get_all(
            "Parking Allocation",
            filters={
                "parking_slot": slot.name,
                "occupied_by": owner,
                "allocation_type": "Self-Occupied",
                "status": "Active",
                "start_date": str(getdate(today())),
            },
            fields=["name", "end_date"],
        )
        self.assertEqual(len(owner_rows), 1)
        self.assertEqual(
            getdate(owner_rows[0].end_date),
            getdate(add_days(future.start_date, -1)),
        )
        self.assertEqual(
            frappe.db.get_value("Parking Allocation", future.name, "status"),
            "Active",
        )

    def test_expiry_restores_owner_occupancy(self):
        from society_erp.parking_rental import _expire_one_parking_rental

        owner = self._make_customer("Expiry Owner")
        renter = self._make_customer("Expiry Renter")
        slot = self._make_slot(owner)

        old_owner_allocation = self._make_allocation(
            slot,
            owner,
            allocation_type="Self-Occupied",
            start_date=add_days(today(), -30),
            end_date=add_days(today(), -11),
            status="Expired",
        )

        rental = self._make_allocation(
            slot,
            renter,
            allocation_type="Private Neighbor Rental",
            start_date=add_days(today(), -10),
            end_date=add_days(today(), -1),
            status="Active",
        )

        processed = _expire_one_parking_rental(rental.name, getdate(today()))

        self.assertTrue(processed)
        self.assertEqual(
            frappe.db.get_value("Parking Allocation", rental.name, "status"),
            "Expired",
        )
        self.assertEqual(
            frappe.db.get_value("Parking Allocation", old_owner_allocation.name, "status"),
            "Expired",
        )

        slot.reload()
        self.assertEqual(slot.currently_occupied_by, owner)
        self.assertEqual(slot.current_status, "Self-Occupied")

        restored = frappe.get_all(
            "Parking Allocation",
            filters={
                "parking_slot": slot.name,
                "occupied_by": owner,
                "allocation_type": "Self-Occupied",
                "status": "Active",
                "start_date": str(getdate(today())),
            },
            fields=["name"],
        )
        self.assertEqual(len(restored), 1)
