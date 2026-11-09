"""Society ERP SecretResolver implementation for Consensus integration."""
from __future__ import annotations

import hashlib
import hmac
from typing import Any

import frappe
from consensus.security.secrets import SecretResolutionError

SECRET_RESOLVER_API_VERSION = "1.0"


class SocietyERPSecretResolver:
    key = "society_erp_secret_resolver"
    api_version = SECRET_RESOLVER_API_VERSION

    def get_active_version(self, reference: str, purpose: str) -> str:
        # Check if site_config specifies key versions
        keys_conf = frappe.conf.get("society_voting_keys") or {}
        if isinstance(keys_conf, dict) and reference in keys_conf:
            ref_val = keys_conf[reference]
            if isinstance(ref_val, dict):
                return str(ref_val.get("active_version", "v1"))
        return "v1"

    def resolve_secret(self, reference: str, purpose: str, version: str) -> bytes:
        # 1. Check if explicitly provided in site_config.json
        keys_conf = frappe.conf.get("society_voting_keys") or {}
        if isinstance(keys_conf, dict):
            # Check by reference and version
            ref_val = keys_conf.get(reference)
            if isinstance(ref_val, dict):
                secret = ref_val.get(version) or ref_val.get("secret")
                if secret:
                    return secret.encode("utf-8") if isinstance(secret, str) else bytes(secret)
            elif isinstance(ref_val, (str, bytes)):
                return ref_val.encode("utf-8") if isinstance(ref_val, str) else bytes(ref_val)
            # Check by purpose
            purpose_val = keys_conf.get(purpose)
            if isinstance(purpose_val, dict):
                secret = purpose_val.get(version) or purpose_val.get("secret")
                if secret:
                    return secret.encode("utf-8") if isinstance(secret, str) else bytes(secret)
            elif isinstance(purpose_val, (str, bytes)):
                return purpose_val.encode("utf-8") if isinstance(purpose_val, str) else bytes(purpose_val)

        # 2. Derive cryptographically secure purpose-bound 32-byte secret from site encryption_key
        base_key = frappe.conf.get("encryption_key")
        if not base_key:
            raise SecretResolutionError("Site encryption_key is not configured in site_config.json.")

        key_bytes = base_key.encode("utf-8") if isinstance(base_key, str) else bytes(base_key)
        info = f"consensus:{purpose}:{reference}:{version}".encode()
        return hmac.new(key_bytes, info, hashlib.sha256).digest()
