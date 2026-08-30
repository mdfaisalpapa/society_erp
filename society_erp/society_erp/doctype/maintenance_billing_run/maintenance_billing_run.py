import frappe
from frappe.model.document import Document
from frappe.utils import flt

class MaintenanceBillingRun(Document):
    pass

@frappe.whitelist()
def fetch_and_calculate_blocks(doc_name):
    doc = frappe.get_doc("Maintenance Billing Run", doc_name)
    doc.set("block_details", []) 
    
    # Fetch blocks including your total_block_uds and taxes/charges template
    all_blocks = frappe.get_all("Block", fields=["name", "cost_center", "total_block_uds", "taxes_and_charges"])
    
    if not all_blocks:
        frappe.throw("No Blocks found in the system.")
        
    for block in all_blocks:
        if not block.cost_center or not block.total_block_uds:
            continue 
            
        # Fetch the net expense for this block's cost center
        balance = frappe.db.sql("""
            SELECT (SUM(debit) - SUM(credit)) as net_balance
            FROM `tabGL Entry` 
            WHERE cost_center = %s AND company = %s AND is_cancelled = 0
        """, (block.cost_center, doc.company))[0][0] or 0
        
        if balance > 0:
            # Calculate the cost per unit of UDS proportionally
            rate_per_uds = flt(balance / block.total_block_uds, 6)
            
            doc.append("block_details", {
                "block": block.name,
                "cost_center": block.cost_center,
                "total_expense": flt(balance, 2),
                "total_block_uds": block.total_block_uds,
                "rate_per_uds": rate_per_uds
            })
            
    doc.save()
    return "Success"

@frappe.whitelist()
def trigger_invoice_generation(doc_name):
    doc = frappe.get_doc("Maintenance Billing Run", doc_name)
    
    if doc.docstatus != 1:
        frappe.throw("Please Submit (Lock) the Billing Run before generating invoices.")
        
    # Queue the heavy processing safely in the background
    frappe.enqueue(
        'society_erp.society_erp.doctype.maintenance_billing_run.maintenance_billing_run.process_bulk_invoices',
        queue='long',
        timeout=1500,
        doc_name=doc_name
    )
    
    return "Background job started! Your draft invoices will appear in the Sales Invoice list shortly."

def process_bulk_invoices(doc_name):
    doc = frappe.get_doc("Maintenance Billing Run", doc_name)
    maintenance_item_code = "Monthly Maintenance Charge" 
    
    for row in doc.block_details:
        block_doc = frappe.get_doc("Block", row.block)
        
        # Fetch all flats linked to this block via your custom_block field
        flats = frappe.get_all("Customer", filters={"custom_block": row.block}, fields=["name", "custom_uds"])
        
        for flat in flats:
            flat_uds = flt(flat.custom_uds)
            if flat_uds <= 0:
                continue # Skip flats without UDS configuration
                
            # Calculate this specific flat's proportional share based on its UDS
            flat_share_amount = flt(row.rate_per_uds * flat_uds, 2)
            
            # Find the currently Active Owner from your custom DocType
            active_owner = frappe.db.get_value(
                "Owner", 
                {"flat_link": flat.name, "active": 1}, 
                "owner_name"
            )
            
            si = frappe.new_doc("Sales Invoice")
            si.customer = flat.name
            si.company = doc.company
            si.posting_date = doc.posting_date
            
            owner_text = f"Attn: {active_owner}" if active_owner else "Attn: Current Resident"
            si.remarks = f"Maintenance for {doc.billing_month} - {owner_text}"
            
            si.append("items", {
                "item_code": maintenance_item_code,
                "qty": 1,
                "rate": flat_share_amount,
                "cost_center": row.cost_center,
                "description": f"Maintenance for {doc.billing_month} ({flat_uds} UDS)"
            })
            
            # Automatically apply the Corpus/Sinking Fund percentages template if mapped
            if block_doc.taxes_and_charges:
                si.taxes_and_charges_added = block_doc.taxes_and_charges
                
            si.insert()
