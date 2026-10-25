import frappe

def get_context(context):
    # 1. Security: Block unauthenticated users
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    user = frappe.session.user

    # 2. Fetch using 'email' instead of 'email_id'
    owner_record = frappe.db.get_value(
        "Owners", 
        {"linked_user": user, "active": 1}, 
        ["name", "flat", "owner_name", "mobile_no", "email"], 
        as_dict=True
    )
    
    if not owner_record:
        context.not_a_resident = True
        return context

    flat_id = owner_record.flat
    context.flat_number = flat_id
    context.owner_details = owner_record

    # 3. Fetch the Flat's permanent details from the Customer DocType
    if frappe.db.exists("Customer", flat_id):
        flat_doc = frappe.get_doc("Customer", flat_id)
        context.flat_details = {
            "block": flat_doc.get("custom_block"),
            "uds": flat_doc.get("custom_uds"),
            "eb_service_no": flat_doc.get("eb_service_no") or flat_doc.get("custom_eb_service_no"),
            "property_tax_no": flat_doc.get("property_tax_no") or flat_doc.get("custom_property_tax_no"),
            "corpus_fund": flat_doc.get("corpus_fund_contribution")
        }
    else:
        context.flat_details = {}

    return context
