# Copyright (c) 2026, Mohammed Faisal and contributors
# For license information, please see license.txt

from datetime import datetime, timedelta
import frappe
from frappe import _
from frappe.utils import flt, nowdate, getdate

STP_STANDARD_CHEMICALS = [
    {
        "name": "Sodium Hypochlorite (Chlorine)",
        "unit": "Liters",
        "threshold": 50.0,
        "desc": "Disinfection of STP treated effluent before flushing and gardening"
    },
    {
        "name": "Alum / Polyaluminium Chloride (PAC)",
        "unit": "Kilograms (Kg)",
        "threshold": 40.0,
        "desc": "Coagulant for settling suspended solids & turbidity reduction in clarifier"
    },
    {
        "name": "Sodium Hydroxide (Caustic Soda)",
        "unit": "Kilograms (Kg)",
        "threshold": 25.0,
        "desc": "pH neutralization in biological aeration tanks"
    },
    {
        "name": "Hydrochloric Acid (HCl)",
        "unit": "Liters",
        "threshold": 20.0,
        "desc": "Acid dosing for pH correction & lime scale descaling"
    },
    {
        "name": "Urea / Bacterial Nutrients",
        "unit": "Kilograms (Kg)",
        "threshold": 25.0,
        "desc": "Nitrogen / microbial nutrient feed for MBBR / activated sludge bacteria"
    },
    {
        "name": "Filter Sand / Activated Carbon Media",
        "unit": "Bags (25Kg / 50Kg)",
        "threshold": 5.0,
        "desc": "Dual media and activated carbon filter top-up"
    }
]


@frappe.whitelist()
def log_stp_chemical_stock(chemical_name: str, current_stock: float, log_date: str = None,
                           minimum_threshold: float = None, daily_consumption: float = 0.0,
                           stock_received: float = 0.0, unit_of_measure: str = None,
                           stock_photo: str = None, supplier_or_invoice: str = None,
                           remarks: str = None) -> dict:
    """
    Records or updates daily STP chemical stock level.
    Sets is_low_stock if current_stock <= minimum_threshold to prevent stock out.
    """
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    if not chemical_name:
        frappe.throw(_("Chemical name is required."))

    cur_val = flt(current_stock)
    thresh_val = flt(minimum_threshold) if minimum_threshold is not None else 50.0
    
    # Auto-fill default threshold if not provided
    if thresh_val <= 0:
        for c in STP_STANDARD_CHEMICALS:
            if c["name"] == chemical_name:
                thresh_val = c["threshold"]
                break

    target_date = log_date or nowdate()

    doc = frappe.get_doc({
        "doctype": "STP Chemical Log",
        "chemical_name": chemical_name,
        "log_date": target_date,
        "unit_of_measure": unit_of_measure or "Liters",
        "current_stock": cur_val,
        "minimum_threshold": thresh_val,
        "is_low_stock": 1 if cur_val <= thresh_val else 0,
        "daily_consumption": flt(daily_consumption),
        "stock_received": flt(stock_received),
        "stock_photo": stock_photo,
        "supplier_or_invoice": supplier_or_invoice,
        "supervisor_in_charge": user,
        "remarks": remarks
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "name": doc.name,
        "chemical_name": doc.chemical_name,
        "current_stock": doc.current_stock,
        "is_low_stock": doc.is_low_stock,
        "message": _("STP chemical stock for {0} recorded ({1} {2}).").format(
            chemical_name, cur_val, doc.unit_of_measure
        )
    }


@frappe.whitelist()
def get_stp_chemical_dashboard() -> dict:
    """
    Returns latest stock status for all STP chemicals,
    identifying low stock warnings and non-data entry gaps for the committee.
    """
    user = frappe.session.user
    today = nowdate()
    today_dt = getdate(today)

    chemical_summary = []
    missing_entry_count = 0
    low_stock_count = 0

    for chem in STP_STANDARD_CHEMICALS:
        name = chem["name"]
        unit = chem["unit"]
        default_thresh = chem["threshold"]

        # Fetch latest entry for this chemical
        latest = frappe.get_all(
            "STP Chemical Log",
            filters={"chemical_name": name},
            fields=[
                "name", "chemical_name", "log_date", "unit_of_measure",
                "current_stock", "minimum_threshold", "is_low_stock",
                "daily_consumption", "stock_received", "stock_photo",
                "supervisor_in_charge", "supplier_or_invoice", "remarks", "creation"
            ],
            order_by="log_date desc, creation desc",
            limit=1
        )

        item_data = {
            "chemical_name": name,
            "unit": unit,
            "description": chem["desc"],
            "default_threshold": default_thresh,
            "has_entry": len(latest) > 0,
            "latest_record": None,
            "days_since_entry": None,
            "entry_missing_today": True,
            "is_stale_entry": False, # No entry for >= 2 days
            "current_stock": 0.0,
            "is_low_stock": False
        }

        if latest:
            rec = latest[0]
            item_data["latest_record"] = rec
            item_data["current_stock"] = flt(rec.current_stock)
            rec_date = getdate(rec.log_date) if rec.log_date else today_dt
            diff_days = (today_dt - rec_date).days
            item_data["days_since_entry"] = diff_days
            item_data["entry_missing_today"] = (diff_days > 0)
            item_data["is_stale_entry"] = (diff_days >= 2)
            
            thresh = flt(rec.minimum_threshold) or default_thresh
            is_low = (item_data["current_stock"] <= thresh) or (rec.is_low_stock == 1)
            item_data["is_low_stock"] = is_low
            item_data["threshold"] = thresh

            if item_data["entry_missing_today"]:
                missing_entry_count += 1
            if is_low:
                low_stock_count += 1
        else:
            # Never entered
            item_data["entry_missing_today"] = True
            item_data["is_stale_entry"] = True
            item_data["days_since_entry"] = 999
            item_data["threshold"] = default_thresh
            item_data["is_low_stock"] = True # zero stock
            missing_entry_count += 1
            low_stock_count += 1

        chemical_summary.append(item_data)

    # Recent history of 20 logs
    recent_logs = frappe.get_all(
        "STP Chemical Log",
        fields=[
            "name", "chemical_name", "log_date", "unit_of_measure",
            "current_stock", "minimum_threshold", "is_low_stock",
            "daily_consumption", "stock_received", "stock_photo",
            "supervisor_in_charge", "supplier_or_invoice", "remarks"
        ],
        order_by="log_date desc, creation desc",
        limit_page_length=25
    )

    return {
        "today_date": today,
        "chemicals": chemical_summary,
        "recent_logs": recent_logs,
        "missing_entry_count": missing_entry_count,
        "low_stock_count": low_stock_count,
        "total_monitored": len(STP_STANDARD_CHEMICALS)
    }
