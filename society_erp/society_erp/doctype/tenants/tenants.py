# Copyright (c) 2026, Mohammed Faisal and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import validate_email_address

class Tenants(Document):
    def autoname(self):
        """Generates the ID format: <Flat Number>-T<Sequence> (e.g., TA1-101-T1)"""
        if not self.flat:
            frappe.throw("Flat number is required to generate the Tenant ID.")
            
        prefix = f"{self.flat}-T"
        
        # Find the highest existing sequence number for this specific flat
        existing_tenants = frappe.get_all("Tenants", filters={"flat": self.flat}, pluck="name")
        max_seq = 0
        
        for name in existing_tenants:
            if name.startswith(prefix):
                try:
                    seq = int(name.replace(prefix, ""))
                    if seq > max_seq:
                        max_seq = seq
                except ValueError:
                    pass
                    
        self.name = f"{prefix}{max_seq + 1}"

    def after_insert(self):
        self.sync_tenant_user_account()

    def on_update(self):
        self.sync_tenant_user_account()

    def sync_tenant_user_account(self):
        """Creates or disables the tenant User account on lease creation or vacancy."""
        if not self.email:
            return

        raw_email = self.email.strip().lower()
        email = validate_email_address(raw_email, throw=False)
        if not email:
            return

        role = "Flat Tenant"
        first_name = self.tenant_name or self.flat

        # Case 1: Tenant is Active -> Provision account
        if self.active == 1:
            if not frappe.db.exists("User", email):
                user = frappe.new_doc("User")
                user.email = email
                user.first_name = first_name
                user.enabled = 1
                user.send_welcome_email = 1  
                user.append("roles", {"role": role})
                user.insert(ignore_permissions=True)
            else:
                user_doc = frappe.get_doc("User", email)
                user_doc.enabled = 1
                if not any(r.role == role for r in user_doc.roles):
                    user_doc.add_roles(role)
                else:
                    user_doc.save(ignore_permissions=True)

        # Case 2: Tenant Vacates -> Disable user login
        elif self.active == 0:
            if frappe.db.exists("User", email):
                other_active_tenants = frappe.db.count("Tenants", filters={"email": email, "active": 1, "name": ["!=", self.name]})
                other_active_owners = frappe.db.count("Owners", filters={"email": email, "active": 1})
                
                if other_active_tenants == 0 and other_active_owners == 0:
                    frappe.db.set_value("User", email, "enabled", 0)
