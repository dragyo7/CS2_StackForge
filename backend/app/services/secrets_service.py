from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes
import json
import os
import sys
from pathlib import Path
from typing import Literal

import httpx

ProviderKeyName = Literal["steam", "faceit", "leetify"]

ENV_VAR_MAP: dict[str, str] = {
    "steam": "STEAM_API_KEY",
    "faceit": "FACEIT_API_KEY",
    "leetify": "LEETIFY_API_KEY",
}

DEFAULT_VAULT_PATH = Path(__file__).resolve().parent.parent.parent / ".stackforge_secrets.dpapi.json"
_vault_path_override: Path | None = None


def set_vault_path_for_tests(path: Path | None) -> None:
    global _vault_path_override
    _vault_path_override = path


def _vault_path() -> Path:
    return _vault_path_override or DEFAULT_VAULT_PATH


def _dpapi_protect(raw_bytes: bytes) -> str:
    """Encrypts bytes with Windows DPAPI (current OS user scope) when available."""
    if sys.platform == "win32":
        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", ctypes.wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_char)),
            ]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        buf = ctypes.create_string_buffer(raw_bytes, len(raw_bytes))
        in_blob = DATA_BLOB(len(raw_bytes), buf)
        out_blob = DATA_BLOB()
        if crypt32.CryptProtectData(ctypes.byref(in_blob), "StackForgeCredential", None, None, None, 0, ctypes.byref(out_blob)):
            try:
                cipher = ctypes.string_at(out_blob.pbData, out_blob.cbData)
                return "dpapi:" + base64.b64encode(cipher).decode("ascii")
            finally:
                kernel32.LocalFree(out_blob.pbData)
    # Non-Windows fallback (restricted local file storage; never stored plaintext in SQLite)
    return "b64:" + base64.b64encode(raw_bytes).decode("ascii")


def _dpapi_unprotect(token: str) -> str | None:
    if token.startswith("dpapi:") and sys.platform == "win32":
        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", ctypes.wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_char)),
            ]

        raw = base64.b64decode(token[6:].encode("ascii"))
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        buf = ctypes.create_string_buffer(raw, len(raw))
        in_blob = DATA_BLOB(len(raw), buf)
        out_blob = DATA_BLOB()
        if crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
            try:
                plain = ctypes.string_at(out_blob.pbData, out_blob.cbData)
                return plain.decode("utf-8")
            finally:
                kernel32.LocalFree(out_blob.pbData)
        return None
    if token.startswith("b64:"):
        try:
            return base64.b64decode(token[4:].encode("ascii")).decode("utf-8")
        except Exception:
            return None
    return None


def _read_vault() -> dict[str, str]:
    vp = _vault_path()
    if not vp.exists():
        return {}
    try:
        data = json.loads(vp.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_vault(data: dict[str, str]) -> None:
    vp = _vault_path()
    vp.parent.mkdir(parents=True, exist_ok=True)
    vp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _mask_secret(secret: str | None) -> str | None:
    if not secret:
        return None
    tail = secret[-4:] if len(secret) > 6 else "**"
    return f"****{tail}"


def get_secret(provider: ProviderKeyName) -> str | None:
    """Reads server-side secret from OS DPAPI vault first, then environment variable."""
    vault = _read_vault()
    encrypted = vault.get(provider)
    if encrypted:
        val = _dpapi_unprotect(encrypted)
        if val:
            return val.strip()
    env_key = ENV_VAR_MAP[provider]
    env_val = os.getenv(env_key)
    return env_val.strip() if env_val and env_val.strip() else None


def save_secret(provider: ProviderKeyName, raw_key: str) -> dict:
    clean = (raw_key or "").strip()
    if len(clean) < 8 or any(ch.isspace() for ch in clean):
        raise ValueError("API key must be at least 8 characters and contain no whitespace.")
    vault = _read_vault()
    vault[provider] = _dpapi_protect(clean.encode("utf-8"))
    _write_vault(vault)
    return get_credential_status(provider)


def delete_secret(provider: ProviderKeyName) -> dict:
    vault = _read_vault()
    vault.pop(provider, None)
    _write_vault(vault)
    return get_credential_status(provider)


def get_credential_status(provider: ProviderKeyName) -> dict:
    vault = _read_vault()
    env_val = os.getenv(ENV_VAR_MAP[provider])
    if provider in vault and _dpapi_unprotect(vault[provider]):
        val = _dpapi_unprotect(vault[provider])
        return {
            "provider": provider,
            "configured": True,
            "source": "windows_dpapi_vault" if sys.platform == "win32" else "local_vault",
            "masked_hint": _mask_secret(val),
            "env_var": ENV_VAR_MAP[provider],
        }
    if env_val and env_val.strip():
        return {
            "provider": provider,
            "configured": True,
            "source": "environment",
            "masked_hint": _mask_secret(env_val.strip()),
            "env_var": ENV_VAR_MAP[provider],
        }
    return {
        "provider": provider,
        "configured": False,
        "source": "none",
        "masked_hint": None,
        "env_var": ENV_VAR_MAP[provider],
    }


def list_credentials_status() -> list[dict]:
    return [get_credential_status("steam"), get_credential_status("faceit"), get_credential_status("leetify")]


async def validate_provider_credential(provider: ProviderKeyName, candidate_key: str | None = None) -> dict:
    """
    Validates an API key server-side without ever logging or returning the secret.
    """
    key = (candidate_key or "").strip() or get_secret(provider)
    if not key:
        return {"provider": provider, "valid": False, "status": "NOT_CONFIGURED", "message": "No key configured."}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            if provider == "steam":
                resp = await client.get(
                    "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
                    params={"key": key, "steamids": "76561197960287930"},
                )
                if resp.status_code == 200:
                    return {"provider": "steam", "valid": True, "status": "VALID", "message": "Steam Web API key accepted."}
                if resp.status_code in (401, 403):
                    return {"provider": "steam", "valid": False, "status": "INVALID", "message": "Steam Web API rejected key (403/401)."}
                return {"provider": "steam", "valid": False, "status": "UNAVAILABLE", "message": f"Steam validation returned HTTP {resp.status_code}."}

            if provider == "faceit":
                resp = await client.get(
                    "https://open.faceit.com/data/v4/players",
                    params={"nickname": "NiKo"},
                    headers={"Authorization": f"Bearer {key}"},
                )
                if resp.status_code == 200:
                    return {"provider": "faceit", "valid": True, "status": "VALID", "message": "FACEIT Data API v4 key accepted."}
                if resp.status_code in (401, 403):
                    return {"provider": "faceit", "valid": False, "status": "INVALID", "message": "FACEIT Data API rejected key (401/403)."}
                return {"provider": "faceit", "valid": False, "status": "UNAVAILABLE", "message": f"FACEIT validation returned HTTP {resp.status_code}."}

            if provider == "leetify":
                resp = await client.get(
                    "https://api-public.cs-prod.leetify.com/api-key/validate",
                    headers={"_leetify_key": key, "Authorization": f"Bearer {key}"},
                )
                if resp.status_code == 200:
                    return {"provider": "leetify", "valid": True, "status": "VALID", "message": "Leetify API key validated."}
                if resp.status_code in (401, 403):
                    return {"provider": "leetify", "valid": False, "status": "INVALID", "message": "Leetify API rejected key."}
                return {"provider": "leetify", "valid": False, "status": "UNAVAILABLE", "message": f"Leetify validation returned HTTP {resp.status_code}."}
    except Exception:
        return {"provider": provider, "valid": False, "status": "UNAVAILABLE", "message": "Upstream validation timed out or failed (no secret exposed)."}

    return {"provider": provider, "valid": False, "status": "FAILED", "message": "Unsupported credential provider."}
