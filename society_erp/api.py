import frappe
import io

@frappe.whitelist(allow_guest=True)
def generate_qr(passcode):
    """Generates a QR code image on the fly for WhatsApp unfurling."""
    if not passcode:
        frappe.throw("Passcode is required")
        
    import qrcode
        
    # Generate the QR Code data
    qr_data = f"verify_{passcode}"
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    # Create the image in memory
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    
    # Correctly instruct Frappe to serve the file directly to the browser
    frappe.response['filename'] = f"gatepass_{passcode}.png"
    frappe.response['filecontent'] = bio.getvalue()
    frappe.response['type'] = 'download'
    frappe.response['display_content_as'] = 'inline'

from frappe.utils.pdf import get_pdf
from frappe.utils import nowdate

from frappe.utils.pdf import get_pdf
from frappe.utils import nowdate

@frappe.whitelist()
def download_open_tickets_pdf():
    # 1. Fetch all open tickets
    tickets = frappe.get_all("Maintenance Ticket", 
        filters={"status": "Open"}, 
        fields=["name", "resident", "category", "description", "creation"],
        order_by="resident asc"
    )
    
    pm_categories = ["Handing Over", "Defects Rectification"]
    
    # 2. Split tickets into Maintenance vs Project Manager
    maint_data = {}
    pm_data = {}
    
    for t in tickets:
        flat = t.get("resident") or "Unknown"
        tower = flat.split("-")[0] if "-" in flat else "Unknown Tower"
        cat = t.get("category") or "Uncategorized"
        
        # Route to the correct dictionary
        target_dict = pm_data if cat in pm_categories else maint_data
        
        if tower not in target_dict: target_dict[tower] = {}
        if cat not in target_dict[tower]: target_dict[tower][cat] = []
        target_dict[tower][cat].append(t)
            
    # Helper function to generate the HTML blocks
    def generate_html_section(title, data_dict):
        if not data_dict:
            return f"<h2>{title}</h2><p style='text-align:center;'>No open tickets found.</p>"
            
        html = f"<h2>{title}</h2>"
        for tower in sorted(data_dict.keys()):
            html += f"<div class='tower-header'>🏢 Tower: {tower}</div>"
            for cat in sorted(data_dict[tower].keys()):
                html += f"<div class='cat-header'>📂 {cat}</div>"
                html += """
                <table>
                    <tr>
                        <th width="15%">Ticket ID</th>
                        <th width="15%">Flat</th>
                        <th width="70%">Description</th>
                    </tr>
                """
                for t in data_dict[tower][cat]:
                    desc = (t.get("description") or "").replace("\n", " ")
                    if len(desc) > 80: desc = desc[:80] + "..."
                    html += f"<tr><td>{t.get('name')}</td><td>{t.get('resident')}</td><td>{desc}</td></tr>"
                html += "</table>"
        return html

    # 3. Build the full HTML Template with a CSS Page Break
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Helvetica, Arial, sans-serif; }}
            h2 {{ text-align: center; color: #2c3e50; margin-bottom: 5px; margin-top: 0px; }}
            .date {{ text-align: center; color: #7f8c8d; font-size: 12px; margin-bottom: 20px; }}
            .tower-header {{ background-color: #2980b9; color: white; padding: 8px; font-size: 16px; margin-top: 20px; }}
            .cat-header {{ background-color: #ecf0f1; color: #2c3e50; padding: 6px; font-size: 14px; font-weight: bold; margin-top: 10px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 5px; }}
            th, td {{ border: 1px solid #bdc3c7; padding: 6px; text-align: left; font-size: 12px; }}
            th {{ background-color: #bdc3c7; }}
            .page-break {{ page-break-before: always; }}
        </style>
    </head>
    <body>
        <div class="date">Generated on: {nowdate()}</div>
    """
    
    # Add Standard Maintenance Tickets
    html += generate_html_section("Open Maintenance Tickets", maint_data)
    
    # Add the hard page break
    html += "<div class='page-break'></div>"
    
    # Add Project Manager Tickets
    html += generate_html_section("Open Project Manager Tickets (Defects & Handover)", pm_data)
                
    html += "</body></html>"
    
    # 4. Convert HTML to PDF and serve it as a standard download
    frappe.response['filename'] = f"Open_Tickets_{nowdate()}.pdf"
    frappe.response['filecontent'] = get_pdf(html)
    frappe.response['type'] = 'download'
