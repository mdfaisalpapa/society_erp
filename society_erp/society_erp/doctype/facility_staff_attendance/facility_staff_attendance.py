# Copyright (c) 2026, Society ERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import time_diff_in_hours


class FacilityStaffAttendance(Document):
    def validate(self):
        # Auto-compute hours worked and overtime
        if self.in_time and self.out_time:
            diff = time_diff_in_hours(self.out_time, self.in_time)
            if diff < 0:
                diff += 24.0
            self.hours_worked = round(diff, 2)
            
            # Determine overtime if exceeds 8 hours or shift duration
            shift_dur = 8.0
            if self.shift:
                dur = frappe.db.get_value("Facility Shift", self.shift, "duration_hours")
                if dur:
                    shift_dur = float(dur)
            
            if self.hours_worked > shift_dur:
                self.overtime_hours = round(self.hours_worked - shift_dur, 2)
            else:
                self.overtime_hours = 0.0
