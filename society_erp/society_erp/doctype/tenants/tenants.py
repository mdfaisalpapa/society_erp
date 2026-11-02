# Copyright (c) 2026, Mohammed Faisal and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from society_erp.account_management import (
    deactivate_user_if_unused,
    ensure_linked_resident_account,
)


class Tenants(Document):
    def autoname(self):
        """Generate Tenant ID as <Flat Number>-T<Sequence>."""
        if not self.flat:
            frappe.throw("Flat number is required to generate the Tenant ID.")

        prefix = f"{self.flat}-T"
        existing_tenants = frappe.get_all(
            "Tenants", filters={"flat": self.flat}, pluck="name"
        )
        max_seq = 0

        for name in existing_tenants:
            if name.startswith(prefix):
                try:
                    seq = int(name.replace(prefix, "", 1))
                    max_seq = max(max_seq, seq)
                except ValueError:
                    pass

        self.name = f"{prefix}{max_seq + 1}"

    def after_insert(self):
        self.sync_tenant_user_account()

    def on_update(self):
        self.sync_tenant_user_account()

    def sync_tenant_user_account(self):
        """
        Create/reuse and link a User for an active Tenant.

        The Tenants row is inserted first; linked_user is populated after
        the User has been created or identified.
        """
        if self.active:
            ensure_linked_resident_account(
                self,
                role="Flat Tenant",
                display_name=self.tenant_name or self.flat,
            )
        else:
            deactivate_user_if_unused(self)
