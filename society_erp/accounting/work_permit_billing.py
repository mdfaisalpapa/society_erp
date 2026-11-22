import frappe
from frappe.utils import flt, today

def get_permit_bank_and_company_details(permit_doc):
    """
    Returns (company, bank_account_no, bank_ifsc, beneficiary, abbr, cost_center)
    """
    company = "KVC3-TEST"
    if not frappe.db.exists("Company", company):
        existing_companies = frappe.get_all("Company", pluck="name")
        if existing_companies:
            company = existing_companies[0]

    abbr = frappe.get_cached_value("Company", company, "abbr") or "CHCR"

    # Default cost center
    cost_center = f"General Common - {abbr}"
    if not frappe.db.exists("Cost Center", cost_center):
        existing_cc = frappe.get_all(
            "Cost Center",
            filters={"company": company, "is_group": 0},
            pluck="name",
            limit=1
        )
        if existing_cc:
            cost_center = existing_cc[0]

    flat_no = permit_doc.flat_number
    if flat_no and frappe.db.exists("Customer", flat_no):
        block = frappe.db.get_value("Customer", flat_no, "custom_block")
        if block:
            candidate_cc = f"{block} Block - {abbr}"
            if frappe.db.exists("Cost Center", candidate_cc) and not frappe.db.get_value("Cost Center", candidate_cc, "is_group"):
                cost_center = candidate_cc

    settings = frappe.get_single("Society ERP Settings")
    bank_account_no = (settings.bank_account_number or "4139313654").strip()
    bank_ifsc = (settings.bank_ifsc_code or "CBIN0283135").strip()
    beneficiary = (settings.bank_account_beneficiary_name or "Apartment Owners Association").strip()

    return {
        "company": company,
        "abbr": abbr,
        "cost_center": cost_center,
        "bank_account_no": bank_account_no,
        "bank_ifsc": bank_ifsc,
        "beneficiary": beneficiary,
    }


def create_work_permit_invoice_and_deposit(permit_doc):
    """
    Creates and submits:
    1. Sales Invoice for retained Admin/Debris charge (₹1,000)
    2. Payment Entry (Receipt) for total Deposit Collected (₹5,000):
       - ₹1,000 allocated to Sales Invoice
       - ₹4,000 unallocated refundable security deposit
    """
    flat_no = permit_doc.flat_number
    deposit_collected = flt(permit_doc.get("deposit_amount") or 5000.0)
    retained_fee = 1000.0
    utr = (permit_doc.get("payment_reference_no") or "").strip() or "UPI-DEPOSIT"
    pay_date = permit_doc.get("payment_date") or today()

    details = get_permit_bank_and_company_details(permit_doc)
    company = details["company"]
    abbr = details["abbr"]
    cost_center = details["cost_center"]

    # 1. Sales Invoice for retained portion (₹1,000)
    item_code = "Work Permit Debris & Admin Charge"
    if not frappe.db.exists("Item", item_code):
        item_doc = frappe.new_doc("Item")
        item_doc.item_code = item_code
        item_doc.item_name = "Work Permit Debris & Admin Charge"
        item_doc.item_group = "Services"
        item_doc.is_stock_item = 0
        item_doc.is_sales_item = 1
        item_doc.gst_hsn_code = "999598"
        item_doc.insert(ignore_permissions=True)

    si = frappe.new_doc("Sales Invoice")
    si.customer = flat_no
    si.company = company
    si.posting_date = pay_date
    si.due_date = pay_date
    si.remarks = f"Work Permit Debris & Admin Retained Fee for Permit #{permit_doc.name} (Flat: {flat_no}) - UPI Ref: {utr}"

    si.append("items", {
        "item_code": item_code,
        "qty": 1,
        "rate": retained_fee,
        "cost_center": cost_center,
        "description": f"Work Permit Debris & Admin Fee ({permit_doc.work_type} - Contractor: {permit_doc.contractor_name})"
    })

    si.run_method("set_missing_values")
    si.cost_center = cost_center
    for it in si.items:
        it.cost_center = cost_center

    si.insert(ignore_permissions=True)
    si.submit()

    # 2. Payment Entry (Receipt) for ₹5,000 total collection
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

    bank_gl_acc = f"{details['bank_account_no']} - Central Bank of India - {abbr}"
    if not frappe.db.exists("Account", bank_gl_acc):
        cbi_accs = frappe.get_all(
            "Account",
            filters={"company": company, "account_type": "Bank", "account_number": details["bank_account_no"]},
            pluck="name"
        )
        if cbi_accs:
            bank_gl_acc = cbi_accs[0]
        else:
            def_bank = frappe.db.get_value("Company", company, "default_bank_account")
            bank_gl_acc = def_bank if def_bank else frappe.get_all("Account", filters={"company": company, "account_type": "Bank"}, pluck="name")[0]

    pe = get_payment_entry("Sales Invoice", si.name, bank_account=bank_gl_acc)
    pe.paid_amount = deposit_collected
    pe.received_amount = deposit_collected
    pe.mode_of_payment = "UPI"
    pe.reference_no = utr
    pe.reference_date = pay_date
    pe.cost_center = cost_center
    pe.remarks = f"Work Permit Deposit collected for Permit #{permit_doc.name} (Flat: {flat_no}). ₹1,000 retained, ₹4,000 refundable on debris clearance."

    pe.insert(ignore_permissions=True)
    pe.submit()

    return si.name, pe.name


def process_work_permit_refund(permit_doc, refund_utr=None, refund_date=None, refund_amount=4000.0):
    """
    Creates and submits a refund Payment Entry (Payment Type: Pay) for ₹4,000
    from AoA Bank to Customer upon completion and debris clearance.
    """
    flat_no = permit_doc.flat_number
    amount = flt(refund_amount or 4000.0)
    ref_no = (refund_utr or permit_doc.get("refund_reference_no") or "").strip() or f"REFUND-WP-{permit_doc.name}"
    ref_date = refund_date or permit_doc.get("refund_date") or today()

    details = get_permit_bank_and_company_details(permit_doc)
    company = details["company"]
    abbr = details["abbr"]
    cost_center = details["cost_center"]

    bank_gl_acc = f"{details['bank_account_no']} - Central Bank of India - {abbr}"
    if not frappe.db.exists("Account", bank_gl_acc):
        cbi_accs = frappe.get_all(
            "Account",
            filters={"company": company, "account_type": "Bank", "account_number": details["bank_account_no"]},
            pluck="name"
        )
        if cbi_accs:
            bank_gl_acc = cbi_accs[0]
        else:
            def_bank = frappe.db.get_value("Company", company, "default_bank_account")
            bank_gl_acc = def_bank if def_bank else frappe.get_all("Account", filters={"company": company, "account_type": "Bank"}, pluck="name")[0]

    # Find debtor account for customer
    from erpnext.accounts.party import get_party_account
    party_acc = get_party_account("Customer", flat_no, company)
    if not party_acc:
        party_acc = frappe.db.get_value("Company", company, "default_receivable_account") or f"Debtors - {abbr}"

    ref_pe = frappe.new_doc("Payment Entry")
    ref_pe.payment_type = "Pay"
    ref_pe.party_type = "Customer"
    ref_pe.party = flat_no
    ref_pe.party_account = party_acc
    ref_pe.company = company
    ref_pe.paid_from = bank_gl_acc
    ref_pe.paid_to = party_acc
    ref_pe.paid_amount = amount
    ref_pe.received_amount = amount
    ref_pe.target_exchange_rate = 1.0
    ref_pe.reference_no = ref_no
    ref_pe.reference_date = ref_date
    ref_pe.mode_of_payment = "UPI"
    ref_pe.cost_center = cost_center
    ref_pe.remarks = f"Work Permit Refund (Debris Cleared) for Permit #{permit_doc.name} (Flat: {flat_no}) - UTR: {ref_no}"

    ref_pe.insert(ignore_permissions=True)
    ref_pe.submit()

    return ref_pe.name
