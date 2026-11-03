import io
from pathlib import Path
from urllib.parse import urlencode
from xml.sax.saxutils import escape

import frappe
from frappe import _
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

from pyhanko.sign import signers
from pyhanko.sign.fields import SigFieldSpec
from pyhanko.sign.signers import PdfSignatureMetadata
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter


def _get_signer():
    """Load the Association's signing certificate and private key."""

    signing_dir = Path.home() / ".config" / "society_erp" / "pdf-signing"

    key_file = signing_dir / "voting-pdf-private.pem"
    cert_file = signing_dir / "voting-pdf-cert.pem"
    passphrase_file = signing_dir / "passphrase"

    for path in (key_file, cert_file, passphrase_file):
        if not path.is_file():
            frappe.throw(
                _("PDF signing configuration is missing: {0}").format(path.name)
            )

    passphrase = passphrase_file.read_text().strip()

    return signers.SimpleSigner.load(
        key_file=str(key_file),
        cert_file=str(cert_file),
        key_passphrase=passphrase.encode("utf-8"),
    )



def _make_unsigned_pdf(receipt):
    """Create the unsigned voting receipt with QR and readable hash."""

    from reportlab.platypus import Flowable
    from reportlab.graphics.barcode import qr
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics import renderPDF

    buffer = io.BytesIO()
    page_width, _ = A4

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReceiptTitle",
        parent=styles["Title"],
        fontSize=16,
        leading=20,
        alignment=1,
        spaceAfter=5 * mm,
    ))
    styles.add(ParagraphStyle(
        name="ReceiptNote",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#555555"),
    ))
    styles.add(ParagraphStyle(
        name="ReceiptHash",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=7,
        leading=10,
        wordWrap="CJK",
    ))

    class GreenTick(Flowable):
        def __init__(self):
            super().__init__()
            self.width = 8 * mm
            self.height = 8 * mm

        def draw(self):
            self.canv.setStrokeColor(colors.HexColor("#198754"))
            self.canv.setLineWidth(2.5)
            self.canv.setLineCap(1)
            self.canv.line(1 * mm, 4 * mm, 3.2 * mm, 1.8 * mm)
            self.canv.line(3.2 * mm, 1.8 * mm, 7 * mm, 7 * mm)


    class ReceiptQR(Flowable):
        def __init__(self, value, size=25 * mm):
            super().__init__()
            self.value = value
            self.width = size
            self.height = size

        def draw(self):
            widget = qr.QrCodeWidget(self.value)
            x1, y1, x2, y2 = widget.getBounds()
            drawing = Drawing(
                self.width,
                self.height,
                transform=[
                    self.width / (x2 - x1), 0, 0,
                    self.height / (y2 - y1), 0, 0,
                ],
            )
            drawing.add(widget)
            renderPDF.draw(drawing, self.canv, 0, 0)

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=38 * mm,
    )

    story = [
        Paragraph("KENDRIYA VIHAR CHENNAI PHASE III AOA", styles["Heading2"]),
        Paragraph("VOTING RECEIPT", styles["ReceiptTitle"]),
        Paragraph(
            "Digitally signed acknowledgement of vote cast",
            styles["Normal"],
        ),
        Spacer(1, 8 * mm),
    ]

    rows = [
        ["Poll", receipt["poll_title"]],
        ["Poll reference", receipt["poll_name"]],
        ["Voter name", receipt["voter_name"]],
        ["Flat number", receipt["flat"]],
        ["Voter category", receipt["voter_type"]],
        ["Selected option", receipt["selected_option"]],
        ["Voting weight", str(receipt["voting_weight"])],
        ["Receipt code", receipt["receipt_code"]],
        ["Date and time", str(receipt["cast_on"])],
        [
            "SHA-256 ballot hash",
            Paragraph(
                "<br/>".join(
                    receipt["ballot_hash"][i:i + 32]
                    for i in range(0, len(receipt["ballot_hash"]), 32)
                ),
                styles["ReceiptHash"],
            ),
        ],
    ]

    table = Table(rows, colWidths=[48 * mm, 112 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEEEEE")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BBBBBB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 11),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    story.extend([
        table,
        Spacer(1, 7 * mm),
    ])

    register_url = (
        frappe.utils.get_url()
        + "/voting-register?"
        + urlencode({
            "poll": receipt["poll_name"],
            "receipt": receipt["receipt_code"],
        })
    )

    verification = Paragraph(
        "Scan the QR code to open the Association's public anonymous "
        "ballot register. The register will locate this receipt. "
        "Check that the selected option and voting weight match this PDF."
        "<br/><br/>"
        f'<link href="{escape(register_url)}" color="#145DA0">'
        "<b>View my ballot in the Public Ballot Register</b></link>",
        styles["Normal"],
    )

    verification_table = Table(
        [[verification, ReceiptQR(register_url)]],
        colWidths=[120 * mm, 30 * mm],
    )
    verification_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(verification_table)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "The Association's digital signature protects this PDF against "
        "undetected modification. Any alteration after signing will "
        "invalidate the signature.",
        styles["ReceiptNote"],
    ))

    signature_text = Paragraph(
        "<b>Digitally signed by Kendriya Vihar Chennai Phase III AOA</b><br/>"
        "Association digital signature applied to this PDF.<br/>"
        "Open the PDF signature panel to validate the signature and "
        "document integrity.",
        styles["ReceiptNote"],
    )
    signature_block = Table(
        [[GreenTick(), signature_text]],
        colWidths=[12 * mm, 145 * mm],
    )
    signature_block.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#198754")),
    ]))
    story.append(Spacer(1, 2 * mm))
    story.append(signature_block)

    doc.build(story)
    return buffer.getvalue()


def _sign_pdf(unsigned_pdf):
    """Apply the Association's cryptographic PDF signature."""

    signer = _get_signer()
    source = io.BytesIO(unsigned_pdf)
    output = io.BytesIO()

    pdf_signer = signers.PdfSigner(
        PdfSignatureMetadata(
            field_name="AssociationSignature",
            md_algorithm="sha256",
            reason="Association-issued voting receipt",
            location="Chennai, India",
        ),
        signer=signer,
        new_field_spec=SigFieldSpec(
            sig_field_name="AssociationSignature",
            on_page=0,
            box=None,
        ),
    )

    pdf_signer.sign_pdf(
        IncrementalPdfFileWriter(source),
        output=output,
    )

    return output.getvalue()


@frappe.whitelist(methods=["POST"])
def download_voting_receipt_pdf(
    poll_name,
    flat,
    receipt_code,
    ballot_hash,
    idempotency_key,
):
    """Generate a signed receipt for the authenticated voter."""

    import hashlib
    import re

    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Please log in to download your voting receipt."))

    if not isinstance(idempotency_key, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{32,128}", idempotency_key
    ):
        frappe.throw(_("Invalid receipt verification key."))

    # Confirm participation belongs to this logged-in user.
    participation = frappe.db.get_value(
        "Voting Participation",
        {
            "poll": poll_name,
            "flat": flat,
            "voter_user": user,
        },
        ["voter_type", "voted_on"],
        as_dict=True,
    )

    if not participation:
        frappe.throw(
            _("No voting participation record found for this account.")
        )

    # Reproduce the exact key hash used by cast_vote().
    key_material = "\0".join([
        poll_name,
        flat,
        idempotency_key,
    ])
    key_hash = hashlib.sha256(
        key_material.encode("utf-8")
    ).hexdigest()

    # Retrieve the ballot using the secret key hash, not public receipt code.
    ballot = frappe.db.get_value(
        "Voting Ballot",
        {
            "poll": poll_name,
            "idempotency_key_hash": key_hash,
        },
        [
            "receipt_code",
            "ballot_hash",
            "selected_option",
            "voting_weight",
            "cast_on",
        ],
        as_dict=True,
    )

    if (
        not ballot
        or ballot.receipt_code != receipt_code
        or ballot.ballot_hash != ballot_hash
    ):
        frappe.throw(
            _("The receipt details could not be verified.")
        )

    poll_title = frappe.db.get_value(
        "Voting Poll", poll_name, "poll_title"
    )
    voter_name = frappe.db.get_value(
        "User", user, "full_name"
    )

    receipt = {
        "poll_name": poll_name,
        "poll_title": poll_title or poll_name,
        "voter_name": voter_name or user,
        "flat": flat,
        "voter_type": participation.voter_type or "",
        "selected_option": (
            frappe.db.get_value(
                "Voting Option", ballot.selected_option, "option_label"
            ) or ballot.selected_option
        ),
        "voting_weight": ballot.voting_weight,
        "receipt_code": ballot.receipt_code,
        "cast_on": ballot.cast_on,
        "ballot_hash": ballot.ballot_hash,
    }

    unsigned_pdf = _make_unsigned_pdf(receipt)
    signed_pdf = _sign_pdf(unsigned_pdf)

    frappe.local.response.filename = (
        f"Voting-Receipt-{receipt_code}.pdf"
    )
    frappe.local.response.filecontent = signed_pdf
    frappe.local.response.type = "download"
    frappe.local.response.content_type = "application/pdf"