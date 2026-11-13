import frappe
from frappe.model.document import Document
from frappe.utils import add_months, getdate


class FacilityAMCLog(Document):
    def validate(self):
        # Auto-compute next service due date if not provided (default +3 months for quarterly AMC)
        if self.service_date and not self.next_service_due_date:
            self.next_service_due_date = add_months(getdate(self.service_date), 3)
