# Copyright (c) 2026, Society ERP and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import time_diff_in_hours


class FacilityShift(Document):
    def validate(self):
        if self.start_time and self.end_time:
            # Calculate duration in hours
            diff = time_diff_in_hours(self.end_time, self.start_time)
            if diff < 0:
                diff += 24.0
                self.is_night_shift = 1
            self.duration_hours = round(diff, 2)
