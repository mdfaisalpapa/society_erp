import frappe
from society_erp.resident_portal import get_verified_owner_records

@frappe.whitelist()
def get_vehicles():
    """List vehicles associated with the logged-in owner's verified flats."""

    owners = get_verified_owner_records()
    owner_names = [o.name for o in owners]
    flats = sorted({o.flat for o in owners if o.flat})

    if not flats:
        return {"vehicles": []}

    vehicles = frappe.get_all(
        "Resident Vehicle",
        filters={
            "flat": ["in", flats],
            "owner_reference": ["in", owner_names],
        },
        fields=[
            "name",
            "flat",
            "vehicle_type",
            "registration_number",
            "registered_owner_name",
            "relationship_to_resident",
            "make",
            "model",
            "color",
            "is_electric",
            "active",
            "approval_status",
        ],
        order_by="creation desc",
        limit_page_length=100,
    )

    return {"vehicles": vehicles}



@frappe.whitelist()
def get_vehicle_form_options(vehicle_type=None, make=None):
    """Return makes for a vehicle type and models for a selected make."""

    get_verified_owner_records()

    vehicle_types = ["Car", "Bike"]

    if vehicle_type and vehicle_type not in vehicle_types:
        frappe.throw("Invalid vehicle type.")

    makes = []
    models = []

    if vehicle_type:
        makes = frappe.get_all(
            "Resident Vehicle Make",
            filters={"vehicle_type": vehicle_type},
            fields=["name", "make_name"],
            order_by="make_name asc",
            limit_page_length=500,
        )

    if make:
        make_doc = frappe.db.get_value(
            "Resident Vehicle Make",
            make,
            ["name", "vehicle_type"],
            as_dict=True,
        )

        if not make_doc:
            frappe.throw("Invalid vehicle make.")

        if vehicle_type and make_doc.vehicle_type != vehicle_type:
            frappe.throw("The selected make does not match the vehicle type.")

        models = frappe.get_all(
            "Resident Vehicle Model",
            filters={"make": make},
            fields=["name", "model_name"],
            order_by="model_name asc",
            limit_page_length=1000,
        )

    return {
        "vehicle_types": vehicle_types,
        "makes": makes,
        "models": models,
        "colors": [
            "White", "Silver", "Grey", "Black", "Red", "Blue",
            "Brown", "Beige", "Maroon", "Green", "Yellow",
            "Orange", "Other",
        ],
        "relationships": [
            "Self",
            "Family(Residing)",
            "Extended Family",
            "Company / Employer Lease",
            "Rented / Subscription",
        ],
    }




@frappe.whitelist()
def register_vehicle(
    flat,
    vehicle_type,
    registration_number,
    registered_owner_name,
    relationship_to_resident,
    rc_copy=None,
    noc=None,
    make=None,
    model=None,
    color=None,
    is_electric=0,
    remarks=None,
):
    """Register a vehicle with required documents and flat-specific parking."""

    owners = get_verified_owner_records()
    owner = next((o for o in owners if o.flat == flat), None)

    if not owner:
        frappe.throw(
            "You are not authorised to register a vehicle for this flat.",
            frappe.PermissionError,
        )

    vehicle_type = (vehicle_type or "").strip()
    registration_number = (registration_number or "").strip().upper()
    registered_owner_name = (registered_owner_name or "").strip()
    relationship_to_resident = (relationship_to_resident or "").strip()

    if vehicle_type not in ("Car", "Bike"):
        frappe.throw("Select a valid vehicle type.")

    vehicle_limits = {"Car": 1, "Bike": 2}
    existing_count = frappe.db.sql(
        """
        SELECT COUNT(*) AS total
        FROM `tabResident Vehicle`
        WHERE flat = %s
          AND vehicle_type = %s
          AND IFNULL(approval_status, '') != 'Rejected'
        """,
        (owner.flat, vehicle_type),
        as_dict=True,
    )[0].total

    limit = vehicle_limits[vehicle_type]
    if existing_count >= limit:
        frappe.throw(
            f"This flat has reached its limit of {limit} "
            f"{'car' if vehicle_type == 'Car' else 'bikes'}. "
            "Please contact the association office if an existing "
            "registration needs correction."
        )

    if not registration_number or not registered_owner_name:
        frappe.throw("Registration number and registered owner name are required.")

    valid_relationships = (
        "Self",
        "Family(Residing)",
        "Extended Family",
        "Company / Employer Lease",
        "Rented / Subscription",
    )
    if relationship_to_resident not in valid_relationships:
        frappe.throw("Select a valid relationship to the resident.")

    if frappe.db.exists(
        "Resident Vehicle", {"registration_number": registration_number}
    ):
        frappe.throw(
            "This vehicle registration number is already recorded. "
            "Please contact the association office if it needs correction."
        )

    # RC is mandatory for every vehicle.
    if not rc_copy:
        frappe.throw("Please upload the vehicle RC copy.")

    # NOC is required when the vehicle is not owned by the resident
    # or a family member residing in the flat.
    noc_required = relationship_to_resident not in (
        "Self",
        "Family(Residing)",
    )
    if noc_required and not noc:
        frappe.throw(
            "Please upload the owner's NOC for this vehicle."
        )

    # Only accept private files uploaded by the current user.
    def validate_uploaded_file(file_url, label):
        if not file_url:
            return

        file_record = frappe.db.get_value(
            "File",
            {
                "file_url": file_url,
                "owner": frappe.session.user,
                "is_private": 1,
            },
            ["name", "file_url"],
            as_dict=True,
        )
        if not file_record:
            frappe.throw(
                f"The uploaded {label} could not be verified. "
                "Please upload it again."
            )

    validate_uploaded_file(rc_copy, "RC copy")
    if noc_required:
        validate_uploaded_file(noc, "NOC")

    # Validate make against vehicle type.
    if make:
        make_doc = frappe.db.get_value(
            "Resident Vehicle Make",
            make,
            ["name", "vehicle_type"],
            as_dict=True,
        )
        if not make_doc or make_doc.vehicle_type != vehicle_type:
            frappe.throw("The selected make does not match the vehicle type.")

    # Validate model against make.
    if model:
        model_doc = frappe.db.get_value(
            "Resident Vehicle Model",
            model,
            ["name", "make"],
            as_dict=True,
        )
        if not model_doc or not make or model_doc.make != make:
            frappe.throw("The selected model does not belong to the selected make.")

    valid_colors = (
        "White", "Silver", "Grey", "Black", "Red", "Blue",
        "Brown", "Beige", "Maroon", "Green", "Yellow",
        "Orange", "Other",
    )
    if color and color not in valid_colors:
        frappe.throw("Select a valid vehicle colour.")

    # Automatically link the flat's designated car slot.
    # Do not alter the existing parking slot's occupancy status.
# Automatically link the flat's designated car slot.
    # Do not alter the existing parking slot's occupancy status.
    parking_slot = None
    if vehicle_type == "Car":
        slots = frappe.get_all(
            "Parking Slot",
            filters={
                "owned_by": owner.flat,
                "slot_type": "Car",
            },
            fields=["name"],
            limit_page_length=3,
        )

        if len(slots) > 1:
            frappe.throw(
                "Multiple designated car parking slots found for this flat. "
                "Please contact the association office to clarify your allocation."
            )
        elif len(slots) == 1:
            parking_slot = slots[0].name
        else:
            # Fallback to Open Parking if no reserved slot is owned
            parking_slot = ""
            open_parking_msg = "Assigned to Open Parking (Unreserved)"
            remarks = open_parking_msg if not remarks else f"{remarks} - {open_parking_msg}"
    doc = frappe.get_doc({
        "doctype": "Resident Vehicle",
        "flat": owner.flat,
        "owner_reference": owner.name if owner.resident_type == "Owner" else None,
        "tenant_reference": owner.name if owner.resident_type == "Tenant" else None,
        "belongs_to": owner.resident_type,
        "vehicle_type": vehicle_type,
        "registration_number": registration_number,
        "registered_owner_name": registered_owner_name,
        "relationship_to_resident": relationship_to_resident,
        "make": make or None,
        "model": model or None,
        "color": color or None,
        "is_electric": (
            1 if str(is_electric).lower() in ("1", "true", "yes") else 0
        ),
        "remarks": remarks or None,
        "rc_copy": rc_copy,
        "noc": noc if noc_required else None,
        "parking_slot": parking_slot,
        "active": 0,
        "approval_status": "Pending",
    })

    doc.insert(ignore_permissions=True)

    # Attach the private uploaded files to the newly created vehicle.
    for file_url, fieldname in (
        (rc_copy, "rc_copy"),
        (noc if noc_required else None, "noc"),
    ):
        if file_url:
            frappe.db.set_value(
                "File",
                {"file_url": file_url, "owner": frappe.session.user},
                {
                    "attached_to_doctype": "Resident Vehicle",
                    "attached_to_name": doc.name,
                    "attached_to_field": fieldname,
                },
            )

    return {
        "name": doc.name,
        "approval_status": doc.approval_status,
        "parking_slot": parking_slot,
    }

# Add this to: society_erp/api/resident_portal.py

@frappe.whitelist()
def reallocate_parking_slot(slot_id, old_alloc_name, new_type, occupant, start_date, end_date=None):
    """Closes the old allocation and creates a new one to preserve history."""
    user = frappe.session.user
    # Ensure the user actually owns the flat/slot
    owner_flat = frappe.db.get_value("Owners", {"linked_user": user, "active": 1}, "flat")
    if not owner_flat:
        frappe.throw("Access Denied.")
        
    # 1. Close Old Allocation
    if old_alloc_name and old_alloc_name != "NONE":
        frappe.db.set_value("Parking Allocation", old_alloc_name, {
            "end_date": start_date,
            "status": "Expired"
        })

    # 2. Create New Allocation
    new_alloc = frappe.get_doc({
        "doctype": "Parking Allocation",
        "parking_slot": slot_id,
        "occupied_by": occupant.strip().upper(),
        "allocation_type": new_type,
        "start_date": start_date,
        "end_date": end_date or None,
        "status": "Active"
    })
    
    new_alloc.insert(ignore_permissions=True)
    return True

@frappe.whitelist()
def get_parking_history(slot_id):
    """Fetches the ledger of past and current allocations for a slot."""
    return frappe.get_all(
        "Parking Allocation",
        filters={"parking_slot": slot_id},
        fields=["name", "allocation_type", "occupied_by", "start_date", "end_date", "status"],
        order_by="start_date desc"
    )

# Add this to: society_erp/api/resident_portal.py

@frappe.whitelist()
def delete_pending_vehicle(vehicle_id):
    """Deletes a vehicle record ONLY if it belongs to the active user AND is still Pending."""
    user = frappe.session.user
    owner = frappe.db.get_value("Owners", {"linked_user": user, "active": 1}, ["name", "flat"], as_dict=True)
    
    if not owner:
        frappe.throw("Access Denied.")

    vehicle = frappe.db.get_value(
        "Resident Vehicle", 
        {"name": vehicle_id, "flat": owner.flat}, 
        ["name", "approval_status", "parking_slot"], 
        as_dict=True
    )

    if not vehicle:
        frappe.throw("Vehicle not found or you do not have permission to delete it.")

    if vehicle.approval_status != "Pending":
        frappe.throw("Only vehicles pending approval can be deleted. Please contact the Estate Office to disable an approved vehicle.")

    # Execute deletion
    frappe.delete_doc("Resident Vehicle", vehicle.name, ignore_permissions=True)
    return True


@frappe.whitelist()
def disable_active_vehicle(vehicle_id):
    """Deactivates an approved vehicle by changing its status to Inactive."""
    user = frappe.session.user
    owner = frappe.db.get_value("Owners", {"linked_user": user, "active": 1}, ["name", "flat"], as_dict=True)

    if not owner:
        frappe.throw("Access Denied.")

    vehicle = frappe.db.get_value(
        "Resident Vehicle",
        {"name": vehicle_id, "flat": owner.flat},
        ["name", "approval_status"],
        as_dict=True
    )

    if not vehicle:
        frappe.throw("Vehicle not found or you do not have permission to modify it.")

    if vehicle.approval_status != "Approved":
        frappe.throw("Only approved vehicles can be deactivated.")

    # Update the status field directly
    frappe.db.set_value("Resident Vehicle", vehicle.name, "approval_status", "Inactive")
    return True


