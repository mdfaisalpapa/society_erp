import frappe
from frappe.model.document import Document


class ChannelIdentity(Document):
    def validate(self):
        if self.resident_email:
            self.resident_email = self.resident_email.strip().lower()
        if self.channel_user_id:
            self.channel_user_id = str(self.channel_user_id).strip()
