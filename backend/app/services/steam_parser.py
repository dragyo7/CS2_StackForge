from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

STEAM_ID64_RE = re.compile(r"^7656119\d{10}$")
STEAM_PROFILE_PATH_RE = re.compile(r"^/profiles/(7656119\d{10})(?:/.*)?$", re.IGNORECASE)
STEAM_VANITY_PATH_RE = re.compile(r"^/id/([A-Za-z0-9_-]{2,64})(?:/.*)?$", re.IGNORECASE)
CSSTATS_PATH_RE = re.compile(r"^/player/(7656119\d{10})(?:/.*)?$", re.IGNORECASE)
LEETIFY_SID_PATH_RE = re.compile(r"^/(?:app/)?profile/(7656119\d{10})(?:/.*)?$", re.IGNORECASE)
LEETIFY_UUID_PATH_RE = re.compile(r"^/(?:app/)?profile/([0-9a-f-]{36})(?:/.*)?$", re.IGNORECASE)
FACEIT_PATH_RE = re.compile(r"^/(?:[a-z]{2}/)?players/([A-Za-z0-9_-]{2,64})(?:/.*)?$", re.IGNORECASE)
CSWATCH_PATH_RE = re.compile(r"^/player/(7656119\d{10})(?:/.*)?$", re.IGNORECASE)

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
    source_provider: str | None = None
    source_profile_url: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class UniversalIdentifier:
    raw: str
    identifier_type: str  # steam_id64 | steam_profile_url | steam_vanity_url | csstats_url | leetify_url | faceit_url | cswatch_url | nickname | invalid
    normalized_value: str
    steam_id64: str | None = None
    vanity_name: str | None = None
    faceit_nickname: str | None = None
    leetify_uuid: str | None = None
    profile_url: str | None = None


def is_valid_steam_id64(value: str | None) -> bool:
    if not value:
        return False
    return bool(STEAM_ID64_RE.match(value.strip()))


def normalize_steam_url_or_id(raw_value: str) -> tuple[str | None, str | None, str | None]:
    """
    Normalizes SteamID64, Steam /profiles/, Steam /id/, CSStats /player/{sid64},
    Leetify /profile/{sid64}, and CSWatch /player/{sid64}.
    Never invents a SteamID64 from a vanity or display name.
    """
    text = raw_value.strip()
    if not text:
        return None, None, None

    if is_valid_steam_id64(text):
        return text, f"https://steamcommunity.com/profiles/{text}", None

    candidate_url = text
    if any(
        candidate_url.lower().startswith(dom)
        for dom in ("steamcommunity.com/", "csstats.gg/", "leetify.com/", "cswatch.gg/", "www.faceit.com/")
    ):
        candidate_url = f"https://{candidate_url}"

    if "://" in candidate_url:
        parsed = urlparse(candidate_url)
        host = (parsed.netloc or "").lower()
        if host in {"steamcommunity.com", "www.steamcommunity.com"}:
            m_prof = STEAM_PROFILE_PATH_RE.match(parsed.path)
            if m_prof:
                sid = m_prof.group(1)
                return sid, f"https://steamcommunity.com/profiles/{sid}", None
            m_van = STEAM_VANITY_PATH_RE.match(parsed.path)
            if m_van:
                vanity = m_van.group(1)
                return None, f"https://steamcommunity.com/id/{vanity}", vanity
        elif host in {"csstats.gg", "www.csstats.gg"}:
            m_cs = CSSTATS_PATH_RE.match(parsed.path)
            if m_cs:
                sid = m_cs.group(1)
                return sid, f"https://steamcommunity.com/profiles/{sid}", None
        elif host in {"leetify.com", "www.leetify.com"}:
            m_lt = LEETIFY_SID_PATH_RE.match(parsed.path)
            if m_lt:
                sid = m_lt.group(1)
                return sid, f"https://steamcommunity.com/profiles/{sid}", None
        elif host in {"cswatch.gg", "www.cswatch.gg"}:
            m_cw = CSWATCH_PATH_RE.match(parsed.path)
            if m_cw:
                sid = m_cw.group(1)
                return sid, f"https://steamcommunity.com/profiles/{sid}", None
        return None, None, None

    return None, None, None


def detect_universal_identifier(raw_input: str) -> UniversalIdentifier:
    text = raw_input.strip()
    if not text:
        return UniversalIdentifier(raw=raw_input, identifier_type="invalid", normalized_value="")

    if is_valid_steam_id64(text):
        return UniversalIdentifier(
            raw=raw_input,
            identifier_type="steam_id64",
            normalized_value=text,
            steam_id64=text,
            profile_url=f"https://steamcommunity.com/profiles/{text}",
        )

    candidate_url = text
    if any(
        candidate_url.lower().startswith(dom)
        for dom in ("steamcommunity.com/", "csstats.gg/", "leetify.com/", "cswatch.gg/", "faceit.com/", "www.faceit.com/")
    ):
        candidate_url = f"https://{candidate_url}"

    if "://" in candidate_url:
        parsed = urlparse(candidate_url)
        host = (parsed.netloc or "").lower()
        if host in {"steamcommunity.com", "www.steamcommunity.com"}:
            m_prof = STEAM_PROFILE_PATH_RE.match(parsed.path)
            if m_prof:
                sid = m_prof.group(1)
                return UniversalIdentifier(
                    raw=raw_input,
                    identifier_type="steam_profile_url",
                    normalized_value=sid,
                    steam_id64=sid,
                    profile_url=f"https://steamcommunity.com/profiles/{sid}",
                )
            m_van = STEAM_VANITY_PATH_RE.match(parsed.path)
            if m_van:
                van = m_van.group(1)
                return UniversalIdentifier(
                    raw=raw_input,
                    identifier_type="steam_vanity_url",
                    normalized_value=van,
                    vanity_name=van,
                    profile_url=f"https://steamcommunity.com/id/{van}",
                )
        elif host in {"csstats.gg", "www.csstats.gg"}:
            m_cs = CSSTATS_PATH_RE.match(parsed.path)
            if m_cs:
                sid = m_cs.group(1)
                return UniversalIdentifier(
                    raw=raw_input,
                    identifier_type="csstats_url",
                    normalized_value=sid,
                    steam_id64=sid,
                    profile_url=f"https://csstats.gg/player/{sid}",
                )
        elif host in {"leetify.com", "www.leetify.com"}:
            m_lt = LEETIFY_SID_PATH_RE.match(parsed.path)
            if m_lt:
                sid = m_lt.group(1)
                return UniversalIdentifier(
                    raw=raw_input,
                    identifier_type="leetify_url",
                    normalized_value=sid,
                    steam_id64=sid,
                    profile_url=f"https://leetify.com/app/profile/{sid}",
                )
            m_uuid = LEETIFY_UUID_PATH_RE.match(parsed.path)
            if m_uuid:
                uid = m_uuid.group(1)
                return UniversalIdentifier(
                    raw=raw_input,
                    identifier_type="leetify_url",
                    normalized_value=uid,
                    leetify_uuid=uid,
                    profile_url=f"https://leetify.com/app/profile/{uid}",
                )
        elif host in {"cswatch.gg", "www.cswatch.gg"}:
            m_cw = CSWATCH_PATH_RE.match(parsed.path)
            if m_cw:
                sid = m_cw.group(1)
                return UniversalIdentifier(
                    raw=raw_input,
                    identifier_type="cswatch_url",
                    normalized_value=sid,
                    steam_id64=sid,
                    profile_url=f"https://cswatch.gg/player/{sid}",
                )
        elif host in {"faceit.com", "www.faceit.com"}:
            m_fc = FACEIT_PATH_RE.match(parsed.path)
            if m_fc:
                nick = m_fc.group(1)
                return UniversalIdentifier(
                    raw=raw_input,
                    identifier_type="faceit_url",
                    normalized_value=nick,
                    faceit_nickname=nick,
                    profile_url=f"https://www.faceit.com/en/players/{nick}",
                )
        return UniversalIdentifier(raw=raw_input, identifier_type="invalid", normalized_value=text)

    return UniversalIdentifier(raw=raw_input, identifier_type="nickname", normalized_value=text)


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
    raw = raw_line.strip()
    if not raw:
        return ParsedImportLine(raw=raw_line, kind="INVALID", error="Empty line")

    parts: list[str] | None = None
    if "|" in raw:
        parts = [p.strip() for p in raw.split("|")]
    elif "," in raw:
        parts = [p.strip() for p in raw.split(",")]

    if parts and len(parts) >= 2:
        name_part: str | None = None
        steam_id64: str | None = None
        steam_url: str | None = None
        vanity: str | None = None
        rating: float | None = None
        role: str | None = None
        src_prov: str | None = None
        src_url: str | None = None

        for part in parts:
            if not part:
                continue
            det = detect_universal_identifier(part)
            if det.steam_id64:
                steam_id64 = det.steam_id64
                steam_url = f"https://steamcommunity.com/profiles/{det.steam_id64}"
                if det.identifier_type in ("csstats_url", "leetify_url", "cswatch_url"):
                    src_prov = det.identifier_type.replace("_url", "")
                    src_url = det.profile_url
                continue
            if det.vanity_name:
                vanity = det.vanity_name
                steam_url = det.profile_url
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
                source_provider=src_prov,
                source_profile_url=src_url,
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

    det = detect_universal_identifier(raw)
    if det.steam_id64:
        src_prov = det.identifier_type.replace("_url", "") if det.identifier_type in ("csstats_url", "leetify_url", "cswatch_url") else None
        return ParsedImportLine(
            raw=raw,
            kind="STEAM_ID64",
            steam_id64=det.steam_id64,
            steam_profile_url=f"https://steamcommunity.com/profiles/{det.steam_id64}",
            source_provider=src_prov,
            source_profile_url=det.profile_url if src_prov else None,
        )
    if det.vanity_name:
        return ParsedImportLine(
            raw=raw,
            kind="STEAM_VANITY",
            steam_profile_url=det.profile_url,
            vanity_name=det.vanity_name,
        )

    if "://" in raw or raw.lower().startswith("http") or "/" in raw:
        return ParsedImportLine(
            raw=raw,
            kind="INVALID",
            error="Unsupported URL format. Expected Steam /profiles/<17-digit-id>, /id/<vanity>, or CSStats/Leetify/CSWatch profile URL.",
        )

    if len(raw) > 100:
        return ParsedImportLine(raw=raw, kind="INVALID", error="Display name exceeds 100 characters.")

    return ParsedImportLine(raw=raw, kind="MANUAL_NAME", display_name=raw)
