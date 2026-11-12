# Copyright (c) 2026, Society ERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FacilityStaff(Document):
    def validate(self):
        # Auto-set status based on approval
        if self.approval_status == "Pending" and not self.status:
            self.status = "Inactive"
        elif self.approval_status == "Rejected":
            self.status = "Inactive"
        elif self.approval_status == "Approved" and self.status == "Inactive" and not self.blacklisted_reason:
            self.status = "Active"

        if self.contact_number:
            self.contact_number = str(self.contact_number).strip().replace(" ", "").replace("-", "")
            if len(self.contact_number) == 12 and self.contact_number.startswith("91"):
                self.contact_number = self.contact_number[2:]
            elif len(self.contact_number) == 13 and self.contact_number.startswith("+91"):
                self.contact_number = self.contact_number[3:]
