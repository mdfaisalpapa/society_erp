# Copyright (c) 2026, Society ERP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FacilityStaff(Document):
    def validate(self):
        if self.contact_number:
            self.contact_number = str(self.contact_number).strip().replace(" ", "").replace("-", "")
            if len(self.contact_number) == 12 and self.contact_number.startswith("91"):
                self.contact_number = self.contact_number[2:]
            elif len(self.contact_number) == 13 and self.contact_number.startswith("+91"):
                self.contact_number = self.contact_number[3:]
