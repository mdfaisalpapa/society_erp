import base64
from io import BytesIO
from urllib.parse import parse_qs, urlparse
from unittest import TestCase
from unittest.mock import patch

import frappe
from pypdf import PdfReader

from society_erp.society_erp.doctype.voting_poll.voting_receipt_pdf import (
    _make_unsigned_pdf,
    _resolve_poll_option_label,
)


class TestVotingReceiptOptionLabel(TestCase):
    def setUp(self):
        self.poll_name = "VP-TEST-OPTION-001"
        self.option_id = "INTERNAL-OPTION-ROW-ID"
        self.option_label = "Approve"
        self.receipt = {
            "poll_title": "Synthetic poll",
            "poll_name": self.poll_name,
            "poll_description": "",
            "voter_name": "Synthetic resident",
            "flat": "TEST-FLAT-101",
            "voter_type": "Owner",
            "selected_option": self.option_label,
            "voting_weight": 1,
            "receipt_code": "TEST-RECEIPT-OPTION-001",
            "cast_on": "2026-11-04 10:00:00",
            "ballot_hash": "a" * 64,
        }

    def _resolve_from_options(self, options):
        poll = frappe._dict({"options": options})
        with patch("frappe.get_doc", return_value=poll):
            return _resolve_poll_option_label(self.poll_name, self.option_id)

    def _receipt_register_url(self):
        with patch("frappe.utils.get_url", return_value="https://example.test"):
            pdf = _make_unsigned_pdf(self.receipt)

        reader = PdfReader(BytesIO(pdf))
        for page in reader.pages:
            for annotation in page.get("/Annots", []):
                action = annotation.get_object().get("/A", {})
                uri = action.get("/URI")
                if uri and "/voting-register?" in str(uri):
                    return str(uri)
        self.fail("Receipt PDF did not contain its public register QR link")

    def test_valid_option_label_is_encoded_in_qr_claim(self):
        label = self._resolve_from_options([
            frappe._dict({"name": self.option_id, "option_label": self.option_label})
        ])
        self.receipt["selected_option"] = label

        register_url = self._receipt_register_url()
        query = parse_qs(urlparse(register_url).query)
        expected = base64.urlsafe_b64encode(
            self.option_label.encode("utf-8")
        ).decode("ascii").rstrip("=")
        self.assertEqual(query["option"], [expected])
        self.assertEqual(base64.urlsafe_b64decode(expected + "==").decode(), self.option_label)
        self.assertNotIn(self.option_id, register_url)

    def test_missing_option_label_fails_safely(self):
        with self.assertRaises(frappe.ValidationError) as raised:
            self._resolve_from_options([
                frappe._dict({"name": self.option_id, "option_label": None})
            ])

        self.assertNotIn(self.option_id, str(raised.exception))

    def test_blank_option_label_fails_safely(self):
        with self.assertRaises(frappe.ValidationError) as raised:
            self._resolve_from_options([
                frappe._dict({"name": self.option_id, "option_label": "  "})
            ])

        self.assertNotIn(self.option_id, str(raised.exception))

    def test_unresolvable_option_fails_safely(self):
        with self.assertRaises(frappe.ValidationError) as raised:
            self._resolve_from_options([
                frappe._dict({"name": "A-DIFFERENT-OPTION", "option_label": "Approve"})
            ])

        self.assertNotIn(self.option_id, str(raised.exception))

    def test_unsigned_pdf_rejects_blank_label_before_creating_qr(self):
        self.receipt["selected_option"] = " \t"
        with patch("frappe.utils.get_url") as get_url:
            with self.assertRaises(frappe.ValidationError) as raised:
                _make_unsigned_pdf(self.receipt)

        self.assertNotIn(self.option_id, str(raised.exception))
        get_url.assert_not_called()


class TestVotingReceiptDescriptionSanitisation(TestCase):
    def _extract_description_text(self, description):
        receipt = {
            "poll_title": "TEST POLL",
            "poll_name": "TEST-POLL-001",
            "poll_description": description,
            "voter_name": "Test Resident",
            "flat": "TEST-A-101",
            "voter_type": "Owner",
            "selected_option": "Yes",
            "voting_weight": 1,
            "receipt_code": "TEST-RECEIPT-001",
            "cast_on": "2026-11-04 10:00:00",
            "ballot_hash": "a" * 64,
        }

        with patch(
            "frappe.utils.get_url",
            return_value="https://example.test",
        ):
            pdf = _make_unsigned_pdf(receipt)

        reader = PdfReader(BytesIO(pdf))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    def test_script_and_style_contents_are_suppressed(self):
        description = (
            "<p>Before script.</p>"
            "<script>drop_script <b>drop_nested_script</b></script>"
            "<p>After script.</p>"
            "<style>.hidden { color: red; } drop_css</style>"
            "<style><span>drop_nested_style</span></style>"
            "<p><b>Keep bold</b> and <i>keep italic</i>.</p>"
        )

        text = self._extract_description_text(description)

        for visible in (
            "Before script.",
            "After script.",
            "Keep bold",
            "keep italic",
        ):
            self.assertIn(visible, text)

        for suppressed in (
            "drop_script",
            "drop_nested_script",
            ".hidden",
            "color: red",
            "drop_css",
            "drop_nested_style",
        ):
            self.assertNotIn(suppressed, text)
