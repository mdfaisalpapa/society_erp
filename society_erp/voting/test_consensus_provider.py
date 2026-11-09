"""Comprehensive Automated Integration Tests for Society ERP Consensus Provider & Provisional Electorate."""
from __future__ import annotations

import secrets
from datetime import timedelta
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

import frappe
from consensus.services.eligibility import build_eligibility_snapshot, verify_eligibility_snapshot
from consensus.services.voting import cast_vote, send_voting_otp, verify_voting_otp
from frappe.utils import getdate, now_datetime

from society_erp.voting.electorate import (
    approve_electorate,
    calculate_flat_maintenance_dues,
    close_objections_submission,
    generate_draft_electorate,
    publish_electorate,
)
from society_erp.voting.portal_api import (
    get_electorate_details,
    submit_additional_evidence,
    submit_objection,
)
from society_erp.voting.provider import SocietyERPProvider
from society_erp.voting.secrets import SocietyERPSecretResolver


class TestConsensusProvider(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for role_name in ("Flat Owner", "Flat Tenant"):
            if not frappe.db.exists("Role", role_name):
                frappe.get_doc({"doctype": "Role", "role_name": role_name, "desk_access": 0}).insert(ignore_permissions=True)

    def setUp(self):
        frappe.flags.in_import = True
        self.suffix = secrets.token_hex(4)
        self.test_user = f"user_{self.suffix}@example.com"
        if not frappe.db.exists("User", self.test_user):
            frappe.get_doc({
                "doctype": "User",
                "email": self.test_user,
                "first_name": "Test",
                "last_name": f"Voter {self.suffix}",
                "enabled": 1,
            }).insert(ignore_permissions=True, ignore_mandatory=True)

        self.test_user_2 = f"user2_{self.suffix}@example.com"
        if not frappe.db.exists("User", self.test_user_2):
            frappe.get_doc({
                "doctype": "User",
                "email": self.test_user_2,
                "first_name": "Test2",
                "last_name": f"Voter {self.suffix}",
                "enabled": 1,
            }).insert(ignore_permissions=True, ignore_mandatory=True)

        # Set Society ERP Settings default
        settings = frappe.get_single("Society ERP Settings")
        settings.voting_engine_active = "Consensus"
        settings.save(ignore_permissions=True)

        # Set Voting Integration Settings for consensus
        int_settings = frappe.get_single("Voting Integration Settings")
        int_settings.enabled = 1
        int_settings.provider_key = "society_erp_association_provider"
        int_settings.provider_api_version = "1.0"
        int_settings.secret_resolver_key = "society_erp_secret_resolver"
        int_settings.signing_key_reference = "pdf_signing"
        int_settings.provider_reference_encryption_key_reference = "ref_enc"
        int_settings.identity_snapshot_encryption_key_reference = "id_enc"
        int_settings.voter_reference_hmac_key_reference = "voter_hmac"
        int_settings.idempotency_hmac_key_reference = "idem_hmac"
        int_settings.identity_snapshot_hmac_key_reference = "id_hmac"
        int_settings.otp_hmac_key_reference = "otp_hmac"
        int_settings.otp_enabled = 1
        int_settings.save(ignore_permissions=True)

    def tearDown(self):
        frappe.flags.in_import = False

    def _create_flat(self, flat_no, uds=100.0, is_let_out=0, customer_group=None):
        if not customer_group:
            customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "Non Member"
        existing = frappe.db.get_value("Customer", {"customer_name": flat_no}, "name")
        if existing:
            return existing
        doc = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": flat_no,
            "customer_type": "Individual",
            "customer_group": customer_group,
            "custom_uds": uds,
            "custom_let_out_for_rent": is_let_out,
        }).insert(ignore_permissions=True, ignore_mandatory=True)
        return doc.name

    def _create_owner(self, flat_no, name, user_email, active=1):
        return frappe.get_doc({
            "doctype": "Owners",
            "flat": flat_no,
            "owner_name": name,
            "linked_user": user_email,
            "email": user_email,
            "mobile_no": "9876543210",
            "active": active,
            "start_date": "2026-01-01",
        }).insert(ignore_permissions=True, ignore_mandatory=True)

    def _create_tenant(self, flat_no, name, user_email, active=1):
        return frappe.get_doc({
            "doctype": "Tenants",
            "flat": flat_no,
            "tenant_name": name,
            "linked_user": user_email,
            "email": user_email,
            "mobile_no": "9876543211",
            "relationship": "Tenant",
            "start_date": "2026-01-01",
            "active": active,
        }).insert(ignore_permissions=True, ignore_mandatory=True)

    def test_owner_only_policy_ignores_let_out_flat_tenant(self):
        """Tenants receive zero voting rights in Association Voting even when flat is let out."""
        flat_name = self._create_flat(f"FLAT-LET-{self.suffix}", is_let_out=1)
        self._create_owner(flat_name, f"Owner {self.suffix}", self.test_user, active=1)
        self._create_tenant(flat_name, f"Tenant {self.suffix}", self.test_user_2, active=1)

        pub = frappe.get_doc({
            "doctype": "Electorate Publication",
            "title": f"Test Publication {self.suffix}",
            "dues_enforcement_enabled": 0,
        }).insert(ignore_permissions=True, ignore_links=True)

        generate_draft_electorate(pub.name)
        member = frappe.get_doc("Provisional Electorate Member", {"publication": pub.name, "flat_no": flat_name})

        self.assertEqual(member.eligibility_status, "Eligible")
        self.assertEqual(member.voter_user, self.test_user)
        self.assertNotEqual(member.voter_user, self.test_user_2)
        self.assertEqual(float(member.voting_weight), 1.0)

    def test_joint_ownership_anomaly_excludes_without_silent_guessing(self):
        """A flat with multiple active owners is excluded until explicit nomination; system never guesses."""
        flat_name = self._create_flat(f"FLAT-JOINT-{self.suffix}")
        self._create_owner(flat_name, f"Joint Owner A {self.suffix}", self.test_user, active=1)
        self._create_owner(flat_name, f"Joint Owner B {self.suffix}", self.test_user_2, active=1)

        pub = frappe.get_doc({
            "doctype": "Electorate Publication",
            "title": f"Joint Pub {self.suffix}",
            "dues_enforcement_enabled": 0,
        }).insert(ignore_permissions=True, ignore_links=True)

        generate_draft_electorate(pub.name)
        member = frappe.get_doc("Provisional Electorate Member", {"publication": pub.name, "flat_no": flat_name})

        self.assertEqual(member.eligibility_status, "Excluded")
        self.assertEqual(member.exclusion_reason, "Multiple Active Owners")
        self.assertIsNone(member.voter_user)
        self.assertEqual(float(member.voting_weight), 0.0)

    def test_multi_flat_owner_receives_separate_allocations_and_votes_both(self):
        """One user owning two flats receives two distinct allocations and can cast a ballot for each."""
        flat_1 = self._create_flat(f"FLAT-M1-{self.suffix}")
        flat_2 = self._create_flat(f"FLAT-M2-{self.suffix}")
        self._create_owner(flat_1, f"Multi Owner {self.suffix}", self.test_user, active=1)
        self._create_owner(flat_2, f"Multi Owner {self.suffix}", self.test_user, active=1)

        pub = frappe.get_doc({
            "doctype": "Electorate Publication",
            "title": f"Multi Flat Pub {self.suffix}",
            "dues_enforcement_enabled": 0,
        }).insert(ignore_permissions=True, ignore_links=True)

        generate_draft_electorate(pub.name)
        publish_electorate(pub.name)
        approve_electorate(pub.name)

        # Create Consensus Poll Type with Multiple Allocations Per User
        poll_type_name = f"multi-type-{self.suffix}"
        if not frappe.db.exists("Consensus Poll Type", poll_type_name):
            frappe.get_doc({
                "doctype": "Consensus Poll Type",
                "label": "Multi Flat Type",
                "type_key": poll_type_name,
                "enabled": 1,
                "allocation_mode": "Multiple Allocations Per User",
                "configuration_version": "1",
                "default_rule_key": "rule-v1",
                "default_rule_config": "{}",
            }).insert(ignore_permissions=True, ignore_links=True)

        now = now_datetime()
        poll = frappe.get_doc({
            "doctype": "Consensus Poll",
            "title": f"Multi Flat Poll {self.suffix}",
            "poll_type": poll_type_name,
            "starts_at": now - timedelta(minutes=5),
            "ends_at": now + timedelta(hours=2),
            "scope_selection_operator": "Any",
            "scope_conditions_operator": "All",
            "scope_conditions": "{}",
            "rule_config": "{}",
            "status": "Draft",
            "snapshot_state": "Not Started",
            "require_otp": 0,
            "result_visibility": "After Closing",
            "publish_anonymous_register": 1,
            "scope_selections": [{"scope_type": "publication", "entity_ref": pub.name, "inclusion": "Include"}],
        }).insert(ignore_permissions=True, ignore_links=True)

        # Add 2 options
        for label in ("Yes", "No"):
            frappe.get_doc({
                "doctype": "Consensus Poll Option",
                "poll": poll.name,
                "option_label": label,
                "display_order": 1,
                "enabled": 1,
            }).insert(ignore_permissions=True, ignore_links=True)

        build_eligibility_snapshot(poll.name)
        self.assertTrue(verify_eligibility_snapshot(poll.name))
        poll.db_set("status", "Open")

        # Check eligibility records for test_user
        allocations = frappe.get_all(
            "Consensus Eligibility",
            filters={"poll": poll.name, "voter_user": self.test_user},
            fields=["name", "context_ref", "voting_weight"],
            order_by="context_ref asc",
        )
        self.assertEqual(len(allocations), 2)
        self.assertEqual(allocations[0].context_ref, flat_1)
        self.assertEqual(allocations[1].context_ref, flat_2)

        # Vote on flat 1
        options = frappe.get_all("Consensus Poll Option", filters={"poll": poll.name}, fields=["name", "option_key"])
        frappe.set_user(self.test_user)
        try:
            vote_1 = cast_vote(
                poll.name,
                options[0].option_key,
                secrets.token_hex(16),
                eligibility_name=allocations[0].name,
            )
            self.assertTrue(vote_1["success"])
            self.assertEqual(frappe.db.get_value("Consensus Eligibility", allocations[0].name, "status"), "Voted")

            # Vote on flat 2
            vote_2 = cast_vote(
                poll.name,
                options[1].option_key,
                secrets.token_hex(16),
                eligibility_name=allocations[1].name,
            )
            self.assertTrue(vote_2["success"])
            self.assertEqual(frappe.db.get_value("Consensus Eligibility", allocations[1].name, "status"), "Voted")

            self.assertEqual(frappe.db.count("Consensus Ballot", {"poll": poll.name}), 2)
            self.assertEqual(frappe.db.count("Consensus Participation", {"poll": poll.name}), 2)
        finally:
            frappe.set_user("Administrator")

    def test_dues_enforcement_optional_and_decimal_threshold(self):
        """Dues enforcement compares Decimal amounts against cutoff date; ignores late payments and exclusions."""
        flat_dues = self._create_flat(f"FLAT-DUES-{self.suffix}")
        self._create_owner(flat_dues, f"Owner Dues {self.suffix}", self.test_user, active=1)

        # Create or verify receivable account
        acc_label = f"Test Maintenance Receivable - {self.suffix}"
        company = frappe.db.get_value("Company", {}, "name")
        parent_acc = frappe.db.get_value("Account", {"account_name": ["like", "%Accounts Receivable%"], "is_group": 1}, "name")
        acc_doc = frappe.get_doc({
            "doctype": "Account",
            "account_name": acc_label,
            "company": company,
            "parent_account": parent_acc,
            "account_type": "Receivable",
            "is_group": 0,
        }).insert(ignore_permissions=True, ignore_links=True)
        acc_name = acc_doc.name

        cutoff = str(getdate(now_datetime() - timedelta(days=7)))

        # When dues enforcement disabled -> Eligible even with dues
        pub_disabled = frappe.get_doc({
            "doctype": "Electorate Publication",
            "title": f"Dues Disabled {self.suffix}",
            "dues_enforcement_enabled": 0,
        }).insert(ignore_permissions=True, ignore_links=True)

        generate_draft_electorate(pub_disabled.name)
        m_disabled = frappe.get_doc("Provisional Electorate Member", {"publication": pub_disabled.name, "flat_no": flat_dues})
        self.assertEqual(m_disabled.eligibility_status, "Eligible")

        # When dues enforcement enabled with ₹0.00 threshold
        pub_enabled = frappe.get_doc({
            "doctype": "Electorate Publication",
            "title": f"Dues Enabled {self.suffix}",
            "dues_enforcement_enabled": 1,
            "dues_cutoff_date": cutoff,
            "dues_threshold": 0.00,
            "maintenance_receivable_accounts": acc_name,
        }).insert(ignore_permissions=True, ignore_links=True)

        # Insert a GL Entry of ₹50.00 debit before cutoff
        company = frappe.db.get_value("Company", {}, "name")
        cost_center = frappe.db.get_value("Cost Center", {"is_group": 0}, "name")
        gle = frappe.get_doc({
            "doctype": "GL Entry",
            "posting_date": cutoff,
            "account": acc_name,
            "party_type": "Customer",
            "party": flat_dues,
            "voucher_type": "Journal Entry",
            "voucher_no": f"TEST-JV-DUES-{self.suffix}",
            "debit": 50.00,
            "credit": 0.00,
            "debit_in_account_currency": 50.00,
            "credit_in_account_currency": 0.00,
            "company": company,
            "cost_center": cost_center,
            "docstatus": 1,
        }).insert(ignore_permissions=True, ignore_links=True)

        generate_draft_electorate(pub_enabled.name)
        m_enabled = frappe.get_doc("Provisional Electorate Member", {"publication": pub_enabled.name, "flat_no": flat_dues})
        self.assertEqual(m_enabled.eligibility_status, "Excluded")
        self.assertEqual(m_enabled.exclusion_reason, "Unreconciled Dues Above Threshold")
        self.assertEqual(Decimal(str(m_enabled.outstanding_dues)), Decimal("50.00"))

        # Clean up test GL Entry
        frappe.db.delete("GL Entry", {"name": gle.name})

    def test_corpus_receivable_accounts_excluded_from_maintenance_dues(self):
        """Corpus fund receivables never exclude voters from Association Voting."""
        flat_corpus = self._create_flat(f"FLAT-CORPUS-{self.suffix}")
        self._create_owner(flat_corpus, f"Owner Corpus {self.suffix}", self.test_user, active=1)

        company = frappe.db.get_value("Company", {}, "name")
        parent_acc = frappe.db.get_value("Account", {"account_name": ["like", "%Accounts Receivable%"], "is_group": 1}, "name")
        cost_center = frappe.db.get_value("Cost Center", {"is_group": 0}, "name")

        maint_doc = frappe.get_doc({
            "doctype": "Account", "account_name": f"Maint-{self.suffix}", "company": company,
            "parent_account": parent_acc,
            "account_type": "Receivable", "is_group": 0,
        }).insert(ignore_permissions=True, ignore_links=True)
        corpus_doc = frappe.get_doc({
            "doctype": "Account", "account_name": f"Corpus-{self.suffix}", "company": company,
            "parent_account": parent_acc,
            "account_type": "Receivable", "is_group": 0,
        }).insert(ignore_permissions=True, ignore_links=True)

        maint_acc = maint_doc.name
        corpus_acc = corpus_doc.name

        cutoff = str(getdate(now_datetime()))
        # Post ₹100,000 to Corpus account
        gle_corpus = frappe.get_doc({
            "doctype": "GL Entry", "posting_date": cutoff, "account": corpus_acc,
            "party_type": "Customer", "party": flat_corpus,
            "voucher_type": "Journal Entry", "voucher_no": f"TEST-JV-CORPUS-{self.suffix}",
            "debit": 100000.00,
            "credit": 0.00, "debit_in_account_currency": 100000.00,
            "credit_in_account_currency": 0.00, "company": company,
            "cost_center": cost_center, "docstatus": 1,
        }).insert(ignore_permissions=True, ignore_links=True)

        # Publication configures ONLY maint_acc
        pub = frappe.get_doc({
            "doctype": "Electorate Publication",
            "title": f"Corpus Exclusion Pub {self.suffix}",
            "dues_enforcement_enabled": 1,
            "dues_cutoff_date": cutoff,
            "dues_threshold": 0.00,
            "maintenance_receivable_accounts": maint_acc,
        }).insert(ignore_permissions=True, ignore_links=True)

        generate_draft_electorate(pub.name)
        m = frappe.get_doc("Provisional Electorate Member", {"publication": pub.name, "flat_no": flat_corpus})

        self.assertEqual(m.eligibility_status, "Eligible")
        self.assertEqual(Decimal(str(m.outstanding_dues)), Decimal("0.00"))

        frappe.db.delete("GL Entry", {"name": gle_corpus.name})

    def test_provisional_electorate_objection_workflow_and_deadline(self):
        """Objections can be submitted while Published, evidence requested, and resolved."""
        flat_name = self._create_flat(f"FLAT-OBJ-{self.suffix}")
        self._create_owner(flat_name, f"Owner Obj {self.suffix}", self.test_user, active=1)

        pub = frappe.get_doc({
            "doctype": "Electorate Publication",
            "title": f"Objection Workflow Pub {self.suffix}",
            "dues_enforcement_enabled": 0,
        }).insert(ignore_permissions=True, ignore_links=True)

        generate_draft_electorate(pub.name)
        publish_electorate(pub.name)

        # Submit objection
        from society_erp.voting.portal_api import submit_objection
        frappe.set_user(self.test_user)
        try:
            res = submit_objection(
                pub.name,
                flat_name,
                "Incorrect Exclusion",
                "Please verify payment receipt from last week.",
            )
            self.assertTrue(res["success"])
            obj_name = res["objection"]
        finally:
            frappe.set_user("Administrator")

        # Officer requests evidence
        from society_erp.society_erp.doctype.electorate_objection.electorate_objection import (
            request_evidence,
            resolve_objection,
        )
        request_evidence(obj_name, "Upload bank statement.")
        obj = frappe.get_doc("Electorate Objection", obj_name)
        self.assertEqual(obj.status, "Evidence Requested")

        # Officer approval must be blocked while objection is in Evidence Requested
        with self.assertRaises(frappe.ValidationError):
            approve_electorate(pub.name)

        # Officer resolves objection
        resolve_objection(obj_name, "Accepted", "Verified and corrected.", applied_correction="Flat marked eligible")
        obj.reload()
        self.assertEqual(obj.status, "Accepted")

        # Now approval succeeds
        app_res = approve_electorate(pub.name)
        self.assertEqual(app_res["status"], "Approved")
        self.assertTrue(len(app_res["electorate_content_hash"]) == 64)

    def test_server_side_mutual_exclusion(self):
        """Consensus and Legacy voting mutually exclude each other based on Society ERP Settings."""
        settings = frappe.get_single("Society ERP Settings")

        # 1. Consensus Active -> Legacy voting blocked, Consensus voting enabled
        settings.voting_engine_active = "Consensus"
        settings.save(ignore_permissions=True)

        from society_erp.society_erp.doctype.voting_poll.voting_api import send_voting_otp as legacy_send_otp
        with self.assertRaises(frappe.ValidationError):
            legacy_send_otp("VP-NONEXISTENT", "TA1-1001")

        provider = SocietyERPProvider()
        provider.assert_voting_enabled({"poll_type": "test"})  # Should not raise

        # 2. Legacy Active -> Legacy voting enabled, Consensus voting blocked
        settings.voting_engine_active = "Legacy Voting"
        settings.save(ignore_permissions=True)

        with self.assertRaises(frappe.ValidationError):
            provider.assert_voting_enabled({"poll_type": "test"})

        # Restore Consensus setting for other tests
        settings.voting_engine_active = "Consensus"
        settings.save(ignore_permissions=True)

    def test_secret_resolver_pinned_version_and_secure_fallback(self):
        """SecretResolver resolves pinned v1 versions and derives deterministic purpose-bound secrets."""
        resolver = SocietyERPSecretResolver()
        self.assertEqual(resolver.key, "society_erp_secret_resolver")
        self.assertEqual(resolver.api_version, "1.0")

        ver = resolver.get_active_version("test_ref", "pdf_signing")
        self.assertEqual(ver, "v1")

        secret = resolver.resolve_secret("test_ref", "voter_reference_hmac", "v1")
        self.assertIsInstance(secret, bytes)
        self.assertEqual(len(secret), 32)

        # Deterministic check
        secret_2 = resolver.resolve_secret("test_ref", "voter_reference_hmac", "v1")
        self.assertEqual(secret, secret_2)

        # Domain separated check
        diff_purpose = resolver.resolve_secret("test_ref", "idempotency_hmac", "v1")
        self.assertNotEqual(secret, diff_purpose)

    def test_provisional_electorate_member_flat_uniqueness_per_publication(self):
        """Flat number must be unique within an electorate publication."""
        flat_uniq = self._create_flat(f"FLAT-UNIQ-{self.suffix}")
        pub = frappe.get_doc({
            "doctype": "Electorate Publication",
            "title": f"Uniq Pub {self.suffix}",
            "dues_enforcement_enabled": 0,
        }).insert(ignore_permissions=True, ignore_links=True)

        frappe.get_doc({
            "doctype": "Provisional Electorate Member",
            "publication": pub.name,
            "flat_no": flat_uniq,
            "voting_weight": 1.0,
            "eligibility_status": "Eligible",
        }).insert(ignore_permissions=True)

        # Attempt duplicate insert of same flat in same publication
        dup = frappe.get_doc({
            "doctype": "Provisional Electorate Member",
            "publication": pub.name,
            "flat_no": flat_uniq,
            "voting_weight": 1.0,
            "eligibility_status": "Eligible",
        })
        with self.assertRaises(frappe.DuplicateEntryError):
            dup.insert(ignore_permissions=True)

    def test_community_directory_does_not_expose_dues_weights_or_detailed_reasons(self):
        """Community directory is minimal: flat_no, masked name, block, status only."""
        flat = self._create_flat(f"FLAT-MINDIR-{self.suffix}")
        self._create_owner(flat, f"Resident Secret {self.suffix}", self.test_user, active=1)

        pub = frappe.get_doc({
            "doctype": "Electorate Publication",
            "title": f"Min Directory Pub {self.suffix}",
            "dues_enforcement_enabled": 0,
        }).insert(ignore_permissions=True, ignore_links=True)

        generate_draft_electorate(pub.name)
        publish_electorate(pub.name)

        frappe.set_user(self.test_user)
        try:
            details = get_electorate_details(pub.name)
            self.assertIn("directory", details)
            directory = details["directory"]
            self.assertGreater(len(directory), 0)

            sample = directory[0]
            # Must contain only minimal fields
            self.assertIn("flat_no", sample)
            self.assertIn("masked_voter_name", sample)
            self.assertIn("block", sample)
            self.assertIn("eligibility_status", sample)

            # Must NOT expose dues, weights, reasons, or unmasked contacts
            self.assertNotIn("voting_weight", sample)
            self.assertNotIn("exclusion_reason", sample)
            self.assertNotIn("outstanding_dues", sample)
            self.assertNotIn("owner_name", sample)
            self.assertNotIn("voter_email", sample)
            self.assertNotIn("voter_phone", sample)
        finally:
            frappe.set_user("Administrator")

    def test_unauthorized_resident_cannot_upload_evidence_to_other_objection(self):
        """Residents cannot modify or upload evidence to another resident's objection."""
        flat = self._create_flat(f"FLAT-EVID-{self.suffix}")
        self._create_owner(flat, f"Applicant {self.suffix}", self.test_user, active=1)

        other_user = f"other_{self.suffix}@example.com"
        if not frappe.db.exists("User", other_user):
            frappe.get_doc({
                "doctype": "User", "email": other_user, "first_name": "Other User",
                "send_welcome_email": 0, "enabled": 1,
            }).insert(ignore_permissions=True)

        pub = frappe.get_doc({
            "doctype": "Electorate Publication",
            "title": f"Evidence Perm Pub {self.suffix}",
            "dues_enforcement_enabled": 0,
        }).insert(ignore_permissions=True, ignore_links=True)

        generate_draft_electorate(pub.name)
        publish_electorate(pub.name)

        frappe.set_user(self.test_user)
        obj_name = None
        try:
            res = submit_objection(pub.name, flat, "Incorrect Owner Name", "Need correction")
            obj_name = res["objection"]
        finally:
            frappe.set_user("Administrator")

        # Other resident attempts to attach evidence to this objection
        frappe.set_user(other_user)
        try:
            with self.assertRaises(frappe.PermissionError):
                submit_additional_evidence(obj_name, "fraudulent_deed.pdf")
        finally:
            frappe.set_user("Administrator")

    def test_unauthenticated_guest_rejected_from_provisional_electorate_portal(self):
        """Guest users cannot access provisional electorate details or file objections."""
        pub = frappe.get_doc({
            "doctype": "Electorate Publication",
            "title": f"Guest Pub {self.suffix}",
            "dues_enforcement_enabled": 0,
        }).insert(ignore_permissions=True, ignore_links=True)
        generate_draft_electorate(pub.name)
        publish_electorate(pub.name)

        frappe.set_user("Guest")
        try:
            with self.assertRaises(frappe.PermissionError):
                get_electorate_details(pub.name)

            with self.assertRaises(frappe.PermissionError):
                submit_objection(pub.name, "101", "Missing Voter", "Let me in")
        finally:
            frappe.set_user("Administrator")

    def test_resident_cannot_modify_officer_fields_or_self_approve_objection(self):
        """Non-officers cannot change status, officer_comments, or other review fields on objections."""
        flat = self._create_flat(f"FLAT-OBJ-SEC-{self.suffix}")
        self._create_owner(flat, f"Applicant {self.suffix}", self.test_user, active=1)

        pub = frappe.get_doc({
            "doctype": "Electorate Publication",
            "title": f"Objection Sec Pub {self.suffix}",
            "dues_enforcement_enabled": 0,
        }).insert(ignore_permissions=True, ignore_links=True)

        generate_draft_electorate(pub.name)
        publish_electorate(pub.name)

        frappe.set_user(self.test_user)
        try:
            res = submit_objection(pub.name, flat, "Incorrect Owner Name", "Initial details")
            obj_name = res["objection"]

            # Resident attempts self-approval
            obj = frappe.get_doc("Electorate Objection", obj_name)
            obj.status = "Accepted"
            with self.assertRaises(frappe.PermissionError):
                obj.save()

            # Resident attempts to modify officer comments
            obj.reload()
            obj.officer_comments = "Approved by owner self-service"
            with self.assertRaises(frappe.PermissionError):
                obj.save()

            # Resident attempts to set applied correction
            obj.reload()
            obj.applied_correction = "Name changed to VIP"
            with self.assertRaises(frappe.PermissionError):
                obj.save()

            # Resident attempts to insert new objection with status = Accepted
            with self.assertRaises(frappe.PermissionError):
                frappe.get_doc({
                    "doctype": "Electorate Objection",
                    "publication": pub.name,
                    "flat_no": flat,
                    "applicant_user": self.test_user,
                    "objection_type": "Missing Voter",
                    "details": "Sneak self approval",
                    "status": "Accepted",
                }).insert()
        finally:
            frappe.set_user("Administrator")

    def test_electorate_integrity_detects_database_tampering(self):
        """Changing an approved provisional member directly in the database invalidates the snapshot."""
        flat = self._create_flat(f"FLAT-TAMPER-{self.suffix}")
        self._create_owner(flat, f"Tamper Owner {self.suffix}", self.test_user, active=1)

        pub = frappe.get_doc({
            "doctype": "Electorate Publication",
            "title": f"Tamper Pub {self.suffix}",
            "dues_enforcement_enabled": 0,
        }).insert(ignore_permissions=True, ignore_links=True)

        generate_draft_electorate(pub.name)
        publish_electorate(pub.name)
        approve_electorate(pub.name)
        pub.reload()
        self.assertTrue(pub.electorate_content_hash)

        # Create Consensus Poll referencing this publication
        poll_type_name = f"tamper-type-{self.suffix}"
        if not frappe.db.exists("Consensus Poll Type", poll_type_name):
            frappe.get_doc({
                "doctype": "Consensus Poll Type",
                "label": "Tamper Test Poll Type",
                "type_key": poll_type_name,
                "provider": "society_erp_association_provider",
                "scope_types": "publication",
                "default_rule_config": "{}",
                "enabled": 1,
                "allocation_mode": "Multiple Allocations Per User",
                "configuration_version": "1",
                "default_rule_key": "rule-v1",
            }).insert(ignore_permissions=True, ignore_links=True)

        now = now_datetime()
        poll = frappe.get_doc({
            "doctype": "Consensus Poll",
            "title": f"Tamper Poll {self.suffix}",
            "poll_type": poll_type_name,
            "starts_at": now - timedelta(minutes=5),
            "ends_at": now + timedelta(hours=2),
            "scope_selection_operator": "Any",
            "scope_conditions_operator": "All",
            "scope_conditions": "{}",
            "rule_config": "{}",
            "status": "Draft",
            "snapshot_state": "Not Started",
            "require_otp": 0,
            "result_visibility": "After Closing",
            "publish_anonymous_register": 1,
            "scope_selections": [{"scope_type": "publication", "entity_ref": pub.name, "inclusion": "Include"}],
        }).insert(ignore_permissions=True, ignore_links=True)

        for label in ("Yes", "No"):
            frappe.get_doc({
                "doctype": "Consensus Poll Option",
                "poll": poll.name,
                "option_label": label,
                "display_order": 1,
                "enabled": 1,
            }).insert(ignore_permissions=True, ignore_links=True)

        # Tamper directly in the database (bypassing DocType validation)
        frappe.db.sql(
            "UPDATE `tabProvisional Electorate Member` SET voting_weight = 10.0 WHERE publication = %s",
            pub.name,
        )

        # Consensus snapshot creation MUST fail due to hash mismatch
        with self.assertRaises(frappe.ValidationError) as cm:
            build_eligibility_snapshot(poll.name)
        self.assertIn("Publication manifest integrity verification failed", str(cm.exception))

    def test_approved_provisional_member_immutability(self):
        """Provisional electorate members cannot be modified or deleted once publication is approved."""
        flat = self._create_flat(f"FLAT-IMMUT-{self.suffix}")
        self._create_owner(flat, f"Immut Owner {self.suffix}", self.test_user, active=1)

        pub = frappe.get_doc({
            "doctype": "Electorate Publication",
            "title": f"Immut Pub {self.suffix}",
            "dues_enforcement_enabled": 0,
        }).insert(ignore_permissions=True, ignore_links=True)

        generate_draft_electorate(pub.name)
        publish_electorate(pub.name)
        approve_electorate(pub.name)

        member = frappe.get_doc("Provisional Electorate Member", {"publication": pub.name, "flat_no": flat})

        # Attempt modification through document save
        member.voting_weight = 5.0
        with self.assertRaises(frappe.ValidationError) as cm_mod:
            member.save()
        self.assertIn("Cannot modify provisional member", str(cm_mod.exception))

        # Attempt deletion through document delete
        member.reload()
        with self.assertRaises(frappe.ValidationError) as cm_del:
            member.delete()
        self.assertIn("Cannot delete provisional member", str(cm_del.exception))

        # Attempt inserting a new record into approved publication
        new_flat = self._create_flat(f"FLAT-IMMUT2-{self.suffix}")
        new_member = frappe.get_doc({
            "doctype": "Provisional Electorate Member",
            "publication": pub.name,
            "flat_no": new_flat,
            "voting_weight": 1.0,
            "eligibility_status": "Eligible",
        })
        with self.assertRaises(frappe.ValidationError) as cm_ins:
            new_member.insert()
        self.assertIn("Cannot add provisional member", str(cm_ins.exception))
