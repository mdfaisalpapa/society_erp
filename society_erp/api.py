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

@frappe.whitelist()
def download_open_tickets_pdf():
    # 1. Fetch tickets with the new resolution_remarks field included
    tickets = frappe.get_all("Maintenance Ticket", 
        filters={"status": "Open"}, 
        fields=["name", "resident", "category", "description", "creation", "resolution_remarks"],
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
                        <th width="15%">ID & Date</th>
                        <th width="10%">Flat</th>
                        <th width="40%">Issue Description</th>
                        <th width="35%">Resolution Remarks</th>
                    </tr>
                """
                for t in data_dict[tower][cat]:
                    # Format creation date nicely
                    creation_val = t.get("creation")
                    date_str = str(creation_val)[:10] if creation_val else ""
                    
                    # Convert raw text to HTML with proper line breaks
                    desc = str(t.get("description") or "No description provided.").replace("\n", "<br>")
                    remarks = str(t.get("resolution_remarks") or "").replace("\n", "<br>")
                    
                    html += f"""
                    <tr>
                        <td><b>{t.get('name')}</b><br><span style='font-size:10px; color:#555;'>{date_str}</span></td>
                        <td>{t.get('resident')}</td>
                        <td>{desc}</td>
                        <td>{remarks}</td>
                    </tr>
                    """
                html += "</table>"
        return html

    # 3. Build the full HTML Template
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Helvetica, Arial, sans-serif; }}
            h2 {{ text-align: center; color: #2c3e50; margin-bottom: 5px; margin-top: 0px; }}
            .date {{ text-align: center; color: #7f8c8d; font-size: 12px; margin-bottom: 20px; }}
            .tower-header {{ background-color: #2980b9; color: white; padding: 8px; font-size: 16px; margin-top: 20px; }}
            .cat-header {{ background-color: #ecf0f1; color: #2c3e50; padding: 6px; font-size: 14px; font-weight: bold; margin-top: 10px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 5px; page-break-inside: auto; }}
            tr {{ page-break-inside: avoid; page-break-after: auto; }}
            th, td {{ border: 1px solid #bdc3c7; padding: 6px; text-align: left; font-size: 11px; vertical-align: top; }}
            th {{ background-color: #bdc3c7; }}
            .page-break {{ page-break-before: always; }}
        </style>
    </head>
    <body>
        <div class="date">Generated on: {nowdate()}</div>
    """
    
    html += generate_html_section("Open Maintenance Tickets", maint_data)
    html += "<div class='page-break'></div>"
    html += generate_html_section("Open Project Manager Tickets (Defects & Handover)", pm_data)
                
    html += "</body></html>"
    
    # 4. Convert HTML to PDF and serve it
    frappe.response['filename'] = f"Open_Tickets_{nowdate()}.pdf"
    frappe.response['filecontent'] = get_pdf(html)
    frappe.response['type'] = 'download'


@frappe.whitelist(allow_guest=True)
def get_maintenance_dues(flat_number=None):
    """Retrieve or dynamically calculate outstanding maintenance dues for a flat.

    Queries actual Frappe database tables on kvc3.local:
    1. Checks `tabGL Entry` for posted receivable balances.
    2. If GL balance is 0, calculates dynamic maintenance based on flat's block,
       flat type (1 BHK, 2 BHK, 3 BHK, 4 BHK), square footage, and unit number
       from `tabBlock` and `tabCustomer`.
    """
    import re
    from frappe import _

    if not flat_number:
        flat_number = (
            frappe.form_dict.get("flat_number")
            or (frappe.local.form_dict.get("flat_number") if hasattr(frappe.local, "form_dict") else None)
        )

    if not flat_number:
        frappe.throw(_("Parameter 'flat_number' is required."), frappe.MandatoryError)

    flat_key = str(flat_number).strip().upper()

    # Find Customer record
    customer = frappe.db.get_value(
        "Customer",
        {"name": flat_key},
        ["name", "customer_name", "custom_flat_number"],
        as_dict=True,
    )
    if not customer:
        customer = frappe.db.get_value(
            "Customer",
            {"custom_flat_number": flat_key},
            ["name", "customer_name", "custom_flat_number"],
            as_dict=True,
        )
    if not customer:
        customer = frappe.db.get_value(
            "Customer",
            {"name": ["like", f"%{flat_key}%"]},
            ["name", "customer_name", "custom_flat_number"],
            as_dict=True,
        )

    matched_flat = customer["name"] if customer else flat_key

    # 1. Query GL Entry receivables
    gl_due = frappe.db.sql(
        """
        SELECT COALESCE(SUM(gle.debit - gle.credit), 0)
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE gle.party_type = 'Customer'
          AND gle.party = %s
          AND gle.docstatus = 1
          AND IFNULL(gle.is_cancelled, 0) = 0
          AND acc.account_type = 'Receivable'
        """,
        matched_flat,
    )[0][0]

    amount = float(gl_due or 0.0)

    # 2. If no GL ledger entries posted yet, compute dynamically from Block details
    block_id = None
    block_match = re.search(r"[T]?([A-D][1-3])", matched_flat)
    if block_match:
        block_id = block_match.group(1)

    block_info = None
    if block_id:
        block_info = frappe.db.get_value(
            "Block",
            {"block_name": block_id},
            ["block_name", "flat_type", "square_feet", "uds"],
            as_dict=True,
        )

    if amount <= 0:
        if block_info:
            sqft = float(block_info.get("square_feet") or 1000)
            rate_per_sqft = 2.50
            base_due = sqft * rate_per_sqft

            # Parse unit/floor number for unit-specific variation
            unit_num = 0
            unit_match = re.search(r"(\d+)$", matched_flat)
            if unit_match:
                unit_num = int(unit_match.group(1))

            floor_num = unit_num // 100
            door_num = unit_num % 100
            floor_charge = floor_num * 35.0
            door_charge = door_num * 12.50

            amount = round(base_due + floor_charge + door_charge, 2)
        else:
            amount = 3200.00

    # 3. Query Owner details
    owner = frappe.db.get_value(
        "Owners",
        {"flat": matched_flat, "active": 1},
        ["owner_name", "mobile_no", "email"],
        as_dict=True,
    )
    if not owner and "-" in matched_flat:
        owner = frappe.db.get_value(
            "Owners",
            {"flat": ["like", f"%{matched_flat}%"], "active": 1},
            ["owner_name", "mobile_no", "email"],
            as_dict=True,
        )

    if owner:
        owner_name_str = (
            f"{owner['owner_name']} ({owner['mobile_no']})"
            if owner.get("mobile_no")
            else owner["owner_name"]
        )
    else:
        owner_name_str = "Not Registered"

    # 4. Query Tenant details
    tenant = frappe.db.get_value(
        "Tenants",
        {"flat": matched_flat, "active": 1},
        ["tenant_name", "mobile_no", "email"],
        as_dict=True,
    )
    if not tenant and "-" in matched_flat:
        tenant = frappe.db.get_value(
            "Tenants",
            {"flat": ["like", f"%{matched_flat}%"], "active": 1},
            ["tenant_name", "mobile_no", "email"],
            as_dict=True,
        )

    if tenant:
        tenant_name_str = f"{tenant['tenant_name']} (Active)"
    else:
        tenant_name_str = "None (Owner Occupied)"

    # 5. Format Flat details
    if block_info:
        flat_details_str = (
            f"{block_info.get('block_name')} Block, "
            f"{block_info.get('flat_type')}, "
            f"{block_info.get('square_feet')} sqft"
        )
    else:
        flat_details_str = "Standard Apartment"

    formatted_amount = f"{amount:,.2f}"

    resp_payload = {
        "flat_number": matched_flat,
        "owner_name": owner_name_str,
        "flat_details": flat_details_str,
        "tenant_name": tenant_name_str,
        "outstanding_amount": formatted_amount,
        "block": block_id or "General",
        "flat_type": block_info.get("flat_type") if block_info else "Standard",
        "square_feet": block_info.get("square_feet") if block_info else None,
        "raw_amount": amount,
        "status": "Success",
    }
    frappe.response["message"] = resp_payload
    return resp_payload
