# Copyright (c) 2026, Mohammed Faisal and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class STPChemicalLog(Document):
    def validate(self):
        curr = float(self.current_stock or 0.0)
        thresh = float(self.minimum_threshold or 0.0)
        if thresh > 0 and curr <= thresh:
            self.is_low_stock = 1
        else:
            self.is_low_stock = 0
