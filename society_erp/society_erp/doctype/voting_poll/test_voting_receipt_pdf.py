from io import BytesIO
from unittest import TestCase
from unittest.mock import patch

from pypdf import PdfReader

from society_erp.society_erp.doctype.voting_poll.voting_receipt_pdf import (
    _make_unsigned_pdf,
)


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
