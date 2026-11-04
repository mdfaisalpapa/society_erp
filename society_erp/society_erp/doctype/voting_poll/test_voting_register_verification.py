import base64
from datetime import datetime
from io import BytesIO
from urllib.parse import parse_qs, urlparse
from unittest import TestCase
from unittest.mock import patch

import frappe
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from society_erp.society_erp.doctype.voting_poll import voting_api
from society_erp.society_erp.doctype.voting_poll import voting_receipt_pdf


class TestVotingRegisterVerification(TestCase):
    def setUp(self):
        self.poll_name = "VP-TEST-00001"
        self.receipt_code = "TEST-RECEIPT-00001"
        self.option_id = "INTERNAL-OPTION-ROW-ID"
        self.option_label = "Approve"
        self.weight = 1.25
        self.cast_on = datetime(2026, 11, 4, 10, 0, 0, 123456)
        self.ballot_hash = voting_api._ballot_hash(
            self.poll_name,
            self.receipt_code,
            self.option_id,
            self.option_label,
            self.weight,
            self.cast_on,
        )
        self.rows = [{
            "receipt_code": self.receipt_code,
            "selected_option": self.option_id,
            "selected_option_label": self.option_label,
            "voting_weight": self.weight,
            "ballot_hash": self.ballot_hash,
        }]
        self.poll = frappe._dict({
            "name": self.poll_name,
            "poll_title": "Synthetic verification poll",
            "status": "Closed",
            "ballot_register_published": 1,
            "published_on": "2026-11-04 11:00:00",
            "ballot_register_hash": voting_api._register_hash(self.rows),
        })
        self.ballot = frappe._dict({
            "receipt_code": self.receipt_code,
            "selected_option": self.option_id,
            "voting_weight": self.weight,
            "cast_on": self.cast_on,
            "ballot_hash": self.ballot_hash,
        })
        self.claims = {
            "poll_name": self.poll_name,
            "receipt_code": self.receipt_code,
            "ballot_hash": self.ballot_hash,
            "option_b64": self._encoded_option(self.option_label),
            "voting_weight": "1.250",
        }

    @staticmethod
    def _encoded_option(label):
        return base64.urlsafe_b64encode(label.encode("utf-8")).decode("ascii").rstrip("=")

    def _verification_mocks(self, rows=None, poll=None, ballot=None):
        rows = self.rows if rows is None else rows
        poll = self.poll if poll is None else poll
        ballot = self.ballot if ballot is None else ballot
        return (
            patch.object(voting_api.frappe.db, "exists", return_value=True),
            patch.object(voting_api.frappe, "get_doc", return_value=poll),
            patch.object(voting_api, "_get_public_ballot_rows", return_value=rows),
            patch.object(
                voting_api.frappe.db,
                "get_value",
                side_effect=[ballot, self.option_label],
            ),
        )

    def test_missing_option_label_uses_generic_public_label(self):
        ballot_row = frappe._dict({
            "receipt_code": self.receipt_code,
            "selected_option": self.option_id,
            "voting_weight": self.weight,
            "ballot_hash": self.ballot_hash,
        })
        with patch.object(voting_api.frappe, "get_all", return_value=[ballot_row]), \
                patch.object(voting_api.frappe.db, "get_value", return_value=None):
            rows = voting_api._get_public_ballot_rows(self.poll_name)

        self.assertEqual(rows[0]["selected_option_label"], "Option unavailable")
        self.assertEqual(rows[0]["selected_option"], self.option_id)
        public_rows = voting_api._public_ballot_projection(rows)
        self.assertNotIn(self.option_id, frappe.as_json(public_rows))

    def test_missing_option_label_cannot_verify_receipt(self):
        rows = [{**self.rows[0], "selected_option_label": "Option unavailable"}]
        poll = frappe._dict({
            **self.poll,
            "ballot_register_hash": voting_api._register_hash(rows),
        })
        with patch.object(voting_api.frappe.db, "exists", return_value=True), \
                patch.object(voting_api.frappe, "get_doc", return_value=poll), \
                patch.object(voting_api, "_get_public_ballot_rows", return_value=rows), \
                patch.object(
                    voting_api.frappe.db,
                    "get_value",
                    side_effect=[self.ballot, None],
                ):
            result = voting_api.verify_published_ballot_receipt(**self.claims)

        self.assertEqual(result["status"], "option_unavailable")
        self.assertNotIn(self.option_id, frappe.as_json(result))

    def test_missing_option_label_is_safe_in_json_csv_and_pdf_text(self):
        rows = [{**self.rows[0], "selected_option_label": "Option unavailable"}]
        public_data = {
            "poll": self.poll_name,
            "poll_title": self.poll.poll_title,
            "published_on": self.poll.published_on,
            "ballot_count": 1,
            "register_hash": voting_api._register_hash(rows),
            "ballots": voting_api._public_ballot_projection(rows),
        }
        with patch.object(
            voting_api,
            "_published_ballot_register_state",
            return_value=("published", self.poll, rows),
        ):
            public_json = voting_api.get_published_ballot_register(self.poll_name)
        self.assertNotIn(self.option_id, frappe.as_json(public_json))
        self.assertEqual(
            public_json["ballots"][0]["selected_option_label"], "Option unavailable"
        )

        response = frappe.local.response
        frappe.local.response = frappe._dict()
        try:
            with patch.object(
                voting_api, "get_published_ballot_register", return_value=public_data
            ):
                voting_api.download_published_ballot_register(self.poll_name)
            csv_output = frappe.local.response.filecontent
            self.assertIn("Option unavailable", csv_output)
            self.assertNotIn(self.option_id, csv_output)

            def render_synthetic_pdf(html):
                self.assertIn("Option unavailable", html)
                self.assertNotIn(self.option_id, html)
                buffer = BytesIO()
                page = canvas.Canvas(buffer)
                page.drawString(36, 760, public_data["ballots"][0]["selected_option_label"])
                page.save()
                return buffer.getvalue()

            with patch.object(
                voting_api, "get_published_ballot_register", return_value=public_data
            ), patch("frappe.utils.pdf.get_pdf", side_effect=render_synthetic_pdf):
                voting_api.download_published_ballot_register_pdf(self.poll_name)
            pdf_text = " ".join(
                page.extract_text() or ""
                for page in PdfReader(BytesIO(frappe.local.response.filecontent)).pages
            )
            self.assertIn("Option unavailable", pdf_text)
            self.assertNotIn(self.option_id, pdf_text)
        finally:
            frappe.local.response = response

    def test_valid_receipt_and_ballot_hash(self):
        mocks = self._verification_mocks()
        with mocks[0], mocks[1], mocks[2], mocks[3] as get_value:
            result = voting_api.verify_published_ballot_receipt(**self.claims)

        self.assertEqual(result["status"], "verified")
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(get_value.call_count, 2)
        self.assertEqual(get_value.call_args_list[0].args[0], "Voting Ballot")
        self.assertEqual(
            get_value.call_args_list[0].args[1],
            {"poll": self.poll_name, "receipt_code": self.receipt_code},
        )
        self.assertEqual(get_value.call_args_list[1].args[:2], (
            "Voting Option", self.option_id
        ))
        self.assertNotIn(self.option_id, frappe.as_json(result))

    def test_receipt_code_not_found(self):
        claims = {**self.claims, "receipt_code": "OTHER-RECEIPT"}
        with self._verification_mocks()[0], self._verification_mocks()[1], \
                self._verification_mocks()[2], self._verification_mocks()[3] as get_value:
            result = voting_api.verify_published_ballot_receipt(**claims)

        self.assertEqual(result["status"], "not_found")
        get_value.assert_not_called()

    def test_modified_selected_option_is_rejected(self):
        claims = {**self.claims, "option_b64": self._encoded_option("Reject")}
        with self._verification_mocks()[0], self._verification_mocks()[1], \
                self._verification_mocks()[2], self._verification_mocks()[3]:
            result = voting_api.verify_published_ballot_receipt(**claims)

        self.assertEqual(result["status"], "hash_mismatch")
        self.assertFalse(result["checks"]["selected_option"])

    def test_modified_voting_weight_is_rejected(self):
        claims = {**self.claims, "voting_weight": "1.500"}
        with self._verification_mocks()[0], self._verification_mocks()[1], \
                self._verification_mocks()[2], self._verification_mocks()[3]:
            result = voting_api.verify_published_ballot_receipt(**claims)

        self.assertEqual(result["status"], "hash_mismatch")
        self.assertFalse(result["checks"]["voting_weight"])

    def test_modified_receipt_ballot_hash_is_rejected(self):
        claims = {**self.claims, "ballot_hash": "0" * 64}
        with self._verification_mocks()[0], self._verification_mocks()[1], \
                self._verification_mocks()[2], self._verification_mocks()[3]:
            result = voting_api.verify_published_ballot_receipt(**claims)

        self.assertEqual(result["status"], "hash_mismatch")
        self.assertFalse(result["checks"]["receipt_ballot_hash"])

    def test_modified_stored_ballot_hash_is_rejected(self):
        changed_ballot = frappe._dict({**self.ballot, "ballot_hash": "0" * 64})
        with self._verification_mocks(ballot=changed_ballot)[0], \
                self._verification_mocks(ballot=changed_ballot)[1], \
                self._verification_mocks(ballot=changed_ballot)[2], \
                self._verification_mocks(ballot=changed_ballot)[3]:
            result = voting_api.verify_published_ballot_receipt(**self.claims)

        self.assertEqual(result["status"], "hash_mismatch")
        self.assertFalse(result["checks"]["stored_ballot_hash"])

    def test_modified_published_register_is_rejected(self):
        changed_rows = [{**self.rows[0], "selected_option_label": "Reject"}]
        with self._verification_mocks(rows=changed_rows)[0], \
                self._verification_mocks(rows=changed_rows)[1], \
                self._verification_mocks(rows=changed_rows)[2], \
                self._verification_mocks(rows=changed_rows)[3] as get_value:
            result = voting_api.verify_published_ballot_receipt(**self.claims)

        self.assertEqual(result["status"], "hash_mismatch")
        self.assertEqual(result["checks"], {"register_hash": False})
        get_value.assert_not_called()

    def test_register_integrity_is_checked_before_public_projection(self):
        changed_rows = [{**self.rows[0], "selected_option_label": "Reject"}]
        with patch.object(voting_api.frappe.db, "exists", return_value=True), \
                patch.object(voting_api.frappe, "get_doc", return_value=self.poll), \
                patch.object(voting_api, "_get_public_ballot_rows", return_value=changed_rows):
            with self.assertRaises(frappe.ValidationError):
                voting_api.get_published_ballot_register(self.poll_name)

    def test_unpublished_register_is_not_queried(self):
        poll = frappe._dict({**self.poll, "ballot_register_published": 0})
        with self._verification_mocks(poll=poll)[0], \
                self._verification_mocks(poll=poll)[1], \
                self._verification_mocks(poll=poll)[2] as get_rows, \
                self._verification_mocks(poll=poll)[3] as get_value:
            result = voting_api.verify_published_ballot_receipt(**self.claims)

        self.assertEqual(result["status"], "register_not_published")
        get_rows.assert_not_called()
        get_value.assert_not_called()

    def test_invalid_receipt_parameters_are_rejected_before_database_access(self):
        invalid_claim_sets = (
            {**self.claims, "ballot_hash": "not-a-sha256"},
            {**self.claims, "option_b64": "A"},
        )
        for claims in invalid_claim_sets:
            with self.subTest(claims=claims), patch.object(
                voting_api.frappe.db, "exists"
            ) as exists:
                result = voting_api.verify_published_ballot_receipt(**claims)

            self.assertEqual(result["status"], "invalid_request")
            exists.assert_not_called()

    def test_guest_public_register_json_omits_internal_and_identity_fields(self):
        with patch.object(
            voting_api,
            "_published_ballot_register_state",
            return_value=("published", self.poll, self.rows),
        ):
            result = voting_api.get_published_ballot_register(self.poll_name)

        ballot = result["ballots"][0]
        self.assertNotIn("selected_option", ballot)
        self.assertNotIn(self.option_id, frappe.as_json(result))
        for private_key in (
            "flat", "voter_user", "voter_name", "voter_type",
            "idempotency_key_hash", "participation",
        ):
            self.assertNotIn(private_key, frappe.as_json(result))

    def test_guest_csv_and_pdf_omit_internal_and_identity_fields(self):
        public_data = {
            "poll": self.poll_name,
            "poll_title": self.poll.poll_title,
            "published_on": self.poll.published_on,
            "ballot_count": 1,
            "register_hash": self.poll.ballot_register_hash,
            "ballots": voting_api._public_ballot_projection(self.rows),
        }
        response = frappe.local.response
        frappe.local.response = frappe._dict()
        try:
            with patch.object(voting_api, "get_published_ballot_register", return_value=public_data):
                voting_api.download_published_ballot_register(self.poll_name)
            csv_output = frappe.local.response.filecontent
            self.assertNotIn(self.option_id, csv_output)
            self.assertNotIn("voter_user", csv_output)
            self.assertNotIn("TEST-FLAT-101", csv_output)

            captured_html = {}

            def capture_pdf(html):
                captured_html["value"] = html
                return b"synthetic-pdf"

            with patch.object(voting_api, "get_published_ballot_register", return_value=public_data), \
                    patch("frappe.utils.pdf.get_pdf", side_effect=capture_pdf):
                voting_api.download_published_ballot_register_pdf(self.poll_name)

            self.assertNotIn(self.option_id, captured_html["value"])
            self.assertNotIn("voter_user", captured_html["value"])
            self.assertNotIn("TEST-FLAT-101", captured_html["value"])
        finally:
            frappe.local.response = response

    def test_receipt_qr_carries_public_verification_claims(self):
        receipt = {
            "poll_title": "Synthetic verification poll",
            "poll_name": self.poll_name,
            "poll_description": "",
            "voter_name": "Synthetic Resident",
            "flat": "TEST-FLAT-101",
            "voter_type": "Owner",
            "selected_option": self.option_label,
            "voting_weight": self.weight,
            "receipt_code": self.receipt_code,
            "cast_on": self.cast_on,
            "ballot_hash": self.ballot_hash,
        }
        with patch("frappe.utils.get_url", return_value="https://example.test"):
            pdf = voting_receipt_pdf._make_unsigned_pdf(receipt)

        reader = PdfReader(BytesIO(pdf))
        uris = []
        for page in reader.pages:
            for annotation in page.get("/Annots", []):
                action = annotation.get_object().get("/A", {})
                if action.get("/URI"):
                    uris.append(str(action["/URI"]))

        register_url = next(uri for uri in uris if "/voting-register?" in uri)
        claims = parse_qs(urlparse(register_url).query)
        self.assertEqual(claims["poll"], [self.poll_name])
        self.assertEqual(claims["receipt"], [self.receipt_code])
        self.assertEqual(claims["hash"], [self.ballot_hash])
        self.assertEqual(claims["option"], [self.claims["option_b64"]])
        self.assertEqual(claims["weight"], ["1.250"])
        self.assertNotIn("flat", urlparse(register_url).query.lower())
        self.assertNotIn("voter", urlparse(register_url).query.lower())

    def test_guest_public_endpoints_are_whitelisted_for_guest(self):
        public_methods = (
            voting_api.get_published_ballot_register,
            voting_api.verify_published_ballot_receipt,
            voting_api.get_published_ballot_registers,
            voting_api.download_published_ballot_register,
            voting_api.download_published_ballot_register_pdf,
        )
        current_user = frappe.session.user
        frappe.set_user("Guest")
        try:
            for method in public_methods:
                self.assertIn(method, frappe.guest_methods)
                frappe.is_whitelisted(method)
        finally:
            frappe.set_user(current_user)

    def test_guest_is_denied_private_voting_and_identity_endpoints(self):
        current_user = frappe.session.user
        frappe.set_user("Guest")
        try:
            private_methods = (
                voting_api.cast_vote,
                voting_api.send_voting_otp,
                voting_api.verify_voting_otp,
                voting_api.get_resident_polls,
                voting_api.get_resident_poll_details,
                voting_api.get_poll_audit_summary,
                voting_api.publish_ballot_register,
                voting_api.end_poll,
                voting_api.extend_poll,
                voting_receipt_pdf.download_voting_receipt_pdf,
            )
            for method in private_methods:
                with self.subTest(method=method.__name__):
                    with self.assertRaises(frappe.PermissionError):
                        frappe.is_whitelisted(method)
        finally:
            frappe.set_user(current_user)
