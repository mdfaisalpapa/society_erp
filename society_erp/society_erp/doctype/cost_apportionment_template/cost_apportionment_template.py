import frappe
from frappe.model.document import Document
from frappe.utils import flt, today

class CostApportionmentTemplate(Document):
    def on_update(self):
        # Automatically update balance whenever the document is saved
        if self.parent_cost_center and self.company:
            check_unallocated_balance(self.name, self.parent_cost_center, self.company)

def get_all_child_cost_centers(parent_cost_center, company):
    parent = frappe.get_doc("Cost Center", parent_cost_center)
    return frappe.get_all(
        "Cost Center", 
        filters={
            "lft": (">=", parent.lft), 
            "rgt": ("<=", parent.rgt), 
            "is_group": 0, 
            "company": company
        }, 
        pluck="name"
    )

@frappe.whitelist()
def check_unallocated_balance(template_name, parent_cost_center, company):
    if not parent_cost_center or not company:
        return 0.0

    child_cost_centers = get_all_child_cost_centers(parent_cost_center, company)
    if not child_cost_centers:
        return 0.0

    grand_total = 0.0
    for cc in child_cost_centers:
        balance = frappe.db.sql("""
            SELECT (SUM(debit) - SUM(credit)) as net_balance
            FROM `tabGL Entry` 
            WHERE cost_center = %s AND company = %s AND is_cancelled = 0 
        """, (cc, company))[0][0] or 0
        
        if balance > 0:
            grand_total += balance
            
    if frappe.db.exists("Cost Apportionment Template", template_name):
        frappe.db.set_value("Cost Apportionment Template", template_name, "latest_unallocated_balance", grand_total)
    
    return grand_total

@frappe.whitelist()
def generate_apportionment_je(template_name):
    doc = frappe.get_doc("Cost Apportionment Template", template_name)
    
    if doc.docstatus != 1:
        frappe.throw("You must Submit (Lock) this template before generating an apportionment.")
        
    # --- STRICT CHECK: Prevent duplicate Draft JEs ---
    existing_draft = frappe.db.exists("Journal Entry", {
        "user_remark": ["like", f"%Template: {doc.name}%"],
        "docstatus": 0,
        "company": doc.company
    })
    if existing_draft:
        frappe.throw(f"A Draft Journal Entry (<b>{existing_draft}</b>) already exists for this template. Please submit or cancel it before generating a new one.")

    total_pct = sum([flt(row.percentage) for row in doc.allocation_rules])
    if not (99.99 <= total_pct <= 100.01):
        frappe.throw(f"Allocation percentages must total exactly 100%. Currently totals {total_pct}%")

    child_cost_centers = get_all_child_cost_centers(doc.parent_cost_center, doc.company)

    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Journal Entry"
    je.posting_date = today()
    je.company = doc.company
    je.user_remark = f"Automated Apportionment of {doc.parent_cost_center} (Template: {doc.name})"

    grand_total = 0.0
    row_remarks_map = []
    entries_found = False

    for cc in child_cost_centers:
        account_balances = frappe.db.sql("""
            SELECT account, (SUM(debit) - SUM(credit)) as net_balance
            FROM `tabGL Entry` 
            WHERE cost_center = %s AND company = %s AND is_cancelled = 0 
            GROUP BY account
            HAVING net_balance > 0
        """, (cc, doc.company), as_dict=True)
        
        for bal in account_balances:
            entries_found = True
            grand_total += bal.net_balance
            
            # 1. CREDIT Row (Clearing the expense account for the amenity)
            je.append("accounts", {
                "account": bal.account, 
                "cost_center": cc, 
                "credit_in_account_currency": flt(bal.net_balance, 2)
            })
            row_remarks_map.append(f"Apportioned share from {cc}")
            
            # 2. DEBIT Rows (Distributing to blocks based on whole percentages)
            allocated_total = 0.0
            for i, rule in enumerate(doc.allocation_rules):
                if i == len(doc.allocation_rules) - 1:
                    debit_amount = flt(bal.net_balance - allocated_total, 2)
                else:
                    debit_amount = flt(bal.net_balance * (flt(rule.percentage) / 100.0), 2)
                    
                allocated_total += debit_amount

                je.append("accounts", {
                    "account": bal.account, 
                    "cost_center": rule.target_cost_center,
                    "debit_in_account_currency": debit_amount
                })
                row_remarks_map.append(f"Apportioned share from {cc}")

    if not entries_found:
        frappe.msgprint(f"No unallocated expenses found for {doc.parent_cost_center}.")
        return None

    je.insert()
    
    for i, d in enumerate(je.accounts):
        if i < len(row_remarks_map):
            frappe.db.sql("UPDATE `tabJournal Entry Account` SET user_remark = %s WHERE name = %s", (row_remarks_map[i], d.name))
            
    return je.name
