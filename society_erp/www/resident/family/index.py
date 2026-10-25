import frappe

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect
    from society_erp.api.resident_family import _current_resident, _relationship_options
    try:
        resident = _current_resident()
    except Exception:
        context.not_a_resident = True
        return context
    context.not_a_resident = False
    context.flat_number = resident["flat"]
    context.resident_name = resident.get("name")
    context.resident_type = resident.get("type")
    context.can_manage_family = True
    context.relationship_options = _relationship_options()
    proof_field = frappe.get_meta("Family Members").get_field("id_proof_type")
    context.id_proof_options = [x.strip() for x in (proof_field.options or "").splitlines() if x.strip()] if proof_field else []
    context.active_members = frappe.get_all("Family Members", filters={"parent_flat": resident["flat"], "status": "Active"}, fields=["name", "member_name", "relationship", "mobile_no", "id_proof_type", "id_proof_document", "registration_status"], order_by="member_name asc")
    context.inactive_members = frappe.get_all("Family Members", filters={"parent_flat": resident["flat"], "status": "Inactive"}, fields=["name", "member_name", "relationship", "mobile_no", "id_proof_type", "id_proof_document", "registration_status"], order_by="member_name asc")
    return context
