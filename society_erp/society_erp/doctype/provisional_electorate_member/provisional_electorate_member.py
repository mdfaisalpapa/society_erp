import frappe
from frappe import _
from frappe.model.document import Document


class ProvisionalElectorateMember(Document):
    def validate(self):
        self._assert_parent_not_frozen("modify" if not self.is_new() else "add")

        if not self.masked_voter_name and self.owner_name:
            self.masked_voter_name = _mask_name(self.owner_name)

        if self.publication and self.flat_no:
            existing = frappe.db.get_value(
                "Provisional Electorate Member",
                {"publication": self.publication, "flat_no": self.flat_no, "name": ["!=", self.name or ""]},
                "name",
            )
            if existing:
                frappe.throw(
                    _("Flat {0} is already registered in publication {1}.").format(self.flat_no, self.publication),
                    frappe.DuplicateEntryError,
                )

    def on_trash(self):
        self._assert_parent_not_frozen("delete")

    def _assert_parent_not_frozen(self, action: str = "modify"):
        if not self.publication:
            return
        status = frappe.db.get_value("Electorate Publication", self.publication, "status")
        if status in ("Approved", "Superceded", "Superseded", "Archived"):
            frappe.throw(
                _(
                    "Cannot {0} provisional member: publication '{1}' is {2}. "
                    "Approved, superceded, and archived publications are immutable. "
                    "Create a new publication version instead."
                ).format(action, self.publication, status),
                frappe.ValidationError,
            )


def _mask_name(name: str) -> str:
    """Mask owner name for public/community directory display, e.g. John Doe -> J*** D**."""
    if not name or not name.strip():
        return "***"
    parts = name.strip().split()
    masked_parts = []
    for part in parts:
        if len(part) <= 1:
            masked_parts.append(part)
        elif len(part) == 2:
            masked_parts.append(part[0] + "*")
        else:
            masked_parts.append(part[0] + ("*" * (len(part) - 1)))
    return " ".join(masked_parts)
