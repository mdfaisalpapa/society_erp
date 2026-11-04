import base64
import io
from pathlib import Path
from urllib.parse import urlencode
from xml.sax.saxutils import escape
from html.parser import HTMLParser

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




class _ReceiptDescriptionParser(HTMLParser):
    """Convert editor HTML into safe, page-splittable ReportLab paragraphs."""

    INLINE_TAGS = {
        "b": "b",
        "strong": "b",
        "i": "i",
        "em": "i",
        "u": "u",
        "sup": "super",
        "sub": "sub",
    }

    BLOCK_TAGS = {
        "p", "div", "section", "article",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "li",
    }

    def __init__(self, style):
        super().__init__(convert_charrefs=True)
        self.style = style
        self.blocks = []
        self.current = []
        self.inline_stack = []
        self.list_item = False
        self.suppressed_tag = None

    def _close_inline(self):
        while self.inline_stack:
            tag = self.inline_stack.pop()
            self.current.append(f"</{tag}>")

    def _flush(self):
        self._close_inline()
        content = "".join(self.current).strip()
        self.current = []

        if content:
            if self.list_item:
                content = "- " + content

            self.blocks.append(Paragraph(content, self.style))

        self.list_item = False

    def handle_starttag(self, tag, attrs):
        if self.suppressed_tag:
            return

        if tag in ("script", "style"):
            self.suppressed_tag = tag
            return

        if tag in self.BLOCK_TAGS or tag in ("ul", "ol"):
            self._flush()

        if tag == "li":
            self.list_item = True
        elif tag == "br":
            self.current.append("<br/>")
        elif tag in self.INLINE_TAGS:
            safe_tag = self.INLINE_TAGS[tag]
            self.current.append(f"<{safe_tag}>")
            self.inline_stack.append(safe_tag)

    def handle_endtag(self, tag):
        if self.suppressed_tag:
            if tag == self.suppressed_tag:
                self.suppressed_tag = None
            return

        if tag in self.INLINE_TAGS:
            safe_tag = self.INLINE_TAGS[tag]

            if safe_tag in self.inline_stack:
                while self.inline_stack:
                    opened = self.inline_stack.pop()
                    self.current.append(f"</{opened}>")
                    if opened == safe_tag:
                        break

        elif tag in self.BLOCK_TAGS or tag in ("ul", "ol"):
            self._flush()

    def handle_data(self, data):
        if self.suppressed_tag:
            return

        self.current.append(escape(data))

    def finish(self):
        self._flush()
        return self.blocks


def _description_flowables(description, styles):
    """Return safe, individually splittable description flowables."""

    if not description:
        return []

    parser = _ReceiptDescriptionParser(styles["ReceiptDescription"])
    parser.feed(description)
    parser.close()

    return parser.finish()


def _make_unsigned_pdf(receipt):
    """Create the unsigned voting receipt with QR and readable hash."""

    option_label = receipt.get("selected_option")
    if not isinstance(option_label, str) or not option_label.strip():
        frappe.throw(
            _("The selected option label is unavailable. The receipt PDF cannot be generated.")
        )

    from reportlab.platypus import Flowable
    from reportlab.graphics.barcode import qr
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics import renderPDF

    buffer = io.BytesIO()
    page_width, _page_height = A4

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
        name="ReceiptDescription",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#333333"),
        backColor=colors.HexColor("#F5F5F5"),
        borderColor=colors.HexColor("#CCCCCC"),
        borderWidth=0.4,
        borderPadding=6,
        spaceAfter=2 * mm,
    ))
    styles.add(ParagraphStyle(
        name="ReceiptHash",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=7,
        leading=10,
        wordWrap="CJK",
    ))

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
        Spacer(1, 3 * mm),
    ]

    if receipt.get("poll_description"):
        story.append(Paragraph(
            "Poll Description",
            styles["Heading4"],
        ))
        story.extend(
            _description_flowables(
                receipt["poll_description"],
                styles,
            )
        )
        story.append(Spacer(1, 5 * mm))
    else:
        story.append(Spacer(1, 5 * mm))

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
            "hash": receipt["ballot_hash"],
            "option": base64.urlsafe_b64encode(
                option_label.encode("utf-8")
            ).decode("ascii").rstrip("="),
            "weight": f"{float(receipt['voting_weight']):.3f}",
        })
    )

    verification = Paragraph(
        "After publication of the voting results, scan this QR code "
        "to view the complete Public Ballot Register and locate your "
        "ballot. You can verify your receipt against the published record."
        "<br/><br/>"
        f'<link href="{escape(register_url)}" color="#145DA0">'
        "<b>View Public Ballot Register</b></link>",
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

    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "The Association's digital signature appears in the signature "
        "panel below. Click the digital signature to inspect its "
        "properties and validate the document and its integrity.",
        styles["ReceiptNote"],
    ))

    doc.build(story)
    return buffer.getvalue()


def _sign_pdf(unsigned_pdf):
    """Apply the Association's visible cryptographic PDF signature."""

    from pyhanko.stamp import TextStampStyle
    from pyhanko.pdf_utils.text import TextBoxStyle

    signer = _get_signer()
    source = io.BytesIO(unsigned_pdf)
    output = io.BytesIO()

    signature_style = TextStampStyle(
        stamp_text=(
            "Digitally signed by %(signer)s\n"
            "Date: %(ts)s\n"
            "Association voting receipt"
        ),
        border_width=1,
        border_color=(0.10, 0.45, 0.25),
        background_opacity=0,
        text_box_style=TextBoxStyle(
            font_size=11,
            leading=14,
            text_color=(0, 0, 0),
        ),
    )

    pdf_signer = signers.PdfSigner(
        PdfSignatureMetadata(
            field_name="AssociationSignature",
            md_algorithm="sha256",
            reason="Association-issued voting receipt",
            location="Chennai, India",
        ),
        signer=signer,
        stamp_style=signature_style,
        new_field_spec=SigFieldSpec(
            sig_field_name="AssociationSignature",
            on_page=-1,
            box=(56, 32, 539, 100),
            readable_field_name="Association Digital Signature",
        ),
    )

    pdf_signer.sign_pdf(
        IncrementalPdfFileWriter(source),
        output=output,
        appearance_text_params={
            "signer": "Kendriya Vihar Chennai Phase III AOA",
        },
    )

    return output.getvalue()


def _resolve_poll_option_label(poll_name, selected_option):
    """Resolve the selected label from this poll without exposing its row ID."""
    poll = frappe.get_doc("Voting Poll", poll_name)
    option_label = next(
        (
            option.option_label
            for option in poll.options
            if option.name == selected_option
        ),
        None,
    )
    if not isinstance(option_label, str) or not option_label.strip():
        frappe.throw(
            _("The selected option label is unavailable. The receipt PDF cannot be generated.")
        )
    return option_label


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

    poll_details = frappe.db.get_value(
        "Voting Poll",
        poll_name,
        ["poll_title", "description"],
        as_dict=True,
    )
    poll_title = poll_details.poll_title if poll_details else None
    poll_description = poll_details.description if poll_details else ""
    voter_name = frappe.db.get_value(
        "User", user, "full_name"
    )

    receipt = {
        "poll_name": poll_name,
        "poll_title": poll_title or poll_name,
        "poll_description": poll_description or "",
        "voter_name": voter_name or user,
        "flat": flat,
        "voter_type": participation.voter_type or "",
        "selected_option": _resolve_poll_option_label(
            poll_name, ballot.selected_option
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
