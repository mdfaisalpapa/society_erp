import frappe

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    user = frappe.session.user
    owner_record = frappe.db.get_value("Owners", {"linked_user": user, "active": 1}, ["name", "flat"], as_dict=True)
    
    if not owner_record:
        context.not_a_resident = True
        return context

    flat = owner_record.flat
    context.flat_number = flat
    
    # 1. Fetch Owned Slots using standard Frappe ORM
    slots = frappe.get_all("Parking Slot", filters={"owned_by": flat}, fields=["name", "slot_type"])
    
    if slots:
        slot_names = [s.name for s in slots]
        # 2. Fetch Active Allocations for these slots
        active_allocs = frappe.get_all(
            "Parking Allocation",
            filters={"parking_slot": ("in", slot_names), "status": "Active"},
            fields=["name", "parking_slot", "allocation_type", "occupied_by"]
        )
        
        # 3. Merge data together for the Jinja template
        for slot in slots:
            alloc = next((a for a in active_allocs if a.parking_slot == slot.name), None)
            slot.allocation_name = alloc.name if alloc else "NONE"
            slot.allocation_type = alloc.allocation_type if alloc else "Self-Occupied"
            slot.occupied_by = alloc.occupied_by if alloc else flat
            
    context.slots = slots
