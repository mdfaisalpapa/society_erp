# Copyright (c) 2026, Mohammed Faisal and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import validate_email_address

class Owners(Document):
    def autoname(self):
        """Generates the ID format: <Flat Number>-O<Sequence> (e.g., TA1-101-O1)"""
        if not self.flat:
            frappe.throw("Flat number is required to generate the Owner ID.")
            
        prefix = f"{self.flat}-O"
        
        # Find the highest existing sequence number for this specific flat
        existing_owners = frappe.get_all("Owners", filters={"flat": self.flat}, pluck="name")
        max_seq = 0
        
        for name in existing_owners:
            if name.startswith(prefix):
                try:
                    seq = int(name.replace(prefix, ""))
                    if seq > max_seq:
                        max_seq = seq
                except ValueError:
                    pass
                    
        self.name = f"{prefix}{max_seq + 1}"

    def after_insert(self):
        self.sync_user_account()

    def on_update(self):
        self.sync_user_account()

    def sync_user_account(self):
        """Creates or updates the linked User account based on active status and email."""
        if not self.email:
            return

        raw_email = self.email.strip().lower()
        email = validate_email_address(raw_email, throw=False)
        if not email:
            return

        role = "Flat Owner"
        first_name = self.owner_name or self.flat

        # Case 1: Owner is Active -> Ensure User exists and is enabled
        if self.active == 1:
            if not frappe.db.exists("User", email):
                user = frappe.new_doc("User")
                user.email = email
                user.first_name = first_name
                user.enabled = 1
                user.send_welcome_email = 1  
                user.append("roles", {"role": role})
                user.insert(ignore_permissions=True)
                user_id = user.name
            else:
                user_id = email
                user_doc = frappe.get_doc("User", user_id)
                user_doc.enabled = 1  
                if not any(r.role == role for r in user_doc.roles):
                    user_doc.add_roles(role)
                else:
                    user_doc.save(ignore_permissions=True)

            if self.linked_user != user_id:
                frappe.db.set_value("Owners", self.name, "linked_user", user_id, update_modified=False)

        # Case 2: Owner is Deactivated -> Disable the User account
        elif self.active == 0:
            if frappe.db.exists("User", email):
                other_active_owners = frappe.db.count("Owners", filters={"email": email, "active": 1, "name": ["!=", self.name]})
                other_active_tenants = frappe.db.count("Tenants", filters={"email": email, "active": 1})
                
                if other_active_owners == 0 and other_active_tenants == 0:
                    frappe.db.set_value("User", email, "enabled", 0)
