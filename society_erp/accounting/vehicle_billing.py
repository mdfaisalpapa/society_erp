import frappe
from frappe.utils import flt, today

def create_vehicle_sticker_invoice_and_receipt(vehicle_doc):
    """
    Creates and submits a Sales Invoice and linked Payment Entry (Receipt)
    for a nominal vehicle sticker fee upon committee approval.
    """
    flat_no = vehicle_doc.flat
    amount = flt(vehicle_doc.get("payment_amount") or 50.0)
    utr = (vehicle_doc.get("payment_reference_no") or "").strip() or "UPI-TRANSFER"
    pay_date = vehicle_doc.get("payment_date") or today()

    # Determine company
    company = "KVC3-TEST"
    if not frappe.db.exists("Company", company):
        existing_companies = frappe.get_all("Company", pluck="name")
        if existing_companies:
            company = existing_companies[0]

    # Determine Cost Center based on flat block (e.g., 'A1 Block - CHCR') or default to 'Common - CHCR'
    abbr = frappe.get_cached_value("Company", company, "abbr") or "CHCR"
    cost_center = f"Common - {abbr}"
    if not frappe.db.exists("Cost Center", cost_center):
        # Fallback to any active cost center for company
        existing_cc = frappe.get_all("Cost Center", filters={"company": company, "is_group": 0}, pluck="name", limit=1)
        if existing_cc:
            cost_center = existing_cc[0]

    if frappe.db.exists("Customer", flat_no):
        block = frappe.db.get_value("Customer", flat_no, "custom_block")
        if block:
            candidate_cc = f"{block} Block - {abbr}"
            if frappe.db.exists("Cost Center", candidate_cc):
                cost_center = candidate_cc

    item_code = frappe.db.get_single_value("Society ERP Settings", "vehicle_sticker_item") or "Vehicle RFID Sticker Fee"
    if not frappe.db.exists("Item", item_code):
        item_code = "Vehicle RFID Sticker Fee"

    # 1. Create and submit Sales Invoice
    si = frappe.new_doc("Sales Invoice")
    si.customer = flat_no
    si.company = company
    si.posting_date = pay_date
    si.due_date = pay_date
    si.remarks = f"Vehicle RFID Sticker Fee for {vehicle_doc.registration_number} (Flat: {flat_no}) - UPI Ref: {utr}"
    
    si.append("items", {
        "item_code": item_code,
        "qty": 1,
        "rate": amount,
        "cost_center": cost_center,
        "description": f"Vehicle RFID Sticker Fee ({vehicle_doc.vehicle_type} - {vehicle_doc.registration_number})"
    })
    
    si.run_method("set_missing_values")
    si.cost_center = cost_center
    for it in si.items:
        it.cost_center = cost_center
    
    si.insert(ignore_permissions=True)
    si.submit()

    # 2. Create and submit Payment Entry (Receipt)
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
    
    # Locate Central Bank of India GL Account for company
    bank_gl_acc = f"4139313654 - Central Bank of India - {abbr}"
    if not frappe.db.exists("Account", bank_gl_acc):
        # Search by account number or Bank type
        cbi_accs = frappe.get_all(
            "Account",
            filters={"company": company, "account_type": "Bank", "account_number": "4139313654"},
            pluck="name"
        )
        if cbi_accs:
            bank_gl_acc = cbi_accs[0]
        else:
            # Fallback to default bank account
            bank_gl_acc = frappe.get_cached_value("Company", company, "default_bank_account")

    pe = get_payment_entry("Sales Invoice", si.name, bank_account=bank_gl_acc)
    pe.mode_of_payment = "UPI" if frappe.db.exists("Mode of Payment", "UPI") else "Wire Transfer"
    pe.reference_no = utr
    pe.reference_date = pay_date
    pe.remarks = f"UPI Payment received for vehicle sticker {vehicle_doc.registration_number} (Flat: {flat_no}) via Central Bank of India"
    
    pe.insert(ignore_permissions=True)
    pe.submit()

    return si.name, pe.name
