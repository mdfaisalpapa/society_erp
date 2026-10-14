import frappe
from frappe.model.document import Document
from frappe.utils import flt, get_first_day, get_last_day
from frappe.model.naming import make_autoname
from datetime import datetime

class MaintenanceBillingRun(Document):
    def autoname(self):
        # 1. Force calculate the Billing Month on the backend
        if self.posting_date:
            d = datetime.strptime(str(self.posting_date), "%Y-%m-%d")
            self.billing_month = d.strftime("%B %Y")
        
        # 2. Generate the precise ID format (e.g., January 2026-0001)
        if self.billing_month:
            self.name = make_autoname(f"{self.billing_month}-.####")
            
    def before_submit(self):
        # Safely assign the status right before the document is locked
        auto_generate = frappe.db.get_single_value("Society ERP Settings", "auto_generate_invoices")
        if auto_generate:
            self.generation_status = "Queued"

    def on_submit(self):
        auto_generate = frappe.db.get_single_value("Society ERP Settings", "auto_generate_invoices")
        
        if auto_generate:
            # Trigger the background queue
            frappe.enqueue(
                'society_erp.society_erp.doctype.maintenance_billing_run.maintenance_billing_run.process_bulk_invoices',
                queue='long',
                timeout=1500,
                doc_name=self.name
            )
            frappe.msgprint("Billing Run Locked. Invoices are generating in the background.")

# ... [Keep your existing fetch_and_calculate_blocks, trigger_invoice_generation, and process_bulk_invoices functions unchanged below this point] ...
import frappe
from frappe.model.document import Document
from frappe.utils import flt, get_last_day

@frappe.whitelist()
def fetch_and_calculate_blocks(doc_name):
    doc = frappe.get_doc("Maintenance Billing Run", doc_name)
    doc.set("block_details", []) 
    
    # Fetch blocks including total block UDS
    all_blocks = frappe.get_all("Block", fields=["name", "cost_center", "total_block_uds"])
    
    if not all_blocks:
        frappe.throw("No Blocks found in the system.")
        
    grand_total = 0.0
    
    # NEW: Establish the exact start and end dates for the billing month
    start_date = get_first_day(doc.posting_date)
    end_date = get_last_day(doc.posting_date)
        
    for block in all_blocks:
        if not block.cost_center or not block.total_block_uds:
            continue 
            
        # FIXED: Joined tabAccount to isolate 'Expense' root types and filtered by the specific month
        balance = frappe.db.sql("""
            SELECT (SUM(ge.debit) - SUM(ge.credit)) as net_balance
            FROM `tabGL Entry` ge
            JOIN `tabAccount` acc ON ge.account = acc.name
            WHERE ge.cost_center = %s 
            AND ge.company = %s 
            AND ge.is_cancelled = 0
            AND acc.root_type = 'Expense'
            AND ge.posting_date BETWEEN %s AND %s
        """, (block.cost_center, doc.company, start_date, end_date))[0][0] or 0
        
        if balance > 0:
            grand_total += balance
            rate_per_uds = flt(balance / block.total_block_uds, 6)
            
            doc.append("block_details", {
                "block": block.name,
                "cost_center": block.cost_center,
                "total_expense": flt(balance, 2),
                "total_block_uds": block.total_block_uds,
                "rate_per_uds": rate_per_uds
            })
            
    doc.total_billed_amount = flt(grand_total, 2)
    doc.save()
    return "Success"

def process_bulk_invoices(doc_name):
    try:
        doc = frappe.get_doc("Maintenance Billing Run", doc_name)
        
        # Failsafe to block duplicate background jobs
        if doc.generation_status == "Completed":
            return 
            
        maintenance_item_code = frappe.db.get_single_value("Society ERP Settings", "monthly_maintenance_item")
        auto_submit = frappe.db.get_single_value("Society ERP Settings", "submit_invoices_automatically")
        
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
                si.set_posting_time = 1 
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
                
                # 1. Force the cost center at the Header Level
                si.cost_center = row.cost_center
                
                # 2. Force the cost center at the Item Level (Income)
                for item in si.get("items"):
                    item.cost_center = row.cost_center
                    
                # 3. Force the cost center onto the Reserve Funds (Taxes Table)
                for tax in si.get("taxes"):
                    tax.cost_center = row.cost_center
                    
                si.run_method("calculate_taxes_and_totals")
                
                si.payment_terms_template = None
                si.set("payment_schedule", [])
                si.due_date = doc.posting_date 
                
                si.insert(ignore_permissions=True)
                
                if auto_submit:
                    si.submit()
                
        # Lock the document from further generation
        frappe.db.set_value("Maintenance Billing Run", doc_name, "generation_status", "Completed")
        frappe.db.commit()
        frappe.log_error(f"Bulk billing completed successfully for {doc_name}.", "Billing Run Success")
        
    except Exception as e:
        # Revert status to allow retrying in case of critical failure
        frappe.db.set_value("Maintenance Billing Run", doc_name, "generation_status", "Pending")
        frappe.db.commit()
        frappe.log_error(frappe.get_traceback(), f"Billing Run Failed: {doc_name}")
