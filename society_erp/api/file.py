import base64
import frappe
from frappe import _
from frappe.utils.file_manager import save_file
from society_erp.api.utils import portal_api


@frappe.whitelist()
@portal_api
def attach_channel_file(
    attached_to_doctype: str,
    attached_to_name: str,
    file_name: str,
    file_content_b64: str,
    attached_to_field: str = None,
    is_private: int = 1,
) -> dict:
    """
    Receives base64-encoded media from universal_chatbot (Telegram photos, WhatsApp documents)
    and saves it securely via Frappe's file manager, linked to the given DocType and document name.

    :param attached_to_doctype: Target DocType name (e.g. 'Resident Vehicle', 'Maintenance Ticket')
    :param attached_to_name: Target document name/ID
    :param file_name: File name with extension (e.g. 'rc_document.jpg', 'bill.pdf')
    :param file_content_b64: Base64-encoded string representing the file payload
    :param attached_to_field: Target fieldname on the document (optional)
    :param is_private: 1 for private attachment, 0 for public
    :return: dict with file_url and file_name
    """
    if not attached_to_doctype or not attached_to_name:
        frappe.throw(_("Target DocType and Document Name are required."), frappe.ValidationError)

    if not file_name or not file_content_b64:
        frappe.throw(_("File name and file content are required."), frappe.ValidationError)

    # Verify target document exists
    if not frappe.db.exists(attached_to_doctype, attached_to_name):
        frappe.throw(
            _("Target document {0} ({1}) does not exist.").format(attached_to_doctype, attached_to_name),
            frappe.DoesNotExistError,
        )

    # Decode base64 payload
    try:
        file_bytes = base64.b64decode(file_content_b64)
    except Exception as e:
        frappe.throw(_("Invalid base64-encoded file content: {0}").format(str(e)), frappe.ValidationError)

    # Save file using Frappe native file manager
    file_doc = save_file(
        fname=file_name,
        content=file_bytes,
        dt=attached_to_doctype,
        dn=attached_to_name,
        is_private=int(is_private),
    )

    # If a specific field was targeted, update the document field directly
    if attached_to_field and frappe.get_meta(attached_to_doctype).has_field(attached_to_field):
        frappe.db.set_value(attached_to_doctype, attached_to_name, attached_to_field, file_doc.file_url)

    return {
        "file_url": file_doc.file_url,
        "file_name": file_doc.file_name,
        "attached_to_doctype": attached_to_doctype,
        "attached_to_name": attached_to_name,
    }
