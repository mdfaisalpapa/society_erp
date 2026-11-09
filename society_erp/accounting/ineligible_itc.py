import frappe
from collections import defaultdict
from frappe import _

from india_compliance.gst_india.constants import GST_TAX_TYPES
from india_compliance.gst_india.overrides.ineligible_itc import (
    DOCTYPE_MAPPING,
    update_regional_gl_entries as ic_update_regional_gl_entries,
    update_valuation_rate as ic_update_valuation_rate,
)
from india_compliance.gst_india.overrides.transaction import (
    is_indian_registered_company,
)
from india_compliance.gst_india.utils import get_gst_account_gst_tax_type_map


def is_unregistered_society(doc):
    """
    Returns True if the company is not recognized as a GST-registered company
    by India Compliance (e.g. an unregistered Apartment Owners Association).
    """
    return not is_indian_registered_company(doc)


def prepare_gst_details_for_unregistered(doc):
    """
    For unregistered entities, India Compliance's standard validations bypass
    setting `tax.gst_tax_type` and item `{tax_type}_amount`.
    This helper populates them from GST Settings and ERPNext's item-wise tax details
    so that India Compliance's IneligibleITC handler can process the invoice.
    """
    if not doc.get("taxes") or not doc.get("items"):
        return False

    gst_account_map = get_gst_account_gst_tax_type_map()
    has_gst_taxes = False

    # 1. Map gst_tax_type on tax rows from GST Settings
    for tax in doc.taxes:
        if not tax.gst_tax_type and tax.account_head in gst_account_map:
            tax.gst_tax_type = gst_account_map[tax.account_head]
        if tax.gst_tax_type:
            has_gst_taxes = True

    if not has_gst_taxes:
        return False

    # 2. Ensure item-wise tax details are calculated
    if not doc.get("_item_wise_tax_details"):
        doc.run_method("calculate_taxes_and_totals")

    # 3. Reset and populate item.{tax_type}_amount from _item_wise_tax_details
    for item in doc.items:
        for tax_type in GST_TAX_TYPES:
            item.set(f"{tax_type}_amount", 0.0)

    for row in doc.get("_item_wise_tax_details") or []:
        item = row.get("item")
        tax = row.get("tax")
        if not item or not tax:
            continue

        tax_type = getattr(tax, "gst_tax_type", None) or gst_account_map.get(tax.account_head)
        if tax_type and hasattr(item, "set"):
            current_amt = item.get(f"{tax_type}_amount") or 0.0
            item.set(f"{tax_type}_amount", current_amt + row.amount)

    return True


def validate_purchase_invoice(doc, method=None):
    """
    Purchase Invoice validation hook for society_erp.
    Sets ineligibility reason and marks items ineligible for ITC
    if GST is present on an unregistered society invoice.
    """
    if not is_unregistered_society(doc):
        return

    gst_account_map = get_gst_account_gst_tax_type_map()
    has_gst = any(
        (getattr(t, "gst_tax_type", None) or t.account_head in gst_account_map)
        for t in doc.get("taxes", [])
    )
    has_ineligible = any(item.get("is_ineligible_for_itc") for item in doc.get("items", []))

    if has_gst or has_ineligible:
        for item in doc.get("items", []):
            item.is_ineligible_for_itc = 1
        doc.ineligibility_reason = "Ineligible As Per Section 17(5)"
        prepare_gst_details_for_unregistered(doc)


def update_valuation_rate(doc, method=None):
    """
    Regional override for erpnext.controllers.buying_controller.update_regional_item_valuation_rate.
    For registered companies: delegates to India Compliance.
    For unregistered societies: enables stock valuation rate adjustment for ineligible ITC.
    """
    if not is_unregistered_society(doc):
        ic_update_valuation_rate(doc, method)
        return

    if doc.get("is_opening") == "Yes":
        return

    has_ineligible = any(item.get("is_ineligible_for_itc") for item in doc.get("items", []))
    if not has_ineligible:
        return

    if prepare_gst_details_for_unregistered(doc):
        if doc.doctype in DOCTYPE_MAPPING:
            DOCTYPE_MAPPING[doc.doctype](doc).update_valuation_rate()


def make_regional_gl_entries(gl_entries, doc):
    """
    Regional override for erpnext.accounts.doctype.purchase_invoice.purchase_invoice.make_regional_gl_entries.
    For registered companies: delegates to India Compliance.
    For unregistered societies:
      - Keeps line items at their base net amounts (does not load GST into items).
      - Excludes base Input Tax CGST/SGST/IGST entries.
      - Generates a single GST Expense entry per Cost Center with detailed narration.
    """
    if not is_unregistered_society(doc):
        return ic_update_regional_gl_entries(gl_entries, doc)

    if doc.get("is_opening") == "Yes":
        return gl_entries

    has_ineligible = any(item.get("is_ineligible_for_itc") for item in doc.get("items", []))
    if not has_ineligible:
        return gl_entries

    from frappe.utils import flt

    gst_account_map = get_gst_account_gst_tax_type_map()
    prepare_gst_details_for_unregistered(doc)

    company_doc = frappe.get_cached_doc("Company", doc.company)
    gst_expense_account = company_doc.default_gst_expense_account
    if not gst_expense_account:
        frappe.throw(
            _("Please set Default GST Expense Account in Company {0}").format(doc.company)
        )

    # 1. Identify all GST tax accounts to exclude from standard GL entries
    tax_accounts = set(gst_account_map.keys())
    for t in doc.get("taxes", []):
        tax_type = getattr(t, "gst_tax_type", None) or gst_account_map.get(t.account_head)
        if tax_type in GST_TAX_TYPES:
            tax_accounts.add(t.account_head)

    # 2. Filter out base Input Tax entries (keeps base item expense entries untouched)
    filtered_entries = [e for e in gl_entries if e.get("account") not in tax_accounts]

    # 3. Calculate GST total and group by Cost Center
    total_tax = sum(
        flt(t.base_tax_amount_after_discount_amount)
        for t in doc.get("taxes", [])
        if (getattr(t, "gst_tax_type", None) or gst_account_map.get(t.account_head)) in GST_TAX_TYPES
    )

    gst_by_cc = defaultdict(float)
    for row in doc.get("_item_wise_tax_details") or []:
        tax = row.get("tax")
        tax_type = getattr(tax, "gst_tax_type", None) or gst_account_map.get(tax.account_head)
        if tax_type in GST_TAX_TYPES:
            item = row.get("item")
            cc = (item.get("cost_center") if item else None) or doc.get("cost_center") or company_doc.cost_center
            gst_by_cc[cc] += flt(row.get("amount", 0.0), 2)

    # Fallback if _item_wise_tax_details was empty
    if not gst_by_cc and total_tax:
        for t in doc.get("taxes", []):
            tax_type = getattr(t, "gst_tax_type", None) or gst_account_map.get(t.account_head)
            if tax_type in GST_TAX_TYPES:
                cc = t.get("cost_center") or doc.get("cost_center") or company_doc.cost_center
                gst_by_cc[cc] += flt(t.base_tax_amount_after_discount_amount, 2)

    if not gst_by_cc:
        return gl_entries

    # Defensive rounding adjustment to match total_tax exactly
    diff = flt(total_tax - sum(gst_by_cc.values()), 2)
    if abs(diff) > 0 and gst_by_cc:
        largest_cc = max(gst_by_cc, key=gst_by_cc.get)
        gst_by_cc[largest_cc] += diff

    # 4. Generate a single GST Expense entry per Cost Center
    dr_or_cr = "credit" if doc.get("is_return") else "debit"
    bill_ref = doc.get("bill_no") or doc.name
    supplier_label = doc.get("supplier_name") or doc.get("supplier")

    for cc, amt in sorted(gst_by_cc.items()):
        amt = flt(amt, 2)
        if not amt:
            continue

        remarks_parts = [f"GST Expense: Bill {bill_ref}", supplier_label, cc]
        if doc.get("remarks") and doc.get("remarks") != doc.name:
            remarks_parts.append(doc.remarks)
        narration = " - ".join(remarks_parts)

        filtered_entries.append(
            doc.get_gl_dict({
                "account": gst_expense_account,
                "against": doc.supplier,
                dr_or_cr: amt,
                f"{dr_or_cr}_in_account_currency": amt,
                "cost_center": cc,
                "remarks": narration,
            })
        )

    return filtered_entries


def update_regional_gl_entries_pr(gl_entries, doc):
    """
    Regional override for erpnext.stock.doctype.purchase_receipt.purchase_receipt.update_regional_gl_entries.
    """
    if not is_unregistered_society(doc):
        return ic_update_regional_gl_entries(gl_entries, doc)

    if doc.get("is_opening") == "Yes":
        return gl_entries

    has_ineligible = any(item.get("is_ineligible_for_itc") for item in doc.get("items", []))
    if not has_ineligible:
        return gl_entries

    if prepare_gst_details_for_unregistered(doc):
        if doc.doctype in DOCTYPE_MAPPING:
            DOCTYPE_MAPPING[doc.doctype](doc).update_gl_entries(gl_entries)

    return filter_zero_balance_tax_entries(gl_entries, doc)


def filter_zero_balance_tax_entries(gl_entries, doc):
    """
    For unregistered societies, eliminates zero-balance transit entries
    (GST Expense clearing account and fully reversed Input Tax accounts)
    from GL Entries so they do not clutter the General Ledger.
    """
    from frappe.utils import flt

    gst_account_map = get_gst_account_gst_tax_type_map()
    company_doc = frappe.get_cached_doc("Company", doc.company)
    gst_expense_account = company_doc.default_gst_expense_account

    target_accounts = set(gst_account_map.keys())
    if gst_expense_account:
        target_accounts.add(gst_expense_account)

    account_totals = defaultdict(lambda: {"dr": 0.0, "cr": 0.0})
    for entry in gl_entries:
        acc = entry.get("account")
        if acc in target_accounts:
            account_totals[acc]["dr"] += flt(entry.get("debit", 0.0))
            account_totals[acc]["cr"] += flt(entry.get("credit", 0.0))

    zero_accounts = set()
    for acc, totals in account_totals.items():
        if abs(totals["dr"] - totals["cr"]) < 0.005:
            zero_accounts.add(acc)

    if not zero_accounts:
        return gl_entries

    return [e for e in gl_entries if e.get("account") not in zero_accounts]
