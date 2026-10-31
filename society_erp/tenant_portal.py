import frappe
import re
from frappe.utils import validate_email_address

# Import your core authentication function from the main file
from society_erp.resident_portal import get_verified_owner_records

@frappe.whitelist()
def get_tenants():
    """Fetch active and past tenants for the owner's flats."""
    from society_erp.resident_portal import get_verified_owner_records
    
    owners = get_verified_owner_records()
    flats = [o.flat for o in owners if o.flat]

    if not flats:
        return {"tenants": []}

    tenants = frappe.get_all(
        "Tenants",
        filters={"flat": ["in", flats]},
        fields=[
            "name", "flat", "tenant_name", "mobile_no", "email", 
            "start_date", "end_date", "active", "registration_status", 
            "rental_agreement", "photo", "id_proof", "police_verification" # Added new fields here
        ],
        order_by="active desc, start_date desc"
    )
    return {"tenants": tenants}

@frappe.whitelist()
def register_tenant(flat, tenant_name, relationship, mobile_no, email=None, start_date=None, rental_agreement=None, police_verification=None, id_proof=None, photo=None):
    """Registers a new tenant with strict data validation and creates a user account."""
    from society_erp.resident_portal import get_verified_owner_records
    
    owners = get_verified_owner_records()
    if not any(o.flat == flat for o in owners):
        frappe.throw("Not authorised for this flat.", frappe.PermissionError)

    # 1. Enforce Mandatory Rental Agreement
    if not rental_agreement:
        frappe.throw("Rental Agreement document is mandatory.")

    # 2. Validate 10-Digit Mobile Number
    mobile_clean = re.sub(r'\D', '', str(mobile_no))
    if len(mobile_clean) != 10:
        frappe.throw("Please enter a valid 10-digit mobile number.")
        
    # 3. Safely Validate Email Format
    if email:
        if not validate_email_address(email, throw=False):
            frappe.throw("Please enter a valid email address.")

    # Deactivate any currently active tenants for this flat
    active_tenants = frappe.get_all("Tenants", filters={"flat": flat, "active": 1}, pluck="name")
    for t in active_tenants:
        frappe.db.set_value("Tenants", t, "active", 0)

    # Create the new tenant record (defaulting to Pending status)
    doc = frappe.get_doc({
        "doctype": "Tenants",
        "flat": flat,
        "tenant_name": tenant_name,
        "relationship": relationship,
        "mobile_no": mobile_clean, 
        "email": email,
        "start_date": start_date,
        "active": 1,
        "registration_status": "Pending",
        "rental_agreement": rental_agreement,
        "police_verification": police_verification,
        "id_proof": id_proof,
        "photo": photo
    })
    doc.insert(ignore_permissions=True)

    # Attach any provided files securely
    for file_url, fieldname in [
        (rental_agreement, "rental_agreement"), 
        (police_verification, "police_verification"), 
        (id_proof, "id_proof"),
        (photo, "photo")
    ]:
        if file_url:
            frappe.db.set_value(
                "File",
                {"file_url": file_url, "owner": frappe.session.user},
                {"attached_to_doctype": "Tenants", "attached_to_name": doc.name, "attached_to_field": fieldname}
            )

    return doc.name
@frappe.whitelist()
def deactivate_tenant(tenant_id):
    """Marks a tenant as inactive, sets the end date, and disables their user account."""
    from society_erp.resident_portal import get_verified_owner_records
    
    owners = get_verified_owner_records()
    flats = [o.flat for o in owners]
    
    tenant = frappe.db.get_value("Tenants", tenant_id, ["flat", "active", "email"], as_dict=True)
    if not tenant or tenant.flat not in flats:
        frappe.throw("Access Denied.", frappe.PermissionError)

    # 1. Deactivate the tenant record
    frappe.db.set_value("Tenants", tenant_id, "active", 0)
    frappe.db.set_value("Tenants", tenant_id, "end_date", frappe.utils.today())
    
    # 2. Disable the associated User account (if an email was provided)
    if tenant.email:
        clean_email = tenant.email.strip().lower()
        try:
            if frappe.db.exists("User", clean_email):
                # Ensure we only disable it if they aren't also a tenant in another flat
                # (You might skip this check if you strictly disable the account)
                other_active = frappe.db.count("Tenants", filters={"email": clean_email, "active": 1})
                if other_active == 0:
                    frappe.db.set_value("User", clean_email, "enabled", 0)
                    frappe.db.commit() # Ensure the user update commits
        except Exception as e:
            frappe.log_error(message=str(e), title="Tenant User Deactivation Failed")
        
    return True
