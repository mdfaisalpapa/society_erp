import frappe
import io

@frappe.whitelist(allow_guest=True)
def generate_qr(passcode):
    """Generates a QR code image on the fly for WhatsApp unfurling."""
    if not passcode:
        frappe.throw("Passcode is required")
        
    try:
        import qrcode
    except ImportError:
        frappe.throw("qrcode library is not installed on the Frappe server.")
        
    # Generate the QR Code data
    qr_data = f"verify_{passcode}"
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    # Create the image in memory
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    
    # Instruct Frappe to return a direct image instead of a JSON response
    frappe.response['filename'] = f"gatepass_{passcode}.png"
    frappe.response['filecontent'] = bio.getvalue()
    frappe.response['type'] = 'image/png'
