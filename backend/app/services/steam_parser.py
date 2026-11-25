from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

STEAM_ID64_RE = re.compile(r"^7656119\d{10}$")
STEAM_PROFILE_PATH_RE = re.compile(r"^/profiles/(7656119\d{10})(?:/.*)?$", re.IGNORECASE)
STEAM_VANITY_PATH_RE = re.compile(r"^/id/([A-Za-z0-9_-]{2,64})(?:/.*)?$", re.IGNORECASE)

VALID_ROLES = ("Entry", "Rifler", "AWPer", "Support", "Lurker", "IGL")


@dataclass(frozen=True)
class ParsedImportLine:
    raw: str
    kind: str  # STEAM_ID64 | STEAM_VANITY | MANUAL_NAME | INVALID
    steam_id64: str | None = None
    steam_profile_url: str | None = None
    vanity_name: str | None = None
    display_name: str | None = None
    manual_rating: float | None = None
    primary_role: str | None = None
    error: str | None = None


def is_valid_steam_id64(value: str | None) -> bool:
    if not value:
        return False
    return bool(STEAM_ID64_RE.match(value.strip()))


def normalize_steam_url_or_id(raw_value: str) -> tuple[str | None, str | None, str | None]:
    """
    Returns (steam_id64, canonical_profile_url, vanity_name).
    Never invents a SteamID64 from a vanity or display name.
    """
    text = raw_value.strip()
    if not text:
        return None, None, None

    if is_valid_steam_id64(text):
        return text, f"https://steamcommunity.com/profiles/{text}", None

    candidate_url = text
    if candidate_url.startswith("steamcommunity.com/"):
        candidate_url = f"https://{candidate_url}"

    if "://" in candidate_url:
        parsed = urlparse(candidate_url)
        host = (parsed.netloc or "").lower()
        if host not in {"steamcommunity.com", "www.steamcommunity.com"}:
            return None, None, None
        m_prof = STEAM_PROFILE_PATH_RE.match(parsed.path)
        if m_prof:
            sid = m_prof.group(1)
            return sid, f"https://steamcommunity.com/profiles/{sid}", None
        m_van = STEAM_VANITY_PATH_RE.match(parsed.path)
        if m_van:
            vanity = m_van.group(1)
            return None, f"https://steamcommunity.com/id/{vanity}", vanity
        return None, None, None

    return None, None, None


def _normalize_role(token: str | None) -> str | None:
    if not token:
        return None
    cleaned = token.strip().lower()
    for role in VALID_ROLES:
        if role.lower() == cleaned:
            return role
    aliases = {"awp": "AWPer", "igl": "IGL", "supp": "Support", "lurk": "Lurker", "rifle": "Rifler"}
    return aliases.get(cleaned)


def parse_import_line(raw_line: str) -> ParsedImportLine:
    """
    Parses a single bulk-import line.
    Supports:
    - SteamID64: 76561198000000000
    - Steam profile URL: https://steamcommunity.com/profiles/76561198000000000
    - Steam vanity URL: https://steamcommunity.com/id/customname
    - Display name: Nickname
    - Delimited convenience: Nickname | SteamID64/URL | Rating | Role
    """
    raw = raw_line.strip()
    if not raw:
        return ParsedImportLine(raw=raw_line, kind="INVALID", error="Empty line")

    # Check if delimited by '|' or ',' (but not inside URL)
    parts: list[str] | None = None
    if "|" in raw:
        parts = [p.strip() for p in raw.split("|")]
    elif "," in raw and "steamcommunity.com" not in raw.lower():
        parts = [p.strip() for p in raw.split(",")]
    elif "," in raw:
        parts = [p.strip() for p in raw.split(",")]

    if parts and len(parts) >= 2:
        name_part: str | None = None
        steam_id64: str | None = None
        steam_url: str | None = None
        vanity: str | None = None
        rating: float | None = None
        role: str | None = None

        for part in parts:
            if not part:
                continue
            sid, url, van = normalize_steam_url_or_id(part)
            if sid or van:
                steam_id64 = sid or steam_id64
                steam_url = url or steam_url
                vanity = van or vanity
                continue
            r = _normalize_role(part)
            if r:
                role = r
                continue
            try:
                num = float(part)
                if 1.0 <= num <= 100.0:
                    rating = num
                    continue
            except ValueError:
                pass
            if name_part is None:
                name_part = part

        if steam_id64:
            return ParsedImportLine(
                raw=raw,
                kind="STEAM_ID64",
                steam_id64=steam_id64,
                steam_profile_url=steam_url,
                display_name=name_part,
                manual_rating=rating,
                primary_role=role,
            )
        if vanity:
            return ParsedImportLine(
                raw=raw,
                kind="STEAM_VANITY",
                steam_profile_url=steam_url,
                vanity_name=vanity,
                display_name=name_part,
                manual_rating=rating,
                primary_role=role,
            )
        if name_part:
            return ParsedImportLine(
                raw=raw,
                kind="MANUAL_NAME",
                display_name=name_part,
                manual_rating=rating,
                primary_role=role,
            )
        return ParsedImportLine(raw=raw, kind="INVALID", error="Could not parse entry")

    sid, url, van = normalize_steam_url_or_id(raw)
    if sid:
        return ParsedImportLine(raw=raw, kind="STEAM_ID64", steam_id64=sid, steam_profile_url=url)
    if van:
        return ParsedImportLine(raw=raw, kind="STEAM_VANITY", steam_profile_url=url, vanity_name=van)

    if "://" in raw or raw.lower().startswith("http") or "/" in raw:
        return ParsedImportLine(
            raw=raw,
            kind="INVALID",
            error="Unsupported URL format. Expected Steam /profiles/<17-digit-id> or /id/<vanity> URL.",
        )

    if len(raw) > 100:
        return ParsedImportLine(raw=raw, kind="INVALID", error="Display name exceeds 100 characters.")

    return ParsedImportLine(raw=raw, kind="MANUAL_NAME", display_name=raw)
