# Copyright (c) 2026, Society ERP and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class FacilityContract(Document):
    def validate(self):
        # Calculate total daily quota
        total = 0
        for q in (self.quotas or []):
            total += int(q.required_count or 0)
        self.total_daily_quota = total
