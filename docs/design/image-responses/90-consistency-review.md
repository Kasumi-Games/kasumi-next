I read the actual code (`plugins/render/kit.py`, all 8 `kits/*/kit.py`, `kits/atoms.py`, `layout.py`, `core.py`, the four existing renderers, and every plugin the two clusters touch) and measured the per-kit contrast numbers. Findings below.

---

# CONSISTENCY CRITIC — cross-cluster reconciliations

Scope note: I received two clusters (`identity`, `economy`); the economy entry was truncated mid-`RewardStrip`, and no game/utility cluster arrived. Everything below is verified against source unless marked.

---

## P0 — these make the bot feel like two different bots

### 1. Two player identity cards, colliding commands. Merge into one.
- **`PlayerInfoCard`** (identity) — `plugins/inventory/render/profile.py::render_profile`, on `/资料 /个人资料 /我 /profile`
- **`PlayerCard`** (economy) — `plugins/daily/render/player.py::render_player`, on `/info /balance /余额 /信息 /个人信息 /我的信息`

They render the same subject with different anatomy and a different data cut. Identity's has season strip + collection + gacha pity, no XP, no streak. Economy's has an XP bar + streak + level-rank + today's task, no collection, no gacha. `UPDATE.md:384` specifies these as **one** command (`/个人信息 或 /info 或 /我`), and `UPDATE.md:636` already plans `plugins/profile/` as its home. Worse: identity's interaction change makes the profile card the reply to every equip action — so equipping would show card A while `/info` shows card B.

**Winner:** identity's layout (it is the richer canvas and it is the one that lands the equip flow), moved out of `plugins/inventory/` into a single module both plugins call, with economy's XP meter, `consecutive_checkins` and today's-task cell folded into the stat grid. Delete `plugins/daily/render/player.py`. `/资料 简介 <text>` stays on inventory as a text-only subcommand.

**Also drop from the merged card:** `保底计数 53/90`. It is meaningless without a banner, it is the fifth surface rendering the pity gauge, and this card is designed to be posted publicly.

### 2. Nobody agrees on what `kit.player_card` is for.
`docs/design/season-gacha-cosmetics.md:261-315` defines `PlayerInfoCard` as the **transparent kit component** ("not a panel, should not include standing art"), which is `BaseKit.player_card` at `kit.py:162-182`. Identity names its whole *page* `PlayerInfoCard` (name collision with the component) but does call `kit.player_card`. Economy's `PlayerCard` hand-builds the identical identity block — avatar 160 in a frame, name 34px, title pill, description, Lv badge — **without calling `kit.player_card` at all**.

That is the failure mode that kills the theme system: the one component the doc says each of 8 kits must own gets used by exactly one card, so nobody ever writes the other seven.

**Winner:** every identity block on every card goes through `kit.player_card`, with the `utils/cards.py` five-atom fallback selected by `type(kit).player_card is not BaseKit.player_card`. Rename the identity *page* to `ProfileCard` so `PlayerInfoCard` keeps meaning the component.

Corollary: avatar geometry must be pinned once — identity says avatar 160 inside a 200x200 frame, economy says 160 inside 192. No frame art exists yet (`resources/` is empty, no `image_path` in `items.json`), so this ratio is free to fix now and expensive to fix later.

### 3. "Fill with `primary`, put white text on it" fails in 4 of 8 kits. Measured.
Used by `RankCard` badges (hardcodes `(255,255,255,255)`), `CheckinCard` streak dots ("num white"), `SeasonLadderCard` top-3 ("numeral 30px inverted"), `SeasonPassportCard` rank badges, `TaskCard` 已完成 pill, `EnvelopeCard` 手气王 pill.

| kit | white on `primary` | `text_color` on `primary` | `text_color` on `panel_fill` |
|---|---|---|---|
| sakura | **2.16** | 4.08 | 8.80 |
| midnight | **2.59** | 2.11 | 12.53 |
| neon | 3.43 | 2.92 | 16.43 |
| bangdream | 3.60 | 2.24 | 8.06 |
| fluent | 4.53 | 3.84 | 17.40 |
| sailing | 9.00 | 1.31 | 11.45 |
| minimal | 8.06 | **1.00** | 7.40 |
| manga | 18.71 | **1.00** | 18.71 |

Two separate breakages:
- White numerals on `primary` are unreadable at 2.16 (sakura) and 2.59 (midnight) after client downscale.
- `MangaKit.primary == text_color == (18,18,20)` and `MinimalKit` has **no** `primary` (so `getattr` returns `text_color`). Ratio 1.00. Any filled-`primary` surface carrying default-colored text is **literally invisible** in manga and minimal. `SeasonStatusCard`'s current-tier row is specified exactly this way — "CURRENT tier row: filled `kit.panel` behind the row" + the words 你在这 — so the marquee "you are here" row disappears in two kits, including the one both clusters claim is their best monochrome case.

**Winner:** one rule, no exceptions. **Filled emphasis shapes fill with `kit.text_color` and draw their foreground in `kit.panel_fill`.** That is 7.40–18.71 in all eight by construction. `primary` is then reserved for *unfilled* accents (meter fills against a track, thin rules, separators) where a decorative ratio is acceptable — and those always carry a numeric label anyway. Ship this as `utils/cards.py::emphasis(kit)` returning `(fill, on_fill)`; no renderer picks these colors itself.

### 4. Six different progress bars for one concept.
| component | card(s) | size | radius |
|---|---|---|---|
| XP bar | `PlayerCard` | 720x28 | 14 |
| `SeasonProgressBar` | `PlayerInfoCard`, `SeasonStatusCard` | 722x20 | 10 |
| `PityGauge` | `SinglePullCard`, `TenPullRevealCard`, `BannerCard` | 722x20 | 10 + notch |
| claim bar | `EnvelopeCard` | segmented, h=24, gap 6 | 6 |
| claim bar | `EnvelopeListCard` | 720x16 | 8 |
| gap-to-next bar | `RankCard` | 560x14 | 7 |
| rate bars | `BannerCard` | `Fill()`, height unspecified | — |

**Winner:** one `utils/cards.py::meter(kit, *, value, total, width=Fill(), height=20, notch=None, segments=None, label=...)` at h=20 r=10, always with the numeric label rendered by the component itself. 14px and 16px are the outliers to kill — at 2x supersample downscaled by the client, a 14px track is ~12px displayed and the fill/track distinction dies first in fluent (`panel_fill` alpha 178) and sakura (`primary` on panel = 2.16).

### 5. `kit.title_pill(...)` is called unguarded in five economy cards. It only exists on BanGDreamKit.
Verified: `title_pill`, `titled_panel`, `pill` are defined **only** in `render/kits/bangdream/kit.py:197/226/261`. `CheckinCard`, `EnvelopeCard`, `EnvelopeListCard`, `RankCard`, `TaskCard` all write `kit.title_pill(...)` with no `isinstance` branch. `AttributeError` on 7 of 8 kits.

Separately, the header **hierarchy inverts between kits and nobody noticed**. `BanGDreamTitlePill` at `pill_height=57` computes title font `57*33//61 = 30px` and subtitle font `(57*85//62)*36//75 = 37px` — the subtitle is *larger*. The existing house fallback (`mines/render/field.py:76-84`, `one_stroke/render/leaderboard.py:165-173`) is a single 24px line `"标题 - 副标题"`. Identity's `response_card` proposes title 30 / subtitle 24. So the same card's dominant text is the subtitle on bangdream and the title on the other seven — and every card here puts the player-specific fact in the subtitle (`香澄 · Lv.24 · 第 3 名`, `第 24 天 · 香澄`, `#3 · 香澄`).

**Winner:** `utils/cards.py::response_card` is the only header constructor in the codebase; it emits a two-tier header for **all eight** kits with the same hierarchy (title smaller/muted, subtitle larger/`text_color`), and picks `title_pill` only under `isinstance`. No renderer in either cluster may define a fourth `_title_bar`. Also fix the two existing copies while you are there.

---

## P1 — same concept, different rendering

### 6. Two ladder cards with different row anatomy; both cite the same precedent.
`SeasonLadderCard` (rank cell `Fixed(72)`, top-3 = filled panel r=22 with parenthesised `( 1 )`, name `Fill()` 23px, value `Fixed(140)`, row h=56 gap=18, "you" = 3px tick + ink-vs-muted) vs `RankCard` (rank cell `Fixed(56)`, top-3 = filled panel r=14 white text, bare numeral for 4+, name `Fill()` 23px, `Fixed(96)` + `Fixed(150)`, row h=52 gap=18, "you" = separator + the word 你 + gap bar). `EnvelopeCard`'s ledger is a *third* rank/name/value row idiom.

**Winner:** one `utils/cards.py::ladder_rows(kit, rows, *, highlight, columns)`. Take identity's h=56/gap=18 (52 is tight under a 30px badge) and rank cell `Fixed(72)` (56 does not fit three digits at 30px). Take economy's top-3 treatment: filled badge for 1-3, **bare numeral** for 4+ — drop identity's parentheses, the filled-vs-absent shape is already the two-signal cue and it is exactly `leaderboard.py:22-29`'s precedent. Take economy's self-marker (separator + the word 你), which is the strongest monochrome signal, plus identity's ink-vs-muted.

### 7. The 6px ink left-rule means four different things.
"the row that just claimed" (`EnvelopeCard`), "today's task" (`TaskCard`), "a reward you gained" (`CheckinCard` REWARD STRIP), and identity's 3px variant means "this is you" (`SeasonLadderCard`). One glyph, four meanings, across cards a player sees in the same scrollback.

**Winner:** left-rule is reserved for **"this row is you / this row is now"** — your claim, your task today, your ladder row. `CheckinCard`'s reward strip is a list of gains, not a self-marker; give it a leading value column instead.

### 8. Three renderings of the same three balances.
`InventoryCard` currency grid (赛季积分 / 2,350 / Pt / scope), `PlayerCard` stat grid (赛季 Pt / 1,203), `PlayerInfoCard` stat grid (本赛季 Pt / 2,350 · 星星贴纸 · 盆栽). Three label conventions, three unit conventions, three cell geometries.
**Winner:** one `currency_row(kit)` component, labels from `Item.name`, units from `currency.unit_name` (`items.json` is the source of truth: 赛季积分/Pt, 星星贴纸/张, 盆栽/盆). Also note both designs reach for the same number by different accessors — `monetary.get()` *is* `inventory.get_quantity(user_id, "season_point")` (`user_service.py:47`). Pick one call path.

### 9. Terminology drift, some of it already in the shipped strings.
| concept | variants in play | winner |
|---|---|---|
| 星星贴纸 measure word | 张 (`items.json` unit_name, `daily_task/__init__.py:56`, `gacha/service.py:104`) / **个** (`daily/__init__.py:111`, `monetary/level_service.py:74`) / none (`PlayerCard`, `CheckinCard` "+120 星星贴纸") | **张** |
| Pt | `N Pt` (daily, inventory) / **`N 个Pt`** (`red_envelope/messages.py` — 5 strings) | **`N Pt`** |
| season point label | 赛季积分 / 赛季 Pt / 本赛季 Pt | **赛季积分** (name) + **Pt** (unit) |
| off-season label | 休赛期临时 Pt (`daily:56`, `display_scope`) / 临时 Pt (`SeasonStatusCard`) / 休赛期 Pt (`PlayerInfoCard` off-state) | **休赛期临时 Pt** |
| rank format | 第 N 名 / **#7** (`PlayerCard`) | **第 N 名** |
| rarity | `稀有度 6` (current) / StarRow glyphs / the word 六星 / `★★★★★★` (`docs/design:36-52` mandates this) | **★★★★★★** |

On rarity specifically: I checked `old.ttf` — **★ (U+2605) and ☆ (U+2606) are present**; ✓ (U+2713) and 🎉 (U+1F389) are not. So economy's blanket "no ★ glyphs, coverage unverified" is wrong, and identity's custom raw-PIL `StarRow` component is unnecessary. Use text stars; that satisfies the design doc, deletes a component, and fixes item 12 below. The 🎉 in `daily/__init__.py:111` and `level_service.py:74` must be stripped before those strings enter any card — economy caught this, identity did not.

### 10. The signature footer has two rules and only one is right.
Identity prints `香澄 的主题 · 霓虹街机` on **every** card including `/仓库`, `/装扮`, `/抽卡记录` — cards only the owner sees, where third-person possessive reads as a bug. Economy uses `主题 · <name>` for self-service and `<owner> 的主题 · <name>` for shared surfaces (`EnvelopeCard`, `TransferReceiptCard`).
**Winner:** economy's rule. Also: identity says the signature is "suppressed entirely on starter themes"; economy never mentions suppression. Pick one — and be aware that with exactly **one** theme item shipping (`theme_s1_sailing`, `items.json:189-199`), suppression means the footer is invisible for ~everyone on day one, which is the opposite of the product goal.

### 11. Kit display names do not exist anywhere.
Designs print 霓虹街机, 网点纸, 云母窗, 深夜巡演, 樱色, Kasumi 原色, 扬帆主题. A grep across `plugins/`, `docs/`, `UPDATE.md` finds exactly one of these strings: **扬帆主题**, and it is the *item name* of the theme that maps to the sailing kit. So `WardrobeCard`'s theme chips (which read `Item.name`) and every footer (which reads a kit display name) would print different names for the same theme, and `/主题 <token>` has no defined vocabulary.
**Winner:** one `KIT_DISPLAY_NAMES` dict beside `KITS` in `plugins/render/kits/__init__.py:11-20`; `Item.name` for theme items is derived from it or asserted equal to it at sync time.

### 12. Star rows at 14-16px are illegible and they are the manga rarity channel.
`WardrobeCard` chips: 6 slots @14px. `TenPullRevealCard` tiles: 6 @16px. `BannerCard`: @20px. `PlayerInfoCard` title pill: unspecified. Both clusters claim "filled-vs-empty star slots" is what carries rarity in monochrome — at 14px logical, after client downscale, the filled/hollow difference is 1-2px of ink.
**Winner:** `★★★★★☆` as text at ≥22px, or `★6` at 24px on small chips. Never a 6-glyph run below 20px. This also removes the second rarity encoding from the pull tiles (numeral + stars + word), which currently triples the same fact in a 122px-wide cell.

### 13. Page geometry is 2px apart, which breaks every shared grid.
Identity: panel `Fixed(786)` → inner 722. Economy: panel `Fixed(784)` → inner 720. Identity's own risk list already caught the consequence (the 10-column history grid measures 730 against 722). 720 divides cleanly by 2/3/4/5/6/8/9/10/12/15/16; 722 does not.
**Winner:** content column **784**, panel padding **32**, inner **720**, everywhere.

Related and load-bearing: economy sets the root `VStack(..., align="start")`; identity leaves the default `"stretch"`. Per `layout.py:869`, a stretched child gets `rect.width` regardless of its own `Fixed` — so identity's `Fixed(786)` panels are silently overridden and the "same layout, only the theme differs" comparison property (the entire onlooker mechanic) dies. **Winner: economy's `align="start"` + `Frame(header, align_x="start")`.**

---

## P2 — cost, correctness, and policy

### 14. `EnvelopeCard` re-rendered per claim is the worst cost in either cluster.
A 10-part envelope in a live group = 10 full page renders, 10 uploads, 10 near-identical images in everyone's scrollback, each with N nickname lookups and a ledger sort. Both clusters already apply the right rule elsewhere (`星星贴纸不足` stays text because a one-number ack does not earn a render).
**Winner:** render on **create** and on **completion** only. Individual claims stay `恭喜你抢到 N Pt` as text. This also resolves item 15.

### 15. `手气王` cannot be shown mid-race. `EnvelopeCompletionInfo` is only built on the final claim (`red_envelope/service.py:232-238`). The `state="open"` mockup labels row 1 手气王, which will contradict the completion band when a later claim beats it. Omit it until `done`, or label it 暂列第一.

### 16. Cost hazards flagged by one cluster and ignored by the other.
- **Avatar fetch** — `bang_avatar/utils.py:96-104` opens a fresh `ClientSession` per call, no cache. Identity flags it; economy's `PlayerCard` puts an avatar on the highest-frequency command and never mentions it. One `utils/avatars.py::avatar_for(user_id)` with a disk cache, fetched in the handler, never inside `render`.
- **`get_current_season()` runs `sync_seasons_config()` every call** (`season_service.py:95` — re-reads JSON, re-validates every reward item, rewrites and commits). Identity flags it. Economy's `PlayerCard` shows season Pt and calls `is_using_offseason_points()` → `get_point_scope()`, hitting the same path, and never mentions it. Rule: resolve season **once per handler**, thread it in.
- **`atoms.py` only caches `Path` image sources.** If `TenPullRevealCard` art ever ships, that is 11 decodes per ten-pull. Pin: all cosmetic art is `Path`-sourced.

### 17. Shared components are being homed inside plugins.
`RewardStrip` is specified at `plugins/daily_task/render/strip.py` and consumed by `daily` and (per its stated purpose) the game plugins — which makes `plugins/mines` import from `plugins/daily_task/render/`. Identity's `SeasonProgressBar`, `PityGauge` and `StarRow` are declared "shared" with no home at all.
**Winner:** anything crossing a plugin boundary lives in `utils/cards.py` alongside `response_card`/`stat_row`/`theme_signature`. Plugin `render/` dirs hold pages only.

### 18. Duplicated panels that should be one component: today's task appears on `CheckinCard` (TASK panel), `TaskCard` (TODAY panel) and `PlayerCard` (今日任务 cell) with three different layouts → one `task_panel(kit, task, *, compact)`. Season progress appears on `PlayerInfoCard` (strip) and `SeasonStatusCard` (panel) → one component. Off-season appears three ways (`PlayerInfoCard` muted rule, `SeasonStatusCard` 80px numeral variant, `PlayerCard` 56px warning row) with three different strings → one.

### 19. Two ladders, and the profile shows both ranks unlabelled.
`/排行榜` ranks by level/XP; `/赛季排行` ranks by season Pt. `PlayerInfoCard` shows `第 3 名` (season) and `PlayerCard` shows `#7` (level). Merged, the card shows two rank numbers with no metric attached. **Winner:** economy's discipline of naming the ladder in the subtitle (等级榜), applied to both cards and to both profile cells (`赛季第 3 名` / `等级第 7 名`).

### 20. Data that does not exist as designed.
- `GachaResult` (`gacha/service.py:39-48`) has **no `featured` field** — `item_id, character_id, name, rarity, cost, pity_before, pity_after, grant_message`. The 限定 ribbon on `TenPullRevealCard` / `SinglePullCard` has no source. `BannerCard` is fine (`GachaEntry.featured`). Needs a service change; identity lists it as existing.
- `current_rates` (`service.py:129-141`) **lowers** rarity 3/4 under pity. `BannerCard`'s rate table only specifies a `↑` glyph for the 当前 column. Needs `↓` too (both exist in `old.ttf`).
- `EquippedItem` has `UNIQUE(user_id, slot)` (`models.py:101`), so `player_card`'s `title1_image`/`title2_image` pair (`kit.py:167-168`) can never be satisfied. Decide once — titles as text pills from `Item.name`, image params left `None` — before eight kits each invent an answer.

### 21. Sakura's muted text is the weakest text in the system: `muted_text_color` on `panel_fill` measures **2.96:1** (all other kits 3.47–6.48). Both clusters put labels, scopes, dates, hint lines and empty-state rows at 22px muted. In sakura that is below AA at the smallest size used. Either raise muted text to 24px, or forbid `muted_text_color` for anything a player must read (keep it for decoration and secondary labels only).

### 22. Write down the empty-state rule. Identity draws a sound distinction — *partial* absence (an empty ladder slot, an empty wardrobe slot, zero 6★) renders as a muted row **inside** the card because the surrounding structure is the information; *total* absence (`还没有赛季记录`, `还没有赛季历史`) stays text because a render to communicate nothing is waste. It is stated as prose in one cluster's `stays_text` and nowhere else. Promote it to a rule in `utils/cards.py`'s docstring, or eight renderers will each guess.

---

## If only three things get reconciled

1. **One player identity card**, rendered through `kit.player_card` (items 1, 2).
2. **`emphasis(kit)` → `(text_color fill, panel_fill foreground)`** replacing every `fill=primary` + white/default text (item 3) — this is the only item that currently produces *invisible* output, in manga and minimal.
3. **One `response_card` header and one 784/720 geometry with `align="start"`** (items 5, 13) — because "same layout, only the theme differs" is the entire mechanism by which an onlooker can tell a theme is in play, and both clusters currently break it in different ways.