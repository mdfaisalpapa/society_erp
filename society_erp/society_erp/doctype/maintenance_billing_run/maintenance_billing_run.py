import frappe
from frappe.model.document import Document
from frappe.utils import flt

class MaintenanceBillingRun(Document):
    def on_submit(self):
        # Directly call the function to force it onto the main terminal thread
        process_bulk_invoices(self.name)
        frappe.msgprint("Billing Run Locked. Invoices generated directly.")

@frappe.whitelist()
def fetch_and_calculate_blocks(doc_name):
    """
    Fetches net expenses for each block's cost center in strict ascending order,
    and calculates the universal rate per unit of UDS.
    """
    doc = frappe.get_doc("Maintenance Billing Run", doc_name)
    doc.set("block_details", []) 
    
    # Fetch blocks sorted alphabetically (A1 to D3) to ensure clean reporting
    all_blocks = frappe.get_all(
        "Block", 
        fields=["name", "cost_center", "total_block_uds"],
        order_by="name asc"
    )
    
    if not all_blocks:
        frappe.throw("No Blocks found in the system.")
        
    for block in all_blocks:
        if not block.cost_center or not block.total_block_uds:
            continue 
            
        # Fetch the net expense for this block's cost center (Debits - Credits)
        balance = frappe.db.sql("""
            SELECT (SUM(debit) - SUM(credit)) as net_balance
            FROM `tabGL Entry` 
            WHERE cost_center = %s AND company = %s AND is_cancelled = 0
        """, (block.cost_center, doc.company))[0][0] or 0
        
        # Only process if there are actual expenses to apportion
        if balance > 0:
            # Calculate the universal rate per unit of UDS (6 decimal places for precision)
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
    """
    Validates document submission and queues the heavy background worker 
    to prevent browser gateway timeouts.
    """
    doc = frappe.get_doc("Maintenance Billing Run", doc_name)
    
    if doc.docstatus != 1:
        frappe.throw("Please Submit (Lock) the Billing Run before generating invoices.")
        
    frappe.enqueue(
        'society_erp.society_erp.doctype.maintenance_billing_run.maintenance_billing_run.process_bulk_invoices',
        queue='long',
        timeout=1500,
        doc_name=doc_name
    )
    
    return "Background job started! Your draft invoices will appear in the Sales Invoice list shortly."

def process_bulk_invoices(doc_name):
    print(f"\n--- [DEBUG] STARTING INVOICE JOB FOR: {doc_name} (TEST MODE: 10 INVOICES) ---")
    frappe.log_error(f"Test Job triggered for {doc_name}", "Billing Run Debug")
    
    try:
        doc = frappe.get_doc("Maintenance Billing Run", doc_name)
        maintenance_item_code = "Monthly Maintenance Charge" 
        
        global_tax_template = frappe.db.get_single_value(
            "Society ERP Settings", 
            "infrastructure_asset_depreciation_template"
        )
        print(f"[DEBUG] Fetched Tax Template: {global_tax_template}")
        
        test_counter = 0 # Initialize counter
        
        for row in doc.block_details:
            # Stop processing blocks if we hit 10
            if test_counter >= 10:
                break
                
            print(f"[DEBUG] Processing Block: {row.block}")
            
            flats = frappe.get_all(
                "Customer", 
                filters={"custom_block": row.block}, 
                fields=["name", "custom_uds"]
            )
            
            for flat in flats:
                # Stop processing flats if we hit 10
                if test_counter >= 10:
                    break
                    
                flat_uds = flt(flat.custom_uds)
                if flat_uds <= 0:
                    continue 
                    
                flat_share_amount = flt(row.rate_per_uds * flat_uds, 2)
                
                # Fetching active owner from the correct Owners doctype and field mapping
                active_owner = frappe.db.get_value("Owners", {"flat": flat.name, "active": 1}, "owner_name")
                owner_text = f"Attn: {active_owner}" if active_owner else "Attn: Current Resident"
                
                si = frappe.new_doc("Sales Invoice")
                si.customer = flat.name
                si.company = doc.company
                si.posting_date = doc.posting_date
                si.remarks = f"Maintenance for {doc.billing_month} - {owner_text}"
                
                si.append("items", {
                    "item_code": maintenance_item_code,
                    "qty": 1,
                    "rate": flat_share_amount,
                    "cost_center": row.cost_center,
                    "description": f"Maintenance for {doc.billing_month} ({flat_uds} UDS)"
                })
                
                # Apply standard ERPNext taxes field and trigger calculations
                if global_tax_template:
                    si.taxes_and_charges = global_tax_template
                    
                si.run_method("set_missing_values")
                si.run_method("calculate_taxes_and_totals")
                    
                si.insert()
                
                test_counter += 1
                print(f"[DEBUG] Successfully inserted SI for {flat.name} with Taxes (Test {test_counter}/10)")
                
        print(f"--- [DEBUG] INVOICE TEST JOB COMPLETED ---")
        frappe.log_error("Test Invoice generation completed successfully.", "Billing Run Debug")
        
    except Exception as e:
        print(f"[DEBUG] ERROR: {str(e)}")
        frappe.log_error(frappe.get_traceback(), f"Billing Run Failed: {doc_name}")
