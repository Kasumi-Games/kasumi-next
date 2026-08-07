from math import inf
from functools import lru_cache
from dataclasses import dataclass
from unicodedata import east_asian_width

from PIL import ImageDraw
from uniseg.linebreak import line_break_boundaries as _line_break_boundaries
from uniseg.graphemecluster import (
    grapheme_cluster_boundaries as _grapheme_cluster_boundaries,
)

FORBIDDEN_LINE_START = set(",.;:!?)]}，。！？、；：）】》」』〉〕］｝〗〙〛…")
FORBIDDEN_LINE_END = set("([{（【《「『〈〔［｛〖〘〚")
HANGING_LINE_END = set(",.;:!?，。！？、；：…")
@dataclass(frozen=True)
class _BreakCandidate:
    line: str
    width: int
    adjusted_width: int
    penalty: float


def wrap_text(text: str, font, max_width: int | None) -> list[str]:
    if max_width is None:
        return text.splitlines() or [text]
    if max_width <= 0:
        return text.splitlines() or [text]
    try:
        hash(font)
    except TypeError:
        # Third-party font facades are not required to be hashable. They still
        # receive correct wrapping, just without cross-call caching.
        return _wrap_text_uncached(text, font, max_width)
    return list(_cached_wrap_text(text, font, max_width))


@lru_cache(maxsize=512)
def _cached_wrap_text(text: str, font, max_width: int) -> tuple[str, ...]:
    """Cache wrapping against the font object, retaining its identity safely."""

    return tuple(_wrap_text_uncached(text, font, max_width))


def _wrap_text_uncached(text: str, font, max_width: int) -> list[str]:
    return [
        line
        for raw_line in text.splitlines() or [text]
        for line in _wrap_raw_line(raw_line, font, max_width)
    ]


def max_lines_for_height(max_height: int, line_height: int) -> int:
    return max(1, max_height // max(1, line_height))


def merge_line_limits(first: int | None, second: int | None) -> int | None:
    if first is None:
        return second
    if second is None:
        return first
    return min(first, second)


def ellipsis(text: str, font, max_width: int | None, *, force: bool = False) -> str:
    if max_width is None:
        return text + "..." if force else text
    if not force and text_width(text, font) <= max_width:
        return text
    suffix = "..."
    if text_width(suffix, font) > max_width:
        return suffix
    low = 0
    high = len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if text_width(text[:mid] + suffix, font) <= max_width:
            low = mid
        else:
            high = mid - 1
    return text[:low] + suffix


def text_width(text: str, font) -> int:
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]


def display_text_width(text: str, font, max_width: int | None = None) -> int:
    width = text_width(text, font)
    if max_width is None or width <= max_width:
        return width
    if _adjusted_line_width(text, font) <= max_width:
        return max_width
    return width


def draw_text_line(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font,
    fill,
    *,
    max_width: int | None = None,
) -> None:
    width = text_width(text, font)
    if max_width is None or width <= max_width:
        draw.text(xy, text, font=font, fill=fill)
        return
    suffix_start = _hanging_suffix_start(text)
    if suffix_start == len(text):
        draw.text(xy, text, font=font, fill=fill)
        return
    prefix = text[:suffix_start]
    suffix = text[suffix_start:]
    overrun = width - max_width
    suffix_width = text_width(suffix, font)
    if overrun > suffix_width:
        draw.text(xy, text, font=font, fill=fill)
        return
    x, y = xy
    draw.text((x, y), prefix, font=font, fill=fill)
    draw.text(
        (x + text_width(prefix, font) - overrun, y),
        suffix,
        font=font,
        fill=fill,
    )


def _wrap_raw_line(text: str, font, max_width: int) -> list[str]:
    if not text:
        return [""]
    legal_breaks = set(_line_breaks(text))
    legal_breaks.add(len(text))
    grapheme_breaks = _grapheme_boundaries(text)
    next_grapheme = {
        start: end for start, end in zip(grapheme_breaks, grapheme_breaks[1:])
    }
    break_points = sorted({0, len(text), *legal_breaks, *grapheme_breaks})
    width_cache: dict[str, int] = {}
    candidate_cache: dict[tuple[int, int], _BreakCandidate | None] = {}

    def candidate(start: int, end: int) -> _BreakCandidate | None:
        cache_key = (start, end)
        if cache_key in candidate_cache:
            return candidate_cache[cache_key]
        line = text[start:end].strip(" ")
        if not line:
            candidate_cache[cache_key] = None
            return None
        width = _cached_text_width(line, font, width_cache)
        adjusted_width = _adjusted_line_width(line, font, width_cache)
        is_last = end == len(text)
        is_legal = end in legal_breaks
        is_single_oversized = end == next_grapheme.get(start) and width > max_width
        if adjusted_width > max_width and not is_single_oversized:
            candidate_cache[cache_key] = None
            return None
        penalty = 0.0
        if not is_legal:
            penalty += 5000.0
        if line[0] in FORBIDDEN_LINE_START:
            penalty += 20000.0
        if not is_last and line[-1] in FORBIDDEN_LINE_END:
            penalty += 20000.0
        if not is_last and _is_lonely_cjk_line(line):
            penalty += 2500.0
        if adjusted_width < max_width and not is_last:
            remaining = (max_width - adjusted_width) / max_width
            penalty += remaining * remaining * 1000.0
        if width > max_width:
            penalty += (width - max_width) * 25.0
        result = _BreakCandidate(line, width, adjusted_width, penalty)
        candidate_cache[cache_key] = result
        return result

    best_cost: dict[int, float] = {len(text): 0.0}
    best_next: dict[int, tuple[int, str]] = {}
    for start in reversed(break_points[:-1]):
        best = inf
        best_choice: tuple[int, str] | None = None
        for end in break_points:
            if end <= start:
                continue
            item = candidate(start, end)
            if item is None or end not in best_cost:
                continue
            cost = item.penalty + best_cost[end]
            if cost < best:
                best = cost
                best_choice = (end, item.line)
        if best_choice is not None:
            best_cost[start] = best
            best_next[start] = best_choice

    if 0 not in best_next:
        return [text]
    lines: list[str] = []
    start = 0
    while start < len(text):
        end, line = best_next[start]
        lines.append(line)
        start = end
    return lines


def _adjusted_line_width(text: str, font, cache: dict[str, int] | None = None) -> int:
    width = (
        _cached_text_width(text, font, cache)
        if cache is not None
        else text_width(text, font)
    )
    suffix_start = _hanging_suffix_start(text)
    if suffix_start == len(text):
        return width
    suffix = text[suffix_start:]
    suffix_width = (
        _cached_text_width(suffix, font, cache)
        if cache is not None
        else text_width(suffix, font)
    )
    return max(0, width - suffix_width)


def _hanging_suffix_start(text: str) -> int:
    index = len(text)
    while index > 0 and text[index - 1] in HANGING_LINE_END:
        index -= 1
    return index


def _is_lonely_cjk_line(text: str) -> bool:
    return len(text) == 1 and east_asian_width(text) in {"F", "W"}


def _line_breaks(text: str) -> list[int]:
    if _line_break_boundaries is not None:
        return list(_line_break_boundaries(text))
    boundaries: list[int] = []
    for index in range(1, len(text) + 1):
        previous = text[index - 1]
        next_char = text[index] if index < len(text) else ""
        if index == len(text) or previous == " ":
            boundaries.append(index)
        elif (
            previous not in FORBIDDEN_LINE_END and next_char not in FORBIDDEN_LINE_START
        ):
            if east_asian_width(previous) in {"F", "W"} or east_asian_width(
                next_char
            ) in {"F", "W"}:
                boundaries.append(index)
    return boundaries


def _grapheme_boundaries(text: str) -> list[int]:
    if _grapheme_cluster_boundaries is not None:
        return list(_grapheme_cluster_boundaries(text))
    return list(range(0, len(text) + 1))


def _cached_text_width(text: str, font, cache: dict[str, int]) -> int:
    width = cache.get(text)
    if width is None:
        if _has_wide_character(text) and not getattr(font, "letter_spacing", 0):
            width = sum(_cached_char_width(char, font, cache) for char in text)
        else:
            width = text_width(text, font)
        cache[text] = width
    return width


def _cached_char_width(char: str, font, cache: dict[str, int]) -> int:
    width = cache.get(char)
    if width is None:
        width = text_width(char, font)
        cache[char] = width
    return width


def _has_wide_character(text: str) -> bool:
    return any(east_asian_width(char) in {"F", "W"} for char in text)
