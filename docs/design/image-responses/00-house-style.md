# HOUSE RENDER STYLE — Kasumi Next
Extracted verbatim from `plugins/blackjack/render.py`, `plugins/mines/render/field.py`, `plugins/one_stroke/render/{graph,leaderboard}.py`, `plugins/render/{layout,sizing,spacing,kit,core,primitives}.py`, `plugins/render/kits/atoms.py`, and all eight `plugins/render/kits/*/kit.py`. Every number below is quoted from code or measured by running it. Nothing here is invented.

---

## 0. The three-line contract every render module obeys

```python
def render(<domain_obj>, kit: BaseKit | None = None) -> Image.Image:
    kit = kit or BanGDreamKit()
    ...
    return page.render()
```

Confirmed at `plugins/mines/render/field.py:110-111`, `plugins/one_stroke/render/graph.py:404-410`, `plugins/one_stroke/render/leaderboard.py:71-77`. Domain object is positional-first; `kit` is last with a `None` default; the fallback is `BanGDreamKit()` **inside** the function, never a default argument (a default arg would construct the kit at import time).

A renderer returns `Image.Image`, never a `MessageSegment`. `plugins/bang_avatar/render.py:41-80` returns `MessageSegment` — that is legacy and is the module the new `utils.theming.image_segment` exists to kill. Do not copy it.

---

## 1. Module & naming conventions

**Layout on disk.** Two shapes exist, both valid:

| Shape | When | Real example |
|---|---|---|
| `plugins/<p>/render.py` | one surface, or a stateful class renderer | `plugins/blackjack/render.py` |
| `plugins/<p>/render/` package | 2+ surfaces | `plugins/mines/render/`, `plugins/one_stroke/render/` |

Package `__init__.py` is a pure re-export, nothing else:

```python
# plugins/one_stroke/render/__init__.py  — the entire file
from .graph import render
from .leaderboard import render_leaderboard

__all__ = ["render", "render_leaderboard"]
```

**File naming inside the package is by *subject*, not by type**: `field.py`, `graph.py`, `leaderboard.py`. Not `card.py` / `panel.py` / `components.py` — those names belong to `plugins/render/kits/*/`.

**Function naming.** The primary surface of a module is `render`. Every additional surface is `render_<subject>` (`render_leaderboard`). Private helpers are `_`-prefixed and take `kit` first: `_background(kit)`, `_title_bar(kit, title, subtitle, *, width, height)`, `_board_panel(kit, child)`, `_ranking_panel(kit, title, rows)`, `_ranking_rows(kit, rows)`, `_hand_label`, `_cards_panel`, `_hand_section`.

**Class renderers** appear only when there is loaded resource state. `BlackjackRenderer.__init__(..., kit: Optional[BaseKit] = None)` → `self.kit: BaseKit = kit or BanGDreamKit()` (`render.py:66`, `render.py:92`). Its layout constants live in a nested class of UPPER_SNAKE ints:

```python
class RenderLayout:          # plugins/blackjack/render.py:454-478
    PAGE_PADDING = 32
    SECTION_GAP = 24
    CARD_GAP = 32
    PANEL_PADDING = 32
    PANEL_RADIUS = 32
    CARD_SOURCE_WIDTH = 640
    CARD_SOURCE_HEIGHT = 896
    CARD_WIDTH = 160 * 2
    CARD_HEIGHT = 224 * 2
    NAME_TAG_WIDTH = 450
    NAME_TAG_HEIGHT = 48
    NAME_TAG_FONT_SIZE = 36
    CARD_TEXT_FONT_SIZE = 64
    CARD_TEXT_PADDING_HORIZONTAL = 20
    CARD_TEXT_PADDING_VERTICAL = 30
    CARD_TEXT_STROKE_WIDTH = 2
    DEALER_TAG_COLOR = (0xFF, 0x55, 0x22, 255)
    PLAYER_TAG_COLOR = (0x34, 0x74, 0xD6, 255)
    WHITE_TEXT_COLOR = (255, 255, 255, 255)
    BLACK_TEXT_COLOR = (0, 0, 0, 255)
```
Function-style modules put the same numbers as literals at the call site instead. Either is house style; do not mix within one file.

**Imports.** `pyproject.toml:57-62` enforces `ruff` isort with `force-single-line = true` and `length-sort = true`. So: one symbol per line, sorted by line length ascending then alphabetically, `from plugins.render import X`. BanG Dream!-only symbols come from a separate block: `from plugins.render.kits.bangdream import BG_DIR` / `BanGDreamKit` / `CHINESE_FONT`. Domain imports (`from ..models import Field`) come last.

---

## 2. How images are composed into Pages

**Root is `AutoPage`, always.** `Page` (fixed `size=(w,h)`) is not used by any of the four renderers. `AutoPage` measures the child and sizes itself, so cards grow with content instead of clipping.

**The child of the root is always a single `VStack`** whose first element is the title bar and whose remaining elements are body panels:

```python
page = AutoPage(
    min_width=896,
    background=_background(kit),
    padding=56,
    child=VStack(
        [
            _title_bar(kit, "探险", "Arisa的仓库", width=500, height=57),
            _board_panel(kit, Grid(...)),
        ],
        gap=32,
    ),
)
return page.render()
```
(`plugins/mines/render/field.py:133-155`, structurally identical at `graph.py:415-427` and `leaderboard.py:78-98`.)

**`page.render()` takes no argument.** `RenderContext()` is the default (`layout.py:58`, `layout.py:135`). Blackjack passes `RenderContext()` explicitly (`render.py:452`, `render.py:633`) — that is equivalent, not a different mode. In async handlers use `await page.render_async()` (`layout.py:82-100`, `layout.py:181-199`); it just offloads `render` to a thread-pool executor.

**Logical pixels == output pixels.** `RenderContext.pixel_ratio` defaults to `2` (`core.py:171`). `AutoPage.render` builds the canvas at `2x`, then `canvas.resize((page_size.width, page_size.height), LANCZOS)` (`layout.py:175-179`). Measured: a page declared `min_width=896, padding=56` around a `Fixed(786)` board emits exactly **898×987 px**. So `font_size=22` is 22 real pixels in the PNG the client receives. The ~22px readability floor applies directly to the `font_size` values you write.

**Output mode is RGBA.** `generate_table` ends `return result.convert("RGB")` (`blackjack/render.py:634`) — that is the exception because that image feeds a chart pipeline. New cards return RGBA and let the caller PNG-encode.

**Rasters go through `kit.image()`, never `canvas.paste`.** The house sizing rule is visible in blackjack: source card art is `640×896` (`CARD_SOURCE_WIDTH/HEIGHT`), displayed at `CARD_WIDTH = 160 * 2 = 320`, `CARD_HEIGHT = 224 * 2 = 448` — an exact 2:1 reduction, which at `pixel_ratio=2` means the render canvas asks for `640×896` again and the source is resampled 1:1. **Pick `Fixed` display sizes that are the source dimension divided by an integer.**
Mines: `kit.image(stamp_path, width=Fixed(110), height=Fixed(110))` inside a `Fixed(120)` cell → 5px inset per side (`field.py:44`).
`KitImage.fit` defaults to `"contain"` (`atoms.py:165`); use `"cover"` for avatars/jackets that must fill; `radius=` rounds via `rounded_clip`.
Path sources are cached through `ctx.image_cache`; a live `Image.Image` source is `.convert("RGBA").copy()` on *every* render and is not cached (`atoms.py:416-421`). **Prefer passing `Path`.**

**`_draw_hand_cards` (`blackjack/render.py:581-597`) is a compatibility shim** — its docstring says "Compatibility helper for older tests and ad hoc scripts." Do not imitate direct `background.paste()`.

---

## 3. Canonical page geometry (real numbers)

| Surface | Root args | Actual output width |
|---|---|---|
| Square game board (mines, one_stroke graph) | `min_width=896, padding=56` | **898** (786 board + 2×56) |
| Blackjack table | `min_width=832, padding=32` | 832 |
| Blackjack single hand | `padding=32`, no min | fits content |
| Leaderboard (the one wide surface) | `max_width=1500, padding=Insets.only(left=70, top=36, right=70, bottom=56)` | ≤1500 |

Note the trap: **`min_width=896` never actually binds** in mines/graph — the `Fixed(786)` board plus `2×56` padding already measures 898. Treat `min_width` as a floor for sparse content, not as the page width.

**House portrait width for new cards: 896 declared / ~898 actual.** It is the only width two independent renderers agreed on. Do not exceed 1500 (leaderboard's cap) and only go wide for genuinely 3-column content.

The board block is a hard convention:
```python
Frame(child, width=Fixed(786), height=Fixed(786), padding=50, align_x="stretch", align_y="stretch", aspect_ratio=1)
```
inside `kit.panel(..., width=Fixed(786), height=Fixed(786), radius=32)` (`field.py:93-107`). `786 = 896 - 2*56 + 2`. The BanG Dream! branch in `graph.py:381-388` uses `kit.panel(child, radius=64, padding=50, width=Fixed(786), height=Fixed(786))` — same box, kit-specific radius.

---

## 4. Padding / gap scale actually used

Every spacing literal in the four files: `8, 12, 18, 20, 21, 22, 24, 28, 30, 32, 36, 46, 50, 56, 70`.

By role:

| Role | Values in use | Source |
|---|---|---|
| Page padding | `32` blackjack · `56` mines/graph · `Insets.only(70,36,70,56)` leaderboard | `render.py:455`, `field.py:136`, `leaderboard.py:81` |
| Root VStack gap | `24` blackjack `SECTION_GAP`, graph · `32` mines · `46` leaderboard | `render.py:448`, `graph.py:425`, `field.py:152`, `leaderboard.py:95` |
| Panel inner padding | `32` blackjack `PANEL_PADDING` · `50` board frame · `Insets.only(30,28,30,22)` BD ranking body · `Insets.only(20,18,20,24)` fallback ranking | `render.py:560`, `field.py:99`, `leaderboard.py:107`, `leaderboard.py:146` |
| Gap between siblings inside a panel | `12` row HStack · `18` rows VStack · `21` mines Grid · `30` leaderboard columns · `32` blackjack `CARD_GAP` | `leaderboard.py:61,68`, `field.py:149`, `leaderboard.py:91`, `render.py:559` |
| Micro gap | `8` (fallback ranking panel title→body) | `leaderboard.py:141` |

**Ladder to use for new work: `8 / 12 / 18 / 24 / 32 / 50 / 56`.** Everything else in the list is a one-off fitting an existing fixed box.

`Insets` shorthand: bare `int` → `Insets.all(n)` via `as_insets` (`spacing.py:82-96`). Use the int form unless sides genuinely differ; the leaderboard's asymmetry (`top=36, bottom=56`) is deliberate optical centering under a title pill.

---

## 5. Font size ladder actually used

| px | Role | Source |
|---|---|---|
| **80** | Glanceable cell index on a game board | `field.py:26` |
| 64 | Blackjack card value, drawn in **source art space** (640×896), so ≈32 after the 2:1 display reduction | `render.py:470` |
| 40 | `BaseKit.text` default (`kit.py:59`); fallback ranking-panel title | `leaderboard.py:129` |
| 37 | BD title-pill **subtitle** band, computed `(h*85//62)*36//75` — at `h=57` → 37 | `bangdream/components.py:412` |
| 36 | Blackjack name tag | `render.py:468` |
| 34 | BD `titled_panel` title | `leaderboard.py:117` |
| 30 | BD `pill` default (`bangdream/kit.py:267`); BD title-pill **title** band `h*33//61` — at `h=57` → 30 | `bangdream/components.py:409` |
| 24 | `_title_bar` non-BD fallback text | `field.py:80`, `graph.py:367`, `leaderboard.py:171` |
| 23 | Leaderboard row **name** | `leaderboard.py:38` |
| 22 | Leaderboard row **value** | `leaderboard.py:50` |

**Ladder: 22 (absolute body floor) / 24 / 30 / 34–36 / 40 / 64–80 (display numerals only).**
Note the BD title pill inverts the obvious hierarchy: subtitle (37) is *larger* than title (30). The colored title band carries the emphasis, not the size.

Line height is `round(font_size * 1.35)` unless `line_height=` is passed (`atoms.py:71`, `atoms.py:85`, mirrored in `bangdream/components.py:65`).

---

## 6. Text component defaults you must override

`BaseKit.text` signature (`kit.py:54-66`):
```python
def text(self, text: str, *, font_size: int = 40, color: ColorLike | None = None,
         align: TextAlign = "left", wrap: bool = True, max_lines: int | None = None,
         overflow: Overflow = "ellipsis", line_height: int | None = None) -> Component
```

The house single-line-label call (`leaderboard.py:35-43`):
```python
kit.text(name_text, font_size=23, color=color, wrap=False, max_lines=1, overflow="ellipsis")
```
- `wrap=True` is the **default** and will silently break a long nickname onto a second line and grow the row. Always pass `wrap=False, max_lines=1` for labels in a fixed-height row.
- The numeric-column idiom is `align="right"` inside `Frame(..., width=Fixed(72), align_x="stretch", align_y="center")` (`leaderboard.py:47-59`); the label side is `Frame(..., width=Fill(), align_x="start", align_y="center")`.
- `overflow="shrink"` runs a `while font_size > 8:` re-layout loop (`atoms.py:112-131`). It is slow and its output is unreadable after client downscale. None of the four renderers use it. Use `"ellipsis"`.
- Vertical centering is *always* `Frame(child, align_x=..., align_y="center")` — never manual padding.
- **`BanGDreamKit.text` alone accepts `font: BanGDreamFont = "chinese"`** (`bangdream/kit.py:130`). No other kit has that parameter. Shared code must never pass `font=`.

---

## 7. Panel radius conventions

`kit.panel(..., radius: int | None = None)`. When `radius is None`, each kit substitutes its own identity value:

| Kit | Default radius | `panel_fill` |
|---|---|---|
| bangdream | **48** | `(255,255,255,208)` |
| sakura | 44 | `(255,255,255,234)` |
| midnight | 36 | `(30,36,56,224)` |
| sailing | 30 | `(252,252,248,232)` |
| minimal | 20 | `(245,245,245,255)` |
| manga | 14 | `(255,255,255,242)` |
| neon | 10 | `(14,12,28,228)` |
| fluent | 8 | `(255,255,255,178)` |

(`bangdream/kit.py:177`, `sakura/kit.py:146`, `midnight/kit.py:143`, `sailing/kit.py:143`, `minimal/kit.py:84`, `manga/kit.py:143`, `neon/kit.py:146`, `fluent/kit.py:146`. `KitPanel`'s own dataclass default is `32`, `atoms.py:215`.)

**The rule this encodes: omit `radius=` on generic surfaces so the kit's silhouette shows through — that corner is a large part of "which theme am I looking at."** Only pass an explicit radius when geometry demands it:

- pill / capsule → `radius=height // 2` (`render.py:544`, `field.py:89`, `graph.py:376`, `leaderboard.py:179`)
- small cell (120px) → `radius=16` (`field.py:35,51`)
- large board panel → `radius=32` (`field.py:106`), BD variant `radius=64` (`graph.py:384`)
- leaderboard column → `radius=48` (`leaderboard.py:147`), BD `title_radius=32, main_radius=48` (`leaderboard.py:117-118`)

Over-large radii are safe: `draw_rounded_rectangle` clamps to `min(radius, shape_w // 2, shape_h // 2)` (`primitives.py:110`).

---

## 8. Title bars — the most-copied block in the codebase

`_title_bar` is **byte-identical in three files** (`field.py:61-90`, `graph.py:348-377`, `leaderboard.py:151-180`):

```python
def _title_bar(kit: BaseKit, title: str, subtitle: str, *, width: int, height: int):
    if isinstance(kit, BanGDreamKit):
        return kit.title_pill(title, subtitle, pill_width=width, pill_height=height)
    return kit.panel(
        Frame(
            kit.text(f"{title} - {subtitle}", font_size=24, align="center", max_lines=1),
            align_x="center", align_y="center",
        ),
        width=Fixed(width), height=Fixed(height), radius=height // 2,
    )
```

Real call sites — **`height` is always 57**:
- `_title_bar(kit, "探险", "Arisa的仓库", width=500, height=57)`
- `_title_bar(kit, "一笔画", f"{difficulty} | {drawn}/{total} | 奖励 {live}/{base}", width=560, height=57)`
- `_title_bar(kit, "一笔画", "竞速排行榜", width=420, height=57)`

**Structure: short fixed noun (the plugin's name) + a live status string.** The subtitle is where mutable state goes; the title never changes. Copy that split.

### Two facts that will bite you

**(a) `title_pill`'s measured size is not `(width, height)`.** From `BanGDreamTitlePill.measure` (`bangdream/components.py:379-390`):
```
subtitle_h = pill_height * 85 // 62      # 57 -> 78
subtitle_w = pill_width  * 625 // 570    # 500 -> 548
overlap    = pill_height *  9 // 62      # 57 -> 8
size       = (subtitle_w, pill_height + subtitle_h - overlap)
```
→ `(500,57)` measures **548×127**; `(560,57)` → **614×127**; `(420,57)` → **460×127**. Never do layout math against the `width`/`height` you passed in.

**(b) The fallback pill is silently stretched.** The root `VStack` defaults to `align="stretch"` (`layout.py:377`), and `_stack_layout` gives a stretched child `child_w = rect.width` regardless of its own `Fixed` width (`layout.py:869`); `KitPanel.render` paints the rect it is given without re-clamping (`atoms.py:235-247`). Verified by rendering: on the mines page, the *same* `Fixed(500)` title bar occupies x∈[55,842] (787px) with `align="stretch"` and x∈[55,556] (501px) with `align="start"`. So today the header is a compact pill on BanG Dream! and a full-width bar on the other seven kits.

**Fix in `utils/cards.py`, do not re-copy the block.** `response_card(kit, *, title, subtitle=..., body, footer=...)` should build a header that is genuinely kit-neutral (two tiers, `title` at 30–34 and `subtitle` at 22–24, or the reverse to match the BD pill's weighting) and wrap it in `Frame(header, align_x="start")` so both branches agree on width. Keep `kit.title_pill` as the BanG Dream! upgrade branch only.

---

## 9. Guarding kit-specific helpers

The pattern, without exception:

```python
def _background(kit: BaseKit):
    if isinstance(kit, BanGDreamKit):
        return kit.background(source=BG_DIR / "bg00039.png")
    return kit.background()
```
(`field.py:55-58`; also `graph.py:338-345`, `graph.py:380-401`, `leaderboard.py:101-148`, `render.py:520-545`.)

Rules the code follows:
1. The guard is **always** `isinstance(kit, BanGDreamKit)` — never a `hasattr` probe, never a kit-name string.
2. The guard lives inside a **small private helper that returns a `Component`** (or `Background`). Never inline inside `render()`.
3. Both branches produce approximately the same box, so the surrounding layout is identical.
4. The fallback branch uses only the five `BaseKit` atoms.

**BanG Dream! is the only kit with extra helpers.** Verified across all eight `kit.py` files — the other seven expose exactly `background / text / image / panel / separator` and nothing else. The BD-only surface is:

`background(source=...)`, `background_simple(fill=...)`, `board_frame(child, *, width, height, padding, max_size, fill, radius)`, `title_pill(title, subtitle, *, pill_width=500, pill_height=57, ...)`, `titled_panel(title, child, *, title_width, title_height, main_width, main_height, title_font_size=40, stroke_width=6, title_radius=None, main_radius=None, title_fill=None, main_fill=None)`, `pill(text, *, width, height, font_size=30, fill=None, text_color=None, align="center")`.

**`kit.background()` must be called with zero arguments in shared code.** Signatures diverge and `fill` is not portable:
- `BaseKit.background(self, *, fill=None)` (`kit.py:42`)
- `BanGDreamKit.background(self, *, source=None, **props)` — **when `source is None` it returns `self.background_simple()` and drops `fill` on the floor** (`bangdream/kit.py:51-76`)
- `MidnightKit.background(*, fill, bottom, star_density=0.00012, random_seed=0)`, `SailingKit.background(*, fill, bottom, wave_height=46, wave_length=260)`, `SakuraKit.background(*, fill, bottom, petal_density=0.00005, petal_size=18, random_seed=0)`, plus manga/neon/fluent variants.

**Palette access.** Only these three are `BaseKit`-declared and safe on all eight kits (`kit.py:37-39`): `text_color`, `muted_text_color`, `panel_fill`. `primary` and `accent` exist on seven kits but **`MinimalKit` has neither** — use `getattr(kit, "primary", kit.text_color)` if you want an accent, and never let that accent be the only signal.

The house use of the palette pair is the leaderboard's filled-vs-empty row (`leaderboard.py:22-29`): populated rows get `kit.text_color`, placeholder rows get `kit.muted_text_color` **and** their value column becomes an empty string. Two signals, one of which survives monochrome.

---

## 10. Hard-coded colors: exactly where they are allowed

The renderers deliberately bypass the kit for **game-state tokens**:

- mines: unrevealed `(223,223,223,255)`, Kasumi reveal `(255,124,85)`, Arisa reveal `(184,130,225)` (`field.py:34,123,129`)
- one_stroke: `{"wall": (90,85,110,255), "traversable": (215,215,225,255), "drawn": (234,78,116,255), "start": (76,175,80,255), "current": (66,133,244,255)}` (`graph.py:208-214`)
- blackjack: `DEALER_TAG_COLOR = (0xFF,0x55,0x22,255)`, `PLAYER_TAG_COLOR = (0x34,0x74,0xD6,255)`

**The extracted rule: chrome is themed, state is theme-invariant.** Page background, panels, header, body text come from the kit. A token that must mean the same thing across all eight themes keeps its own color.

**And every one of those tokens carries a redundant non-color cue** — this is the codebase's existing manga/monochrome discipline, not a new requirement:
- mines unrevealed cell → a **numeral** at 80px; revealed cell → a **stamp image**
- one_stroke start node → literal label `"S"`; nodes are **circles**, walls are **rounded squares**, edges are **pipes**; the current node adds a drawn **ring** (`graph.py:256-275`)
- blackjack tags → the **name string** "Kasumi" / "You" inside the pill

Follow it: any new state color must be paired with a glyph, a shape, a position, or a word.

Text over a hard-coded fill is `(255,255,255,255)`. The single stroked text in the codebase is the blackjack card value: `stroke_width=2, stroke_fill=(0,0,0,255)` (`render.py:514-515`) — used because it sits on unpredictable card art.

---

## 11. Layout idioms worth memorizing

- **`VStack(children, gap, align)`** — `align` defaults to `"stretch"` (`layout.py:377`). Root stacks use `"start"` (blackjack hand, `render.py:449`), `"stretch"` (blackjack table `render.py:630`, leaderboard `leaderboard.py:96`), or the default (mines/graph). See §8(b): `"stretch"` overrides a child's declared `Fixed` width at render time.
- **`Fill()` needs a bounded axis** or raises `LayoutError` (`layout.py:699-702`, `sizing.py`). `Fill()` on the main axis of a root `AutoPage` `VStack` will throw. Legal uses in-tree: cross-axis inside a fixed-height row (`leaderboard.py:44` `width=Fill()`, `:63` `height=Fill()`), and `main_width=Fill()` inside a `max_width`-bounded HStack (`leaderboard.py:112`).
- **`Grid`** — the house grid pins both tracks and both counts, never `Fit`:
  ```python
  Grid(children=cells, columns=field.width, rows=field.height,
       column_track=Fixed(120), row_track=Fixed(120), gap=21)
  ```
  `Fit` tracks re-`measure` every child in the track (`layout.py:995-1025`). Default field is 5×5 → `5*120 + 4*21 = 684`, inset by the board `padding=50` → 784 inside the 786 panel.
- **`Frame(..., aspect_ratio=1)`** is how a square body is enforced (`field.py:103`, `graph.py:398`); `_apply_aspect` shrinks the longer axis (`layout.py:728-743`).
- **`Overlay(children, align_x, align_y)`** renders all children into the same rect, later on top — the only badge/stamp mechanism available.

---

## 12. Raw-PIL escape hatch (when layout can't express it)

Implement the `Component` protocol as a frozen dataclass. Canonical example `OneStrokeBoard` (`graph.py:168-192`):

```python
@dataclass(frozen=True)
class OneStrokeBoard:
    session: GameSession

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        return constraints.clamp(Size(686, 686))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        ...
```

Rules it demonstrates:
1. **Every logical literal goes through `ctx.scale_px()`** — `ctx.scale_px(8)`, `ctx.scale_px(4)`, `ctx.scale_px(7)` (`graph.py:259-274`). Forgetting one makes it half-size at `pixel_ratio=2`.
2. Expensive per-cell art is `@lru_cache(maxsize=64)` keyed on `(size, fill_tuple, corner_radius, label)` — `_generate_cell`, `_generate_node_circle`, `_generate_pipe` (`graph.py:59,86,108`). Cache keys must be hashable, hence RGBA tuples not `ColorLike`.
3. **Z-order is explicit via separate full-canvas RGBA layers**, composited in a fixed order at the end (`graph.py:219-222`, `graph.py:334-335`):
   ```python
   for layer in (wall_layer, traversable_layer, drawn_layer, special_layer):
       canvas.paste(Image.alpha_composite(canvas, layer), (0, 0))
   ```
4. Derived radii scale with the cell: `corner_radius = max(6, cell_size // 7)` (`graph.py:206`), `font = _font(max(12, size // 3))` (`graph.py:73`).
5. Read `ctx.scale_px` / `ctx.render_ratio`, never `ctx.pixel_ratio` (`core.py:180-199`) — `pixel_ratio` is the *request*, `render_ratio` is what's active for the current canvas.
6. Fonts come from `plugins.render.primitives.load_font(size, path)`, which falls back to PIL's default on `OSError` (`primitives.py:31-49`). Shared font paths are `plugins/render/kits/fonts.py`: `CHINESE_FONT` (`old.ttf`) and `DISPLAY_FONT` (`Orbitron Black.ttf`). `graph.py:31-32` wraps it as `def _font(size): return load_font(size, CHINESE_FONT)`.

Also available from `atoms.py` for custom components: `draw_panel_surface`, `draw_soft_shadow`, `vertical_gradient`, `mix_color`, `resize_contain`, `resize_cover`, `with_opacity`, `rounded_clip`, `draw_aligned_text`, `fit_intrinsic_image_size`.

---

## 13. Measured cost budget

Rendered on this machine, `.venv` Python 3.12, an 898×987 page with two flat panels at `pixel_ratio=2`:

| kit | time |
|---|---|
| minimal | 0.03 s |
| manga | 0.04 s |
| sailing | 0.05 s |
| midnight | 0.09 s |
| bangdream | 0.11 s |
| fluent | 0.11 s |
| sakura | 0.12 s |
| neon | 0.13 s |

BanG Dream! background, 898×898 page: `kit.background()` (tiled pattern) **0.08 s** vs `kit.background(source=BG_DIR/"bg00039.png")` **0.25 s** — the image treatment (blur radius 25, 200px triangle facets, star scatter, repeated watermark; `bangdream/kit.py:62-76`) costs ~3×. mines and one_stroke pay that on *every move*.

Budget: keep a per-message card under **~0.15 s**. Use `await page.render_async()` in any handler that fires repeatedly. `graph.py:338-345` also calls `random.choice(list(Path(BG_DIR).glob(...)))` per render — an un-cached directory scan; do not copy that, hoist the glob to module scope.

---

## 14. Known duplication that `utils/` is replacing (do not re-create)

1. **`_image_segment` — four identical copies**: `plugins/mines/__init__.py:42-45`, `plugins/one_stroke/__init__.py:43-45`, `plugins/bang_avatar/render.py:78-80`, `plugins/cck/draw.py:19-21`. All are `BytesIO` → `img.save(buffer, format="PNG")` → `MessageSegment.image(raw=buffer, mime="image/png")`. → `utils.theming.image_segment`.
2. **`_title_bar` — three byte-identical copies** (§8). → `utils.cards.response_card` header.
3. **`_board_panel` — two near-identical copies** (`field.py:93-107` vs `graph.py:380-401`, differing only in the BD `radius=64` branch).
4. Cosmetic: `from plugins.render import Insets` is imported and unused at `plugins/one_stroke/render/graph.py:15`.

Call-site convention to preserve when wiring new cards (`one_stroke/__init__.py:94-98`):
```python
passive_generator = PG(event)
image = render_leaderboard(...)
await cmd.finish(
    _image_segment(image) + passive_generator.element,
    referrer=passive_generator.event.referrer,
)
```
The `PassiveGenerator` element is appended **after** the image segment, and `referrer=` is always passed. `utils` modules are imported absolutely (`from utils.passive_generator import PassiveGenerator as PG`), so `utils.theming` / `utils.cards` follow the same form.

---

## 15. Checklist for a new plugin render module

1. `plugins/<p>/render.py`, or `plugins/<p>/render/<subject>.py` + a re-export-only `__init__.py`.
2. `def render(obj, kit: BaseKit | None = None) -> Image.Image:` → `kit = kit or BanGDreamKit()`.
3. Root `AutoPage(min_width=896, padding=56, background=_background(kit), child=VStack([...], gap=32))`; leave `align` at `"stretch"` only if every child should be full-bleed, otherwise pass `align="start"`.
4. First VStack child is the header (via `utils.cards`, not a fourth `_title_bar` copy). Fixed plugin noun as title, live state as subtitle.
5. Body panels from `kit.panel(...)` with `radius` **omitted** unless geometry forces it.
6. Body text ≥ 22px; labels get `wrap=False, max_lines=1, overflow="ellipsis"`; colors from `kit.text_color` / `kit.muted_text_color` only.
7. Rasters via `kit.image(path, width=Fixed(w), height=Fixed(h))` where `w`/`h` divide the source integrally.
8. Any BanG Dream!-only flourish goes in a `_`-prefixed helper guarded by `isinstance(kit, BanGDreamKit)`, with a five-atom fallback of the same box size.
9. Any game-state color is hard-coded **and** paired with a glyph/shape/word so it survives `MangaKit`.
10. Render it in all eight kits from `plugins.render.kits.KITS` before shipping; check the header width, the panel corner, and whether the card is still legible with color removed.