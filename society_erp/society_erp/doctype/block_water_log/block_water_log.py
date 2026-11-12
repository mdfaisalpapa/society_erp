import frappe
from frappe.model.document import Document
from frappe.utils import time_diff_in_hours


class BlockWaterLog(Document):
    def validate(self):
        # Calculate domestic pump run hours
        if self.domestic_pump_start and self.domestic_pump_stop:
            self.domestic_run_hours = round(time_diff_in_hours(self.domestic_pump_stop, self.domestic_pump_start), 2)
        
        # Calculate flush pump run hours
        if self.flush_pump_start and self.flush_pump_stop:
            self.flush_run_hours = round(time_diff_in_hours(self.flush_pump_stop, self.flush_pump_start), 2)

        # Flag low water alert if level is critical
        if (self.domestic_level_ft is not None and self.domestic_level_ft < 2.5) or \
           (self.flush_level_ft is not None and self.flush_level_ft < 2.0):
            self.is_low_level_alert = 1
        else:
            self.is_low_level_alert = 0
