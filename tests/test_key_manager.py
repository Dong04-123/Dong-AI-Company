"""Test: key_manager

Tests the API Key manager — key generation, listing, verification,
revocation, tenant resolution, and fingerprint masking.
All tests use temp_dir fixture + monkeypatched _KEY_FILE to
isolate file I/O from the module-level singleton.
"""

import json
import os
import re
import time
import pytest
from pathlib import Path

from dong_ai import key_manager as km


# ═══════════════════════════════════════════════════════════════
# Fixture: patch _KEY_FILE to point inside temp_dir
# ═══════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _isolated_key_file(monkeypatch, temp_dir):
    """Each test gets its own keys.json under temp_dir."""
    key_file = Path(temp_dir) / ".dong" / "keys.json"
    monkeypatch.setattr(km, "_KEY_FILE", key_file)
    # Ensure clean state
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_text("{}")
    yield


# ═══════════════════════════════════════════════════════════════
# Key Format & Generation
# ═══════════════════════════════════════════════════════════════

class TestCreateKey:
    """create_key generates valid keys."""

    def test_create_key_format(self):
        key = km.create_key("tenant-a")
        assert key.startswith("sk-")
        parts = key.split("-")
        assert len(parts) == 5  # sk + 4 hex groups
        assert parts[0] == "sk"

    def test_create_key_hex_chars_only(self):
        key = km.create_key("tenant-c")
        hex_part = key[3:].replace("-", "")
        assert re.match(r"^[0-9a-f]+$", hex_part)

    def test_create_key_unique_per_call(self):
        key1 = km.create_key("t1")
        key2 = km.create_key("t1")
        assert key1 != key2

    def test_create_key_with_description(self):
        key = km.create_key("tenant-d", description="My key")
        keys = km.list_keys()
        match = [k for k in keys if k["description"] == "My key"]
        assert len(match) == 1

    def test_create_key_persists_to_file(self):
        key = km.create_key("persist-test")
        keys = km.list_keys()
        assert len(keys) == 1


# ═══════════════════════════════════════════════════════════════
# List Keys
# ═══════════════════════════════════════════════════════════════

class TestListKeys:
    """list_keys returns keys without exposing full key."""

    def test_list_keys_returns_fingerprint_not_full_key(self):
        key = km.create_key("secret-tenant")
        keys = km.list_keys()
        for k in keys:
            fp = k["fingerprint"]
            assert fp.startswith("sk-")
            assert "..." in fp
            assert len(fp) < len(key)

    def test_list_keys_contains_metadata(self):
        km.create_key("meta-tenant", description="metadata test")
        keys = km.list_keys()
        k = keys[0]
        assert "tenant" in k
        assert "created_at" in k
        assert "description" in k
        assert "revoked" in k
        assert k["tenant"] == "meta-tenant"
        assert k["revoked"] is False

    def test_list_keys_empty_when_no_keys(self):
        keys = km.list_keys()
        assert keys == []

    def test_list_keys_multiple_keys(self):
        km.create_key("ta")
        km.create_key("tb")
        km.create_key("tc")
        keys = km.list_keys()
        assert len(keys) == 3


# ═══════════════════════════════════════════════════════════════
# Verify Key
# ═══════════════════════════════════════════════════════════════

class TestVerifyKey:
    """verify_key returns correct tenant."""

    def test_verify_valid_key(self):
        key = km.create_key("verify-tenant")
        tenant = km.verify_key(key)
        assert tenant == "verify-tenant"

    def test_verify_invalid_key_returns_none(self):
        tenant = km.verify_key("sk-inv...here")
        assert tenant is None

    def test_verify_revoked_key_returns_none(self):
        key = km.create_key("revoke-tenant")
        km.revoke_key(key)
        tenant = km.verify_key(key)
        assert tenant is None

    def test_verify_key_case_sensitive(self):
        key = km.create_key("CaseSensitive")
        tenant_upper = km.verify_key(key.upper())
        assert tenant_upper is None
        tenant_orig = km.verify_key(key)
        assert tenant_orig == "CaseSensitive"


# ═══════════════════════════════════════════════════════════════
# Revoke Key
# ═══════════════════════════════════════════════════════════════

class TestRevokeKey:
    """revoke_key marks key as revoked."""

    def test_revoke_key_returns_true(self):
        key = km.create_key("to-revoke")
        result = km.revoke_key(key)
        assert result is True

    def test_revoke_nonexistent_key_returns_false(self):
        result = km.revoke_key("sk-non...here")
        assert result is False

    def test_revoke_updates_list_keys(self):
        key = km.create_key("revoke-check")
        km.revoke_key(key)
        keys = km.list_keys()
        for k in keys:
            if k["fingerprint"] == km._key_fingerprint(key):
                assert k["revoked"] is True

    def test_revoke_by_fingerprint(self):
        key = km.create_key("fp-revoke")
        fp = km._key_fingerprint(key)
        result = km.revoke_key(fp)
        assert result is True
        assert km.verify_key(key) is None

    def test_double_revoke_idempotent(self):
        key = km.create_key("double-revoke")
        km.revoke_key(key)
        result = km.revoke_key(key)
        assert result is True
        assert km.verify_key(key) is None


# ═══════════════════════════════════════════════════════════════
# Resolve Tenants
# ═══════════════════════════════════════════════════════════════

class TestResolveTenants:
    """resolve_tenants combines env + persistent keys."""

    def test_resolve_persistent_keys(self):
        key = km.create_key("persistent-tenant")
        tenants = km.resolve_tenants()
        assert key in tenants
        assert tenants[key] == "persistent-tenant"

    def test_resolve_env_default_key(self, monkeypatch):
        monkeypatch.setenv("DONG_API_KEY", "sk-env-default-xxx")
        tenants = km.resolve_tenants()
        assert "sk-env-default-xxx" in tenants
        assert tenants["sk-env-default-xxx"] == "default"

    def test_resolve_env_multi_tenant(self, monkeypatch):
        env_keys = json.dumps({"sk-multi-1": "tenant1", "sk-multi-2": "tenant2"})
        monkeypatch.setenv("DONG_API_KEYS", env_keys)
        tenants = km.resolve_tenants()
        assert tenants["sk-multi-1"] == "tenant1"
        assert tenants["sk-multi-2"] == "tenant2"

    def test_resolve_env_overrides_persistent(self, monkeypatch):
        key = km.create_key("original-tenant")
        monkeypatch.setenv("DONG_API_KEYS", json.dumps({key: "override-tenant"}))
        tenants = km.resolve_tenants()
        assert tenants[key] == "override-tenant"

    def test_resolve_skips_revoked_keys(self):
        good_key = km.create_key("good-tenant")
        bad_key = km.create_key("bad-tenant")
        km.revoke_key(bad_key)
        tenants = km.resolve_tenants()
        assert good_key in tenants
        assert bad_key not in tenants

    def test_resolve_no_env_no_keys(self, monkeypatch):
        monkeypatch.delenv("DONG_API_KEY", raising=False)
        monkeypatch.delenv("DONG_API_KEYS", raising=False)
        tenants = km.resolve_tenants()
        assert tenants == {}

    def test_resolve_bad_env_json_ignored(self, monkeypatch):
        monkeypatch.setenv("DONG_API_KEYS", "not valid json")
        tenants = km.resolve_tenants()
        assert isinstance(tenants, dict)

    def test_resolve_combines_env_and_persistent(self, monkeypatch):
        persistent_key = km.create_key("persistent")
        monkeypatch.setenv("DONG_API_KEY", "sk-env-xxx")
        tenants = km.resolve_tenants()
        assert "sk-env-xxx" in tenants
        assert persistent_key in tenants


# ═══════════════════════════════════════════════════════════════
# Fingerprint Masking
# ═══════════════════════════════════════════════════════════════

class TestKeyFingerprint:
    """_key_fingerprint masks key properly."""

    def test_fingerprint_masks_middle(self):
        """sk-abcdef12-34567890-abcdef12-34567890 → sk-abcdef12...7890"""
        key = "sk-abcdef12-34567890-abcdef12-34567890"
        fp = km._key_fingerprint(key)
        # key[:12] = "sk-abcdef12-" (12 chars), key[-4:] = "7890"
        assert fp.startswith("sk-")
        assert "..." in fp
        assert fp.endswith("7890")

    def test_fingerprint_shorter_than_full_key(self):
        key = km.create_key("fp-length")
        fp = km._key_fingerprint(key)
        assert len(fp) < len(key)

    def test_fingerprint_consistent(self):
        key = km.create_key("fp-consistency")
        fp1 = km._key_fingerprint(key)
        fp2 = km._key_fingerprint(key)
        assert fp1 == fp2
