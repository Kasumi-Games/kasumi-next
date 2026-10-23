"""Plugin-owned compositions for Manosaba, selected before generic card layout.

The adapters consume the same display models as their plugins. They choose
their own page geometry; no generic card tree is restyled or rearranged here.
Imports stay lazy because plugin packages initialise NoneBot handlers.
"""

from importlib import import_module

from ..kit import ManosabaKit
from .folio import FolioPage

ROUTES = {
    "inventory.profile": "inventory.profile",
    "inventory.list": "inventory.listing",
    "inventory.season_rank": "inventory.season_rank",
    "inventory.season_info": "inventory.season_info",
    "inventory.trend": "inventory.trend",
    "daily.checkin": "daily.checkin",
    "daily.rank": "daily.rank",
    "help.board": "help.board",
    "help.detail": "help.detail",
    "gacha.banner": "gacha.banner",
    "gacha.pull": "gacha.pull",
    "gacha.history": "gacha.history",
    "mailbox.inbox": "mailbox.inbox",
    "mailbox.mail": "mailbox.mail",
    "mailbox.claim": "mailbox.claim",
    "red_envelope.create": "envelopes.create",
    "red_envelope.list": "envelopes.listing",
    "red_envelope.completion": "envelopes.completion",
    "blackjack.help": "blackjack.help_page",
    "blackjack.table": "blackjack.table",
    "blackjack.stats": "blackjack.stats",
    "mines.board": "mines.board",
    "mines.result": "mines.result",
    "mines.stats": "mines.stats",
    "one_stroke.board": "one_stroke.board",
    "one_stroke.rank": "one_stroke.rank",
    "one_stroke.result": "one_stroke.result",
    "cck.reveal": "reveals.cck",
    "guess_chart.reveal": "reveals.chart",
    "tour.help": "tour.help_page",
    "tour.state": "tour.state",
    "tour.result": "tour.result",
    "tour.rank": "tour.rank",
    "ryuseido.preview": "shop.preview",
}


def page_for(kit, route: str, *args, **kwargs):
    """Return a deferred native composition, or leave another kit's path alone."""
    if not isinstance(kit, ManosabaKit):
        return None
    module, name = ROUTES[route].split(".")
    adapter = import_module(f"{__name__}.{module}")
    surface = getattr(adapter, name)
    if module == "mailbox":
        # Catalog access uses the inventory session on the caller's thread.
        kwargs["prepared"] = adapter.prepare(name, *args, **kwargs)
    return FolioPage(kit, surface, args, kwargs)


__all__ = ["page_for", "FolioPage", "ROUTES"]
