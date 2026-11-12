# Copyright (c) 2026, Society ERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import date_diff, getdate


class FacilityInvoiceReconciliation(Document):
    def validate(self):
        self.calculate_reconciliation()

    def calculate_reconciliation(self):
        if self.from_date and self.to_date:
            days = date_diff(self.to_date, self.from_date) + 1
            self.total_calendar_days = max(days, 0)
        else:
            self.total_calendar_days = 0

        # Fetch contract quota if contract is selected
        if self.contract:
            quota = frappe.db.get_value("Facility Contract", self.contract, "total_daily_quota")
            self.contracted_daily_quota = int(quota or 0)
        else:
            self.contracted_daily_quota = 0

        self.expected_man_days = self.contracted_daily_quota * self.total_calendar_days

        # Roll up verified attendance records for this agency within the date range
        if self.agency and self.from_date and self.to_date:
            att_records = frappe.db.sql(
                """
                SELECT COUNT(name) as present_count, COALESCE(SUM(overtime_hours), 0) as total_ot
                FROM `tabFacility Staff Attendance`
                WHERE agency = %s
                  AND attendance_date BETWEEN %s AND %s
                  AND status = 'Present'
                """,
                (self.agency, self.from_date, self.to_date),
                as_dict=True
            )

            if att_records:
                self.actual_present_man_days = int(att_records[0].present_count or 0)
                self.total_overtime_hours = float(att_records[0].total_ot or 0.0)
            else:
                self.actual_present_man_days = 0
                self.total_overtime_hours = 0.0
        else:
            self.actual_present_man_days = 0
            self.total_overtime_hours = 0.0

        # Calculate shortage
        shortage = self.expected_man_days - self.actual_present_man_days
        self.shortage_man_days = max(shortage, 0)

        # Financial Deductions
        rate_penalty = float(self.penalty_per_shortage_day or 0.0)
        self.shortage_deduction_amount = round(self.shortage_man_days * rate_penalty, 2)

        base_val = float(self.contract_monthly_amount or 0.0)
        shortage_ded = float(self.shortage_deduction_amount or 0.0)
        other_ded = float(self.other_deductions or 0.0)
        ot_pay = float(self.overtime_payout_amount or 0.0)

        self.net_approved_payable = max(round(base_val - shortage_ded - other_ded + ot_pay, 2), 0.0)
