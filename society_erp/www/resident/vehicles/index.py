import frappe
from society_erp.resident_portal import get_verified_owner_records
from society_erp.vehicle_portal import get_vehicles, get_vehicle_form_options
def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    try:
        owners = get_verified_owner_records()
        owner = owners[0]
    except frappe.PermissionError:
        context.not_a_resident = True
        return context

    context.flat_number = owner.flat
    context.belongs_to = owner.resident_type  # Changed from "Owner"
    context.reference_id = owner.name

    # Determine assigned Car slot to display as read-only
    slots = frappe.get_all("Parking Slot", filters={"owned_by": owner.flat, "slot_type": "Car"}, fields=["name"])
    context.auto_parking_slot = slots[0].name if slots else "Open Parking (Subject to Availability)"

    # Fetch existing vehicles
    vehicles_data = get_vehicles().get("vehicles", [])
    context.vehicles = vehicles_data
    
# Calculate Eligibility Limits: Only count Pending or Approved vehicles
    valid_statuses = ["Pending", "Approved"]
    car_count = sum(1 for v in vehicles_data if v.vehicle_type == "Car" and v.approval_status in valid_statuses)
    bike_count = sum(1 for v in vehicles_data if v.vehicle_type == "Bike" and v.approval_status in valid_statuses)
    
    context.car_count = car_count
    context.bike_count = bike_count
    context.car_eligible = max(0, 1 - car_count)
    context.bike_eligible = max(0, 2 - bike_count)
    
    context.form_options = get_vehicle_form_options()
    context.all_flats = frappe.get_all("Customer", pluck="name", order_by="name asc")

    # Fetch Parking Slot Ownership Data
    owned_slots = frappe.get_all("Parking Slot", filters={"owned_by": owner.flat}, fields=["name", "slot_type"])
    
    if owned_slots:
        slot_names = [s.name for s in owned_slots]
        active_allocs = frappe.get_all(
            "Parking Allocation",
            filters={"parking_slot": ("in", slot_names), "status": "Active"},
            fields=["name", "parking_slot", "allocation_type", "occupied_by"]
        )
        
        # Directly query the database for slots used by explicitly valid vehicles
        raw_vehicle_slots = frappe.get_all(
            "Resident Vehicle",
            filters={"flat": owner.flat, "approval_status": ("in", valid_statuses)},
            pluck="parking_slot"
        )
        active_vehicle_slots = [s for s in raw_vehicle_slots if s]        
        for slot in owned_slots:
            alloc = next((a for a in active_allocs if a.parking_slot == slot.name), None)
            slot.allocation_name = alloc.name if alloc else "NONE"
            slot.allocation_type = alloc.allocation_type if alloc else "Unallocated"
            slot.occupied_by = alloc.occupied_by if alloc else "None"
            
            # Flag if a vehicle is explicitly parked in this specific slot
            slot.has_active_vehicle = slot.name in active_vehicle_slots
            
    context.owned_slots = owned_slots
# --- STICKER RETURN ENFORCEMENT ---
    # Find any deactivated vehicles where the physical sticker hasn't been returned to the office yet
    # STICKER RETURN ENFORCEMENT (Status-Based)
    # Any vehicle sitting in "Inactive" status is waiting for physical sticker handover
    unreturned_stickers = frappe.get_all(
        "Resident Vehicle",
        filters={
            "flat": owner.flat, 
            "approval_status": "Inactive"
        },
        pluck="registration_number"
    )
    context.unreturned_stickers = unreturned_stickers
    
    return context
