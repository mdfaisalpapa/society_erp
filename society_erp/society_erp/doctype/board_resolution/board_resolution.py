import frappe
from frappe.model.document import Document
from frappe import _

class BoardResolution(Document):
    def before_submit(self):
        if not self.get("signatories"):
            frappe.throw(_("You must add at least one Committee Member to sign this resolution."))

        pending_members = []
        for row in self.get("signatories"):
            if row.signature_status not in ["Signed", "Declined"]:
                pending_members.append(row.signatory)
        
        if pending_members:
            members_list = ", ".join(pending_members)
            frappe.throw(_(f"Cannot submit yet. All members must either sign or decline first: <b>{members_list}</b>"))
            
        # Ensure final submit aligns with status
        if self.status not in ["Passed", "Rejected"]:
            self.status = "Passed"

@frappe.whitelist()
def sign_resolution(docname, action, rejection_reason=None):
    doc = frappe.get_doc("Board Resolution", docname)
    current_user = frappe.session.user
    
    if action not in ["Signed", "Declined"]:
        frappe.throw(_("Invalid action."))
        
    if action == "Declined" and not rejection_reason:
        frappe.throw(_("Please provide a reason for declining this resolution."))
        
    user_found = False
    
    for row in doc.get("signatories"):
        member_user = frappe.db.get_value("Committee Member", row.signatory, "member_name")
        
        if member_user == current_user:
            user_found = True
            if row.signature_status in ["Signed", "Declined"]:
                frappe.throw(_(f"You have already responded to this resolution (Status: {row.signature_status})."))
            
            row.signature_status = action
            row.timestamp = frappe.utils.now_datetime()
            row.rejection_reason = rejection_reason if action == "Declined" else None
            
    if not user_found:
        frappe.throw(_("You are not authorized to sign this specific resolution."))
        
    # --- 51% MAJORITY CHECK ---
    total_signatories = len(doc.get("signatories"))
    if total_signatories > 0:
        signed_count = sum(1 for r in doc.get("signatories") if r.signature_status == "Signed")
        declined_count = sum(1 for r in doc.get("signatories") if r.signature_status == "Declined")
        
        # Update the status text, but leave docstatus = 0 so others can still vote
        if (signed_count / total_signatories) >= 0.51:
            doc.status = "Passed"
        elif (declined_count / total_signatories) >= 0.51:
            doc.status = "Rejected"
            
    doc.save(ignore_permissions=True)
    return "Success"

@frappe.whitelist()
def get_active_committee_members():
    members = frappe.get_all(
        "Committee Member",
        filters={"status": "Active"},
        fields=["name", "member_name", "designation"]
    )
    
    for m in members:
        full_name = frappe.db.get_value("User", m.member_name, "full_name")
        m.signatory_name = full_name if full_name else m.member_name
        
        desig_name = frappe.db.get_value("Designation", m.designation, "custom_designation_full_name")
        m.designation_name = desig_name if desig_name else m.designation
        
    return members

# --- PERMISSION & VISIBILITY RULES ---
def get_permission_query_conditions(user):
    if not user:
        user = frappe.session.user
    # System Managers / Administrators can see everything
    if "System Manager" in frappe.get_roles(user) or user == "Administrator":
        return None
    
    # Committee members only see resolutions if status is Circulated, or if they created it
    return f"(`tabBoard Resolution`.status = 'Circulated' OR `tabBoard Resolution`.owner = '{user}')"

def has_permission(doc, ptype="read", user=None):
    if not user:
        user = frappe.session.user
    if "System Manager" in frappe.get_roles(user) or user == "Administrator":
        return True
    if doc.owner == user:
        return True
    # Visible to others only when circulated
    if doc.status == "Circulated":
        return True
    return False