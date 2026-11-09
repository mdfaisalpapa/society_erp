"""Society ERP VoterProvider implementation for Consensus integration."""
from __future__ import annotations

import json
from typing import Any

import frappe
from consensus.providers.protocol import (
    CandidatePage,
    CanonicalRuleConfig,
    CanonicalScopeQuery,
    ContactDestination,
    EligibilityDecision,
    PollContext,
    ProviderSnapshotToken,
    ReceiptIdentity,
    ReceiptIdentityField,
    ScopeEntity,
    ScopeQuery,
    ScopeType,
    VoterCandidate,
)
from consensus.security.crypto import canonical_json_bytes
from frappe import _

from society_erp.voting.electorate import compute_electorate_manifest

PROVIDER_API_VERSION = "1.0"


class SocietyERPProvider:
    key = "society_erp_association_provider"
    api_version = PROVIDER_API_VERSION

    def get_metadata(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": "Society ERP Association Provider",
            "version": "1.0",
            "description": "Consensus provider backed by approved Society ERP Electorate Publications.",
        }

    def list_scope_types(self, context: dict[str, Any]) -> list[ScopeType]:
        return [
            {
                "key": "publication",
                "label": "Electorate Publication",
                "hierarchical": False,
                "multiple_entities": False,
                "supports_include_exclude": False,
                "supports_any_selection": True,
                "supports_all_selection": False,
                "description": "Select an approved Electorate Publication",
            },
            {
                "key": "group",
                "label": "Block / Hierarchy",
                "hierarchical": False,
                "multiple_entities": True,
                "supports_include_exclude": True,
                "supports_any_selection": True,
                "supports_all_selection": False,
                "description": "Blocks or publication selection",
            },
        ]

    def list_scope_entities(
        self,
        scope_type: str,
        query: str | None = None,
        parent_ref: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[ScopeEntity]:
        if scope_type == "publication":
            filters = {"status": "Approved"}
            if query:
                filters["title"] = ["like", f"%{query}%"]
            pubs = frappe.get_all("Electorate Publication", filters=filters, fields=["name", "title"])
            return [
                {
                    "entity_ref": p.name,
                    "label": p.title,
                    "parent_ref": None,
                    "hierarchy_path": [p.title],
                }
                for p in pubs
            ]
        # Default/group scope: blocks
        filters = {}
        if query:
            filters["block_name"] = ["like", f"%{query}%"]
        blocks = frappe.get_all("Block", filters=filters, fields=["name", "block_name"])
        return [
            {
                "entity_ref": b.name,
                "label": b.block_name or b.name,
                "parent_ref": None,
                "hierarchy_path": [b.block_name or b.name],
            }
            for b in blocks
        ]

    def resolve_scope_entities(
        self, scope_type: str, entity_refs: list[str], context: dict[str, Any]
    ) -> list[ScopeEntity]:
        entities = []
        for ref in entity_refs:
            if scope_type == "publication":
                pub = frappe.db.get_value("Electorate Publication", ref, ["name", "title"], as_dict=True)
                if pub:
                    entities.append({
                        "entity_ref": pub.name,
                        "label": pub.title,
                        "parent_ref": None,
                        "hierarchy_path": [pub.title],
                    })
            else:
                block = frappe.db.get_value("Block", ref, ["name", "block_name"], as_dict=True)
                label = block.block_name if block else ref
                entities.append({
                    "entity_ref": ref,
                    "label": label,
                    "parent_ref": None,
                    "hierarchy_path": [label],
                })
        return entities

    def validate_scope_query(
        self, query: ScopeQuery, poll_context: PollContext
    ) -> CanonicalScopeQuery:
        canonical_json = canonical_json_bytes(query).decode("utf-8")
        return {
            "query": query,
            "canonical_query_json": canonical_json,
            "provider_api_version": self.api_version,
        }

    def validate_rule_configuration(
        self,
        rule_key: str,
        config: dict[str, Any],
        poll_type: str,
        poll_context: PollContext,
    ) -> CanonicalRuleConfig:
        canonical_json = canonical_json_bytes(config).decode("utf-8")
        return {
            "rule_key": rule_key,
            "rule_version": "1.0",
            "config": config,
            "canonical_config_json": canonical_json,
        }

    def _resolve_publication(self, poll_context: PollContext) -> Any:
        poll_name = poll_context.get("poll_name")
        pub_id = None
        if poll_name and frappe.db.exists("Consensus Poll", poll_name):
            poll = frappe.get_doc("Consensus Poll", poll_name)
            if getattr(poll, "approved_publication_id", None):
                pub_id = poll.approved_publication_id
            else:
                for s in (poll.scope_selections or []):
                    if s.scope_type == "publication" or frappe.db.exists("Electorate Publication", s.entity_ref):
                        pub_id = s.entity_ref
                        break

        if not pub_id:
            # Fallback to the latest approved publication
            pubs = frappe.get_all(
                "Electorate Publication",
                filters={"status": "Approved"},
                order_by="creation desc",
                limit=1,
            )
            if pubs:
                pub_id = pubs[0].name

        if not pub_id:
            frappe.throw(_("No approved electorate publication found to build snapshot."))

        pub = frappe.get_doc("Electorate Publication", pub_id)
        if pub.status != "Approved":
            frappe.throw(_("Publication {0} is in status '{1}'; only 'Approved' publications can be snapshotted.").format(pub.name, pub.status))
        if not pub.electorate_content_hash:
            frappe.throw(_("Publication {0} does not have a certified electorate content hash.").format(pub.name))

        return pub

    def begin_voter_snapshot(self, poll_context: PollContext) -> ProviderSnapshotToken:
        pub = self._resolve_publication(poll_context)

        # Recompute the full canonical manifest and verify content hash before returning snapshot token
        _manifest_payload, computed_hash = compute_electorate_manifest(pub.name)
        if computed_hash != pub.electorate_content_hash:
            frappe.throw(
                _(
                    "Publication manifest integrity verification failed for '{0}': "
                    "records have been modified since approval (computed {1} != approved {2})."
                ).format(pub.name, computed_hash, pub.electorate_content_hash),
                frappe.ValidationError,
            )

        return {
            "token": f"society_erp:{pub.name}:v{pub.version}",
            "provider_data_version": f"{pub.name}:v{pub.version}",
            "approved_publication_id": pub.name,
            "approved_publication_version": int(pub.version),
            "approved_electorate_content_hash": pub.electorate_content_hash,
        }

    def get_voter_candidates(
        self,
        scope_query: ScopeQuery,
        poll_context: PollContext,
        snapshot: ProviderSnapshotToken,
        cursor: str | None,
        page_size: int,
    ) -> CandidatePage:
        pub_name = snapshot.get("approved_publication_id")
        if not pub_name:
            pub = self._resolve_publication(poll_context)
            pub_name = pub.name

        filters: dict[str, Any] = {
            "publication": pub_name,
            "eligibility_status": "Eligible",
        }
        if cursor:
            filters["flat_no"] = [">", cursor]

        members = frappe.get_all(
            "Provisional Electorate Member",
            filters=filters,
            fields=["flat_no", "owner_name", "voter_user", "voting_weight", "block", "uds", "owner_doc"],
            order_by="flat_no asc",
            limit=page_size + 1,
        )

        has_next = len(members) > page_size
        page_members = members[:page_size] if has_next else members
        next_cursor = page_members[-1].flat_no if has_next and page_members else None

        candidates: list[VoterCandidate] = []
        for m in page_members:
            candidates.append({
                "voter_ref": f"{pub_name}:{m.flat_no}",
                "frappe_user": m.voter_user,
                "voter_category": "Residential Owner",
                "context_ref": m.flat_no,
                "attributes": {
                    "flat_no": m.flat_no,
                    "voting_weight": f"{float(m.voting_weight):.3f}",
                    "owner_name": m.owner_name or "",
                    "block": m.block or "",
                    "uds": float(m.uds or 0.0),
                    "owner_doc": m.owner_doc or "",
                },
            })

        return {
            "candidates": candidates,
            "next_cursor": next_cursor,
            "snapshot": snapshot,
        }

    def evaluate_eligibility(
        self,
        candidate: VoterCandidate,
        poll_context: PollContext,
        rule_key: str,
        rule_config: dict[str, Any],
    ) -> EligibilityDecision:
        # Sourced exclusively from approved electorate publication
        weight = candidate["attributes"].get("voting_weight", "1.000")
        return {
            "eligible": True,
            "reason_code": "None",
            "voting_weight": f"{float(weight):.3f}",
            "rule_version": "1.0",
            "voter_category": candidate.get("voter_category"),
            "context_ref": candidate.get("context_ref"),
        }

    def get_receipt_identity(
        self, voter_ref: str, purpose: str, schema_version: str | None = None
    ) -> ReceiptIdentity:
        parts = voter_ref.split(":", 1)
        flat_no = parts[1] if len(parts) == 2 else parts[0]
        pub_name = parts[0] if len(parts) == 2 else None

        filters: dict[str, Any] = {"flat_no": flat_no}
        if pub_name:
            filters["publication"] = pub_name

        m = frappe.db.get_value(
            "Provisional Electorate Member",
            filters,
            ["flat_no", "owner_name", "block", "uds"],
            as_dict=True,
        )

        owner_name = (m.owner_name if m else "") or ""
        block = (m.block if m else "") or "N/A"
        uds = f"{float(m.uds):.3f}" if m and m.uds else "0.000"

        return {
            "schema_key": "society_erp_resident_identity",
            "schema_version": "1.0",
            "fields": [
                {
                    "key": "flat_no",
                    "label": "Flat / Unit",
                    "value": flat_no,
                    "display_order": 1,
                    "required": True,
                    "format_key": "text",
                },
                {
                    "key": "owner_name",
                    "label": "Owner",
                    "value": owner_name,
                    "display_order": 2,
                    "required": True,
                    "format_key": "text",
                },
                {
                    "key": "block",
                    "label": "Block",
                    "value": block,
                    "display_order": 3,
                    "required": False,
                    "format_key": "text",
                },
                {
                    "key": "uds",
                    "label": "UDS",
                    "value": uds,
                    "display_order": 4,
                    "required": False,
                    "format_key": "text",
                },
            ],
        }

    def get_contact_destination(self, voter_ref: str, channel: str) -> ContactDestination:
        parts = voter_ref.split(":", 1)
        flat_no = parts[1] if len(parts) == 2 else parts[0]
        pub_name = parts[0] if len(parts) == 2 else None

        filters: dict[str, Any] = {"flat_no": flat_no}
        if pub_name:
            filters["publication"] = pub_name

        m = frappe.db.get_value(
            "Provisional Electorate Member",
            filters,
            ["voter_email", "voter_phone"],
            as_dict=True,
        )

        if channel == "email":
            dest = (m.voter_email if m else "") or ""
            return {"channel": "email", "destination": dest}
        if channel == "sms":
            dest = (m.voter_phone if m else "") or ""
            return {"channel": "sms", "destination": dest}
        return {"channel": channel, "destination": ""}

    def assert_voting_enabled(self, poll_context: PollContext) -> None:
        try:
            engine = frappe.db.get_single_value("Society ERP Settings", "voting_engine_active", cache=False) or "Legacy Voting"
            if engine != "Consensus":
                frappe.throw(
                    _("Consensus voting is currently disabled in Society ERP Settings."),
                    frappe.ValidationError,
                )
        except frappe.DoesNotExistError:
            frappe.throw(_("Society ERP Settings does not exist."), frappe.ValidationError)
