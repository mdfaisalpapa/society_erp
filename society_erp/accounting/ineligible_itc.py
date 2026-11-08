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
    Sets ineligibility reason if any item is marked ineligible for ITC.
    """
    if not is_unregistered_society(doc):
        return

    has_ineligible = any(item.get("is_ineligible_for_itc") for item in doc.get("items", []))
    if has_ineligible:
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
    For unregistered societies: processes Ineligible ITC reversing Input GST and allocating to item expense accounts.
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

    return gl_entries


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

    return gl_entries
