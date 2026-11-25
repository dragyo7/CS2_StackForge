from __future__ import annotations

import asyncio

from app.providers.cswatch import CSWatchProvider
from app.providers.external import FaceitProvider, LeetifyProvider
from app.providers.steam import SteamProvider


def test_providers_fail_safe_when_unconfigured_or_missing_id():
    steam = SteamProvider(api_key="", use_public_xml=False)
    faceit = FaceitProvider(api_key="")
    leetify = LeetifyProvider(api_key="")
    cswatch = CSWatchProvider()

    async def _run():
        s_sum = await steam.fetch_summaries(["76561198000000001"])
        s_ban = await steam.fetch_bans(["76561198000000001"])
        van_id, van_status = await steam.resolve_vanity_url("custom")
        f_res = await faceit.fetch_by_steam_id64("76561198000000001")
        l_nolink = await leetify.fetch_by_steam_id64(None)
        cw_nolink = await cswatch.fetch_player(None)
        return s_sum, s_ban, van_id, van_status, f_res, l_nolink, cw_nolink

    s_sum, s_ban, van_id, van_status, f_res, l_nolink, cw_nolink = asyncio.run(_run())
    assert s_sum["76561198000000001"].status == "NOT_CONFIGURED"
    assert s_ban["76561198000000001"].status == "NOT_CONFIGURED"
    assert van_id is None and van_status == "NOT_CONFIGURED"
    assert f_res.status == "NOT_CONFIGURED"
    assert l_nolink.status == "NOT_LINKED"
    assert cw_nolink.status == "NOT_LINKED"
