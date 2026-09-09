import frappe
from frappe.model.document import Document

class ParkingAllocation(Document):
    def on_update(self):
        """Triggered every time a Parking Allocation is saved."""
        if not self.parking_slot:
            return
            
        # Fetch the master slot to check its base ownership type
        slot = frappe.get_doc("Parking Slot", self.parking_slot)
        
        if self.status == "Active":
            # Apply the active rental/allocation to the master slot
            new_status = "Self-Occupied" if self.allocation_type == "Self-Occupied" else "Rented to Neighbor"
            
            frappe.db.set_value("Parking Slot", self.parking_slot, {
                "currently_occupied_by": self.occupied_by,
                "current_status": new_status
            })
            
        elif self.status in ["Expired", "Cancelled"]:
            # Intelligently revert the slot based on who actually owns it
            if slot.ownership_status == "Reserved":
                frappe.db.set_value("Parking Slot", self.parking_slot, {
                    "currently_occupied_by": slot.owned_by,
                    "current_status": "Self-Occupied"
                })
            else:
                # If it's an AOA or Visitor slot, clear it completely
                frappe.db.set_value("Parking Slot", self.parking_slot, {
                    "currently_occupied_by": None,
                    "current_status": "Available" # Ensure "Available" is an option in your Parking Slot DocType
                })
