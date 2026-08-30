import frappe
from frappe.model.document import Document
from frappe.utils import flt, today

class CostApportionmentTemplate(Document):
    def on_update(self):
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
        # UPDATED: We now check every account individually to get the absolute total of uncleared items
        account_balances = frappe.db.sql("""
            SELECT (SUM(debit) - SUM(credit)) as net_balance
            FROM `tabGL Entry` 
            WHERE cost_center = %s AND company = %s AND is_cancelled = 0 
            GROUP BY account
            HAVING net_balance != 0 
        """, (cc, company), as_dict=True)
        
        for bal in account_balances:
            # We add the absolute value so the UI shows the total volume of money waiting to be apportioned
            grand_total += abs(bal.net_balance)
            
    if frappe.db.exists("Cost Apportionment Template", template_name):
        frappe.db.set_value("Cost Apportionment Template", template_name, "latest_unallocated_balance", grand_total)
    
    return grand_total

@frappe.whitelist()
def generate_apportionment_je(template_name):
    doc = frappe.get_doc("Cost Apportionment Template", template_name)
    
    if doc.docstatus != 1:
        frappe.throw("You must Submit (Lock) this template before generating an apportionment.")

    total_pct = sum([flt(row.percentage) for row in doc.allocation_rules])
    if not (99.99 <= total_pct <= 100.01):
        frappe.throw(f"Allocation percentages must total exactly 100%. Currently totals {total_pct}%")

    child_cost_centers = get_all_child_cost_centers(doc.parent_cost_center, doc.company)
    generated_jvs = []
    
    for cc in child_cost_centers:
        existing_draft = frappe.db.exists("Journal Entry", {
            "user_remark": ["like", f"%Apportionment of {cc} (Template: {doc.name})%"],
            "docstatus": 0,
            "company": doc.company
        })
        if existing_draft:
            frappe.throw(f"A Draft Journal Entry (<b>{existing_draft}</b>) already exists for <b>{cc}</b>. Please submit or cancel it before generating a new batch.")

    for cc in child_cost_centers:
        # UPDATED: HAVING net_balance != 0 captures both Expenses (Positive) and Income (Negative)
        account_balances = frappe.db.sql("""
            SELECT account, (SUM(debit) - SUM(credit)) as net_balance
            FROM `tabGL Entry` 
            WHERE cost_center = %s AND company = %s AND is_cancelled = 0 
            GROUP BY account
            HAVING net_balance != 0
        """, (cc, doc.company), as_dict=True)
        
        if not account_balances:
            continue
            
        je = frappe.new_doc("Journal Entry")
        je.voucher_type = "Journal Entry"
        je.posting_date = today()
        je.company = doc.company
        je.user_remark = f"Automated Apportionment of {cc} (Template: {doc.name})"
        
        row_remarks_map = []

        for bal in account_balances:
            # --- NEW: Omni-Directional Logic ---
            is_expense = bal.net_balance > 0
            absolute_balance = abs(flt(bal.net_balance, 2))
            
            credit_remark_idx = len(row_remarks_map)
            
            # 1. CLEARING ENTRY for the Common Amenity
            je.append("accounts", {
                "account": bal.account, 
                "cost_center": cc, 
                "credit_in_account_currency": absolute_balance if is_expense else 0.0,
                "debit_in_account_currency": absolute_balance if not is_expense else 0.0
            })
            row_remarks_map.append("") 
            
            allocated_total = 0.0
            breakdown_list = []
            
            for i, rule in enumerate(doc.allocation_rules):
                if i == len(doc.allocation_rules) - 1:
                    apportioned_amount = flt(absolute_balance - allocated_total, 2)
                else:
                    apportioned_amount = flt(absolute_balance * (flt(rule.percentage) / 100.0), 2)
                    
                allocated_total += apportioned_amount
                
                clean_block_name = str(rule.target_cost_center).split(" - ")[0]
                breakdown_list.append(f"{clean_block_name} {apportioned_amount}")

                # 2. DISTRIBUTION ENTRY for the Blocks
                je.append("accounts", {
                    "account": bal.account, 
                    "cost_center": rule.target_cost_center,
                    "debit_in_account_currency": apportioned_amount if is_expense else 0.0,
                    "credit_in_account_currency": apportioned_amount if not is_expense else 0.0
                })
                row_remarks_map.append(f"Apportioned share from {cc}")
                
            # Customize the remark based on whether money is going out or coming in
            action_word = "Expense apportioned to: " if is_expense else "Income distributed to: "
            row_remarks_map[credit_remark_idx] = action_word + ", ".join(breakdown_list)

        je.insert()
        
        for i, d in enumerate(je.accounts):
            if i < len(row_remarks_map):
                frappe.db.sql("UPDATE `tabJournal Entry Account` SET user_remark = %s WHERE name = %s", (row_remarks_map[i], d.name))
                
        generated_jvs.append(je.name)

    if not generated_jvs:
        frappe.msgprint(f"No unallocated balances found for any cost centers under {doc.parent_cost_center}.")
        return None

    return generated_jvs
