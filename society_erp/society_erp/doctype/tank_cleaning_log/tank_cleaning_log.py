import frappe
from frappe.model.document import Document
from frappe.utils import add_months, getdate


class TankCleaningLog(Document):
    def validate(self):
        # Automatically schedule next due date in 6 months if not set
        if self.activity_date and not self.next_due_date:
            self.next_due_date = add_months(getdate(self.activity_date), 6)
