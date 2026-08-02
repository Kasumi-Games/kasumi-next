"""Typography used by the Yumemita website-inspired kit.

The source site uses M PLUS Rounded 1c at weights 500 and 800 for page copy
and cyan article headings, with Montserrat reserved for compact uppercase
navigation. Its large page wordmarks are raster assets rather than Montserrat
text.

Resource Han Rounded CN supplies one coherent Simplified Chinese family for
all ordinary copy and headings, including their adjacent Latin letters and
numbers. Montserrat is opt-in for compact display stats only; M PLUS Rounded
1c Medium supplies the tuned English page wordmark without an over-heavy face.
All bundled files are distributed under the SIL Open Font License 1.1; see
``resources/fonts/OFL-1.1.txt``.
"""

from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent / "resources" / "fonts"

CHINESE_BODY_FONT = FONT_DIR / "ResourceHanRoundedCN-Medium.ttf"
CHINESE_HEADING_FONT = FONT_DIR / "ResourceHanRoundedCN-Bold.ttf"
LATIN_BODY_FONT = FONT_DIR / "MPLUSRounded1c-Medium.ttf"
LATIN_TITLE_FONT = FONT_DIR / "MPLUSRounded1c-Medium.ttf"
LATIN_HEADING_FONT = FONT_DIR / "MPLUSRounded1c-ExtraBold.ttf"
LATIN_DISPLAY_FONT = FONT_DIR / "Montserrat-ExtraBold.ttf"

__all__ = [
    "CHINESE_BODY_FONT",
    "CHINESE_HEADING_FONT",
    "LATIN_BODY_FONT",
    "LATIN_DISPLAY_FONT",
    "LATIN_HEADING_FONT",
    "LATIN_TITLE_FONT",
]
