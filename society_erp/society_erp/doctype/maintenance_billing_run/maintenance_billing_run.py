import frappe
from frappe.model.document import Document
from frappe.utils import flt

class MaintenanceBillingRun(Document):
    def on_submit(self):
        auto_generate = frappe.db.get_single_value("Society ERP Settings", "auto_generate_invoices")
        
        if auto_generate:
            # Bypass the manual button and queue immediately
            frappe.enqueue(
                'society_erp.society_erp.doctype.maintenance_billing_run.maintenance_billing_run.process_bulk_invoices',
                queue='long',
                timeout=1500,
                doc_name=self.name
            )
            frappe.msgprint("Billing Run Locked. Invoices are generating in the background.")
        else:
            frappe.msgprint("Billing Run Locked. Please generate invoices manually using the button.")

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
    try:
        doc = frappe.get_doc("Maintenance Billing Run", doc_name)
        
        # Failsafe to block duplicate background jobs
        if doc.generation_status == "Completed":
            return 
            
        maintenance_item_code = frappe.db.get_single_value("Society ERP Settings", "monthly_maintenance_item")
        
        if not maintenance_item_code:
            frappe.log_error("Monthly Maintenance Item is missing in Settings", "Billing Run Error")
            frappe.db.set_value("Maintenance Billing Run", doc_name, "generation_status", "Pending")
            frappe.db.commit()
            return
            
        global_tax_template = frappe.db.get_single_value(
            "Society ERP Settings", 
            "infrastructure_asset_depreciation_template"
        )
        
        for row in doc.block_details:
            flats = frappe.get_all(
                "Customer", 
                filters={"custom_block": row.block}, 
                fields=["name", "custom_uds"]
            )
            
            for flat in flats:
                flat_uds = flt(flat.custom_uds)
                if flat_uds <= 0:
                    continue 
                    
                flat_share_amount = flt(row.rate_per_uds * flat_uds, 2)
                
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
                
                if global_tax_template:
                    si.taxes_and_charges = global_tax_template
                    
                si.run_method("set_missing_values")
                si.run_method("calculate_taxes_and_totals")
                
                # Invoices inserted as Drafts (docstatus = 0)
                si.insert(ignore_permissions=True)
                
        # Lock the document from further generation
        frappe.db.set_value("Maintenance Billing Run", doc_name, "generation_status", "Completed")
        frappe.db.commit()
        frappe.log_error(f"Bulk billing completed successfully for {doc_name}.", "Billing Run Success")
        
    except Exception as e:
        # Revert status to allow retrying in case of critical failure
        frappe.db.set_value("Maintenance Billing Run", doc_name, "generation_status", "Pending")
        frappe.db.commit()
        frappe.log_error(frappe.get_traceback(), f"Billing Run Failed: {doc_name}")
