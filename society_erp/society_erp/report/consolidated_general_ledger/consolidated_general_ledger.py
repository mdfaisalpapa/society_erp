import sys
import frappe
from frappe.utils import getdate
from erpnext.accounts.report.general_ledger.general_ledger import execute as gl_execute

def execute(filters=None):
    gl_output = gl_execute(filters)
    print(f"\n[DEBUG] Core GL Output Type: {type(gl_output)} | Length: {len(gl_output)}", file=sys.stderr)
    
    columns = gl_output[0]
    data = gl_output[1]
    print(f"[DEBUG] Rows returned: {len(data)}", file=sys.stderr)
    # ... rest of the code    
    # 2. If the user didn't check the consolidation box, return the unmodified core output
    if not filters.get("consolidate_sales"):
        return gl_output

    consolidated_data = []
    si_summary = {} 

    # 3. First Pass: Aggregate Sales Invoices by Date
    for row in data:
        if isinstance(row, dict) and row.get("voucher_type") == "Sales Invoice":
            d = row.get("posting_date")
            if d not in si_summary:
                month_name = getdate(d).strftime("%B %Y")
                si_summary[d] = {
                    "debit": 0.0,
                    "credit": 0.0,
                    "remarks": f"Monthly Maintenance Charges for the month of {month_name}"
                }
            si_summary[d]["debit"] += row.get("debit", 0.0)
            si_summary[d]["credit"] += row.get("credit", 0.0)

    # 4. Second Pass: Rebuild the ledger with running balances
    running_balance = 0.0
    processed_dates = set()

    for row in data:
        if not isinstance(row, dict):
            consolidated_data.append(row)
            continue

        # Preserve Opening/Closing/Total rows natively
        if not row.get("voucher_type"):
            if row.get("account") == "Opening" or "Opening" in str(row.get("account_name", "")):
                running_balance = row.get("debit", 0.0) - row.get("credit", 0.0)
            consolidated_data.append(row)
            continue

        posting_date = row.get("posting_date")

        if row.get("voucher_type") == "Sales Invoice":
            if posting_date not in processed_dates:
                si = si_summary[posting_date]
                running_balance += (si["debit"] - si["credit"])
                
                # Create the consolidated row while preserving standard column formatting
                new_row = row.copy() 
                new_row.update({
                    "account": "Multiple/Consolidated",
                    "party_type": "",
                    "party": "",
                    "against_account": "",
                    "against_voucher_type": "",
                    "against_voucher": "",
                    "voucher_no": "Consolidated",
                    "debit": si["debit"],
                    "credit": si["credit"],
                    "balance": running_balance,
                    "remarks": si["remarks"]
                })
                consolidated_data.append(new_row)
                processed_dates.add(posting_date)
        else:
            # Pass through standard Purchase Invoices / JEs and update running balance
            running_balance += (row.get("debit", 0.0) - row.get("credit", 0.0))
            row["balance"] = running_balance
            consolidated_data.append(row)

    # 5. Reconstruct the output tuple so we don't break Frappe's UI expectations
    result = list(gl_output)
    result[1] = consolidated_data
    
    return tuple(result)
