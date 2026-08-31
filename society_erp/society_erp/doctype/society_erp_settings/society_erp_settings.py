import frappe
from frappe.model.document import Document

class SocietyERPSettings(Document):
    pass

@frappe.whitelist()
def create_maintenance_item():
    item_code = "Monthly Maintenance Charge"
    sac_code = "999598" # Standard GST SAC for Society Maintenance
    
    if frappe.db.exists("Item", item_code):
        return item_code
        
    # Safely generate the SAC code if India Compliance hasn't pre-loaded it
    if not frappe.db.exists("GST HSN Code", sac_code):
        frappe.get_doc({
            "doctype": "GST HSN Code",
            "name": sac_code,
            "description": "Services furnished by membership organisations (RWA Maintenance)"
        }).insert(ignore_permissions=True)
        
    # Generate the non-stock service item automatically with GST compliance
    item = frappe.get_doc({
        "doctype": "Item",
        "item_code": item_code,
        "item_name": "Monthly Maintenance Charge",
        "item_group": "Services",
        "is_stock_item": 0,
        "include_item_in_manufacturing": 0,
        "gst_hsn_code": sac_code,
        "description": "Standard monthly maintenance and infrastructure levy."
    })
    item.insert(ignore_permissions=True)
    
    return item.name
