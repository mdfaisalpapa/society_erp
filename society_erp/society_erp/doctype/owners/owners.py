# Copyright (c) 2026, Mohammed Faisal and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from society_erp.account_management import (
    deactivate_user_if_unused,
    ensure_linked_resident_account,
)


class Owners(Document):
    def autoname(self):
        """Generate Owner ID as <Flat Number>-O<Sequence>."""
        if not self.flat:
            frappe.throw("Flat number is required to generate the Owner ID.")

        prefix = f"{self.flat}-O"
        existing_owners = frappe.get_all(
            "Owners", filters={"flat": self.flat}, pluck="name"
        )
        max_seq = 0

        for name in existing_owners:
            if name.startswith(prefix):
                try:
                    seq = int(name.replace(prefix, "", 1))
                    max_seq = max(max_seq, seq)
                except ValueError:
                    pass

        self.name = f"{prefix}{max_seq + 1}"

    def after_insert(self):
        self.sync_user_account()

    def on_update(self):
        self.sync_user_account()

    def on_trash(self):
        # Do not disable a User merely because an Owner row is deleted.
        # Deactivation is handled through the Active checkbox workflow.
        pass

    def sync_user_account(self):
        """
        Create/reuse and link a User for an active Owner.

        The Owners row is already inserted when after_insert runs, so the
        linked_user field can safely be populated at this point.
        """
        if self.active:
            ensure_linked_resident_account(
                self,
                role="Flat Owner",
                display_name=self.owner_name or self.flat,
            )
        else:
            deactivate_user_if_unused(self)
