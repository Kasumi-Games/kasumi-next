"""Font files shared between kits.

The bundled font assets currently live inside the BanG Dream! kit's resource
directory. Kits that want the same typefaces resolve them from here instead of
copying the binaries into every kit package. ``load_font`` already falls back to
PIL's default font when a path is missing, so a kit stays renderable even if the
bundle is absent.
"""

from pathlib import Path

KITS_DIR = Path(__file__).resolve().parent
SHARED_FONTS_DIR = KITS_DIR / "bangdream" / "resources" / "Fonts"

#: CJK-capable body font.
CHINESE_FONT = SHARED_FONTS_DIR / "old.ttf"

#: Wide geometric font for numerals and short latin display strings.
DISPLAY_FONT = SHARED_FONTS_DIR / "Orbitron Black.ttf"
