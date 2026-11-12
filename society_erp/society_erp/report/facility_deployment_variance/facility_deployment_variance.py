# Copyright (c) 2026, Society ERP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import nowdate


def execute(filters=None):
    filters = filters or {}
    target_date = filters.get("date") or nowdate()

    columns = [
        {"label": _("Shift"), "fieldname": "shift", "fieldtype": "Link", "options": "Facility Shift", "width": 180},
        {"label": _("Role"), "fieldname": "role", "fieldtype": "Data", "width": 160},
        {"label": _("Contract Quota"), "fieldname": "required_count", "fieldtype": "Int", "width": 120},
        {"label": _("Actual Deployed"), "fieldname": "actual_count", "fieldtype": "Int", "width": 120},
        {"label": _("Variance (Shortage)"), "fieldname": "variance", "fieldtype": "Int", "width": 140},
        {"label": _("Status"), "fieldname": "compliance_status", "fieldtype": "Data", "width": 120}
    ]

    # Get active contracts and their quotas
    contract_filters = {"status": "Active"}
    if filters.get("agency"):
        contract_filters["agency"] = filters.get("agency")

    contracts = frappe.get_all("Facility Contract", filters=contract_filters, fields=["name", "agency"])
    if not contracts:
        return columns, []

    data = []
    contract_names = [c.name for c in contracts]

    quotas = frappe.get_all(
        "Facility Contract Quota",
        filters={"parent": ("in", contract_names)},
        fields=["role", "shift", "required_count", "parent"]
    )

    for q in quotas:
        # Check actual attendance for this shift and role on target_date
        actual = frappe.db.count(
            "Facility Staff Attendance",
            {
                "attendance_date": target_date,
                "shift": q.shift,
                "role": q.role,
                "status": "Present"
            }
        )

        variance = actual - int(q.required_count or 0)
        status = "Compliant" if variance >= 0 else "Shortage"

        data.append({
            "shift": q.shift,
            "role": q.role,
            "required_count": int(q.required_count or 0),
            "actual_count": actual,
            "variance": variance,
            "compliance_status": status
        })

    return columns, data
