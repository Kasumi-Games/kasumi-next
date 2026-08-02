from .neon import NeonKit
from .manga import MangaKit
from .fluent import FluentKit
from .kasumi import KasumiKit
from .sakura import SakuraKit
from .mewtype import MewtypeKit
from .minimal import MinimalKit
from .sailing import SailingKit
from .endfield import EndfieldKit
from .midnight import MidnightKit
from .bangdream import BanGDreamKit

#: Every kit keyed by the short name used in configuration and tooling.
KITS = {
    "bangdream": BanGDreamKit,
    "minimal": MinimalKit,
    "midnight": MidnightKit,
    "sailing": SailingKit,
    "sakura": SakuraKit,
    "neon": NeonKit,
    "manga": MangaKit,
    "fluent": FluentKit,
    "kasumi": KasumiKit,
    "mewtype": MewtypeKit,
    "endfield": EndfieldKit,
}

#: Player-facing name for each kit. A theme item's ``name`` in ``items.json``
#: should match its kit's entry here so the name a player reads off an image is
#: the name they can type back.
KIT_DISPLAY_NAMES = {
    "bangdream": "BanG Dream!",
    "minimal": "极简",
    "midnight": "午夜",
    "sailing": "扬帆",
    "sakura": "樱色",
    "neon": "霓虹街机",
    "manga": "漫画分镜",
    "fluent": "Fluent",
    "kasumi": "星之鼓动",
    "mewtype": "梦限大 Mewtype",
    "endfield": "终末地工业",
}

__all__ = [
    "KITS",
    "KIT_DISPLAY_NAMES",
    "BanGDreamKit",
    "FluentKit",
    "KasumiKit",
    "MangaKit",
    "MidnightKit",
    "MinimalKit",
    "NeonKit",
    "SailingKit",
    "SakuraKit",
    "MewtypeKit",
    "EndfieldKit",
]
