import re

import frappe
from frappe import _
from frappe.utils.file_manager import save_file

DOCTYPE = "Family Members"
MAX_UPLOAD_SIZE = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}

def _relationship_options():
    meta = frappe.get_meta("Family Members")
    field = meta.get_field("relationship")

    if not field or not field.options:
        return []

    return [
        option.strip()
        for option in field.options.splitlines()
        if option.strip()
    ]
def _meta():
    return frappe.get_meta(DOCTYPE)


def _has_field(fieldname):
    return _meta().has_field(fieldname)


def _options(fieldname):
    field = _meta().get_field(fieldname)
    return [x.strip() for x in (field.options or "").splitlines() if x.strip()] if field else []


def _current_resident():
    """Resolve the logged-in user to an active tenant or owner flat."""
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in to continue."), frappe.PermissionError)

    user = frappe.session.user
    email = (user or "").strip().lower()
    tenants = frappe.get_all(
        "Tenants", filters={"active": 1},
        fields=["name", "flat", "tenant_name", "email"], order_by="flat asc"
    )
    tenant = next((r for r in tenants if r.email and r.email.strip().lower() == email), None)
    if tenant and tenant.flat:
        return {"flat": tenant.flat, "type": "Tenant", "name": tenant.tenant_name}

    owners = frappe.get_all(
        "Owners", filters={"active": 1},
        fields=["name", "flat", "owner_name", "email"], order_by="flat asc"
    )
    owner = next((r for r in owners if
                  (r.email and r.email.strip().lower() == email) or r.name == user), None)
    if owner and owner.flat:
        return {"flat": owner.flat, "type": "Owner", "name": owner.owner_name}

    frappe.throw(_("Your login is not linked to an active flat."), frappe.PermissionError)


def _get_member_for_flat(member_id, flat):
    if not member_id or not frappe.db.exists(DOCTYPE, {"name": member_id, "parent_flat": flat}):
        frappe.throw(_("Family member not found for your flat."), frappe.PermissionError)
    return frappe.get_doc(DOCTYPE, member_id)


def _validate(member_name, relationship, mobile_no, id_proof_type):
    member_name = (member_name or "").strip()
    relationship = (relationship or "").strip()
    mobile_no = (mobile_no or "").strip()
    id_proof_type = (id_proof_type or "").strip()

    if not member_name:
        frappe.throw(_("Please enter the family member's name."))
    if len(member_name) > 140:
        frappe.throw(_("Name must be 140 characters or fewer."))
    if relationship not in _options("relationship"):
        frappe.throw(_("Please select a valid relationship."))
    if not mobile_no:
        frappe.throw(_("Mobile number is mandatory."))
    # Require an international number with country code, e.g. +919876543210.
    normalized = re.sub(r"[\s()-]", "", mobile_no)
    if not re.fullmatch(r"\+[1-9]\d{7,14}", normalized):
        frappe.throw(_("Enter a valid mobile number including country code, e.g. +919876543210."))
    if not id_proof_type:
        frappe.throw(_("ID proof type is mandatory."))
    if id_proof_type not in _options("id_proof_type"):
        frappe.throw(_("Please select a valid ID proof type."))
    return member_name, relationship, normalized, id_proof_type


def _reset_verification(doc):
    if _has_field("registration_status"):
        doc.registration_status = "Pending"
    if _has_field("verified_by"):
        doc.verified_by = None
    if _has_field("verification_date"):
        doc.verification_date = None


def _member_fields():
    wanted = ["name", "parent_flat", "member_name", "relationship", "mobile_no", "status",
              "registration_status", "id_proof_type", "id_proof_document", "verified_by", "verification_date"]
    return [field for field in wanted if _has_field(field)]


@frappe.whitelist()
def get_family_members():
    resident = _current_resident()
    fields = _member_fields()
    return {
        "flat_number": resident["flat"],
        "resident_type": resident["type"],
        "can_manage": True,
        "relationships": _options("relationship"),
        "id_proof_types": _options("id_proof_type"),
        "active": frappe.get_all(DOCTYPE, filters={"parent_flat": resident["flat"], "status": "Active"},
                                  fields=fields, order_by="member_name asc"),
        "inactive": frappe.get_all(DOCTYPE, filters={"parent_flat": resident["flat"], "status": "Inactive"},
                                    fields=fields, order_by="member_name asc"),
    }


@frappe.whitelist(methods=["POST"])
def add_family_member(member_name, relationship, mobile_no="", id_proof_type=""):
    resident = _current_resident()
    member_name, relationship, mobile_no, id_proof_type = _validate(
        member_name, relationship, mobile_no, id_proof_type
    )
    values = {
        "doctype": DOCTYPE, "parent_flat": resident["flat"], "member_name": member_name,
        "relationship": relationship, "mobile_no": mobile_no, "id_proof_type": id_proof_type,
        "status": "Active",
    }
    if _has_field("registration_status"):
        values["registration_status"] = "Pending"
    doc = frappe.get_doc(values)
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "message": _("Family member added. Upload the required ID proof to complete registration.")}


@frappe.whitelist(methods=["POST"])
def update_family_member(member_id, member_name, relationship, mobile_no="", id_proof_type=""):
    resident = _current_resident()
    member_name, relationship, mobile_no, id_proof_type = _validate(
        member_name, relationship, mobile_no, id_proof_type
    )
    doc = _get_member_for_flat(member_id, resident["flat"])
    doc.member_name = member_name
    doc.relationship = relationship
    doc.mobile_no = mobile_no
    if _has_field("id_proof_type"):
        doc.id_proof_type = id_proof_type
    if _has_field("id_proof_document") and doc.get("id_proof_document"):
        _reset_verification(doc)
    doc.save(ignore_permissions=True)
    return {"message": _("Family member updated. Upload an ID proof if one is not already attached.")}


def _set_status(member_id, status):
    resident = _current_resident()
    doc = _get_member_for_flat(member_id, resident["flat"])
    doc.status = status
    doc.save(ignore_permissions=True)
    return {"message": _("Family member status updated."), "status": status}


@frappe.whitelist(methods=["POST"])
def deactivate_family_member(member_id):
    return _set_status(member_id, "Inactive")


@frappe.whitelist(methods=["POST"])
def reactivate_family_member(member_id):
    return _set_status(member_id, "Active")


@frappe.whitelist(methods=["POST"])
def delete_family_member(member_id):
    resident = _current_resident()
    doc = _get_member_for_flat(member_id, resident["flat"])
    # Remove the attached proof file too, if present, after verifying the member's flat.
    file_url = doc.get("id_proof_document") if _has_field("id_proof_document") else None
    doc.delete(ignore_permissions=True)
    if file_url:
        file_name = frappe.db.get_value("File", {"file_url": file_url, "attached_to_doctype": DOCTYPE,
                                                  "attached_to_name": member_id}, "name")
        if file_name:
            frappe.delete_doc("File", file_name, ignore_permissions=True, force=True)
    return {"message": _("Family member permanently deleted.")}


@frappe.whitelist(methods=["POST"])
def upload_id_proof(member_id):
    """Save a private ID proof after checking that the member belongs to this resident's flat."""
    resident = _current_resident()
    doc = _get_member_for_flat(member_id, resident["flat"])
    uploaded = frappe.request.files.get("file") if getattr(frappe, "request", None) else None
    if not uploaded:
        frappe.throw(_("Choose an ID proof file to upload."))

    filename = (uploaded.filename or "").strip()
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        frappe.throw(_("Only PDF, JPG and PNG files are allowed."))
    content = uploaded.read()
    if not content:
        frappe.throw(_("The uploaded file is empty."))
    if len(content) > MAX_UPLOAD_SIZE:
        frappe.throw(_("The ID proof file must be 5 MB or smaller."))
    if not _has_field("id_proof_document"):
        frappe.throw(_("The ID Proof Document field is missing from Family Members."))

    # save_file validates access to the linked DocType. We temporarily use the
    # Administrator identity only for this already-authorized, flat-checked upload.
    # Always restore the session user, even if file insertion fails.
    original_user = frappe.session.user
    try:
        frappe.set_user("Administrator")
        file_doc = save_file(filename, content, DOCTYPE, doc.name, is_private=1, df="id_proof_document")
    finally:
        frappe.set_user(original_user)

    doc = _get_member_for_flat(member_id, resident["flat"])
    doc.id_proof_document = file_doc.file_url
    _reset_verification(doc)
    doc.save(ignore_permissions=True)
    return {"file_url": file_doc.file_url, "message": _("ID proof uploaded privately. Verification is pending.")}
