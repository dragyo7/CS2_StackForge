from __future__ import annotations

import asyncio

from app.providers.external import FaceitProvider, LeetifyProvider
from app.providers.steam import SteamProvider


def test_providers_fail_safe_when_unconfigured():
    steam = SteamProvider(api_key="")
    faceit = FaceitProvider(api_key="")
    leetify = LeetifyProvider(api_key="")

    async def _run():
        s_sum = await steam.fetch_summaries(["76561198000000001"])
        s_ban = await steam.fetch_bans(["76561198000000001"])
        van_id, van_status = await steam.resolve_vanity_url("custom")
        f_res = await faceit.fetch_by_steam_id64("76561198000000001")
        l_res = await leetify.fetch_by_steam_id64("76561198000000001")
        return s_sum, s_ban, van_id, van_status, f_res, l_res

    s_sum, s_ban, van_id, van_status, f_res, l_res = asyncio.run(_run())
    assert s_sum["76561198000000001"].status == "NOT_CONFIGURED"
    assert s_ban["76561198000000001"].status == "NOT_CONFIGURED"
    assert van_id is None and van_status == "NOT_CONFIGURED"
    assert f_res.status == "NOT_CONFIGURED"
    assert l_res.status == "NOT_CONFIGURED"
