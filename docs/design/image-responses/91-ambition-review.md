# MISSED-OPPORTUNITY CRITIQUE

## Verdict

The batch is **well-engineered and under-imagined**. It reads like a careful audit of every `matcher.finish()` in the repo with a card drawn around each one. The geometry is real, the manga discipline is real, the `stays_text` list is genuinely good judgment. But measured against the user's actual sentence — *"other players can be like 'yoo dude where did u get that sick theme'"* — only **one design in the whole batch (EnvelopeCard) structurally forces a non-owner to look at an owner's theme.** Everything else is a self-query: you type a command, you get your own card. An onlooker never sees it unless you deliberately post it.

And the batch has a foundational blind spot that no cluster names:

> **There is exactly ONE theme item in the entire game.** `plugins/inventory/items.json` contains a single `cosmetic_type: "theme"` entry — `theme_s1_sailing` (扬帆主题, rarity 6). There are **eight** kits in `plugins/render/kits/__init__.py::KITS`. Seven of them are unobtainable. `neon`, `manga`, `fluent`, `sakura`, `midnight`, `minimal` do not exist as items a player can own.

Ten identity cards + eight economy cards are display surfaces for a collectible that has one member, awarded to rank 1-3 and to your first featured 6★. Every mockup in the batch cheerfully writes `香澄 的主题 · 霓虹街机` in the footer. **霓虹街机 is not an item.** The answer to "where did you get that sick theme" is currently "there is no theme, and if there were, there's one of it."

Related, verified by grep: **盆栽 has zero sinks.** `plugins/inventory/service.py:478-488` is the only place it appears — it is granted as duplicate compensation and can never be spent on anything. The design doc says *"Past themes can later enter the 盆栽 shop"* (`docs/design/season-gacha-cosmetics.md:225`). It doesn't exist. The batch designs an `InventoryCard` that displays a currency with no purpose, on a card whose stated justification is *"low information density is the point."*

---

## 1. The lazy ones — named

**InventoryCard** (identity, P2). Three numerals, a link to `/装扮`, and a chip grid. The design's own defence — *"Low information density is the point: this card is where a kit's background treatment is most visible because there is the most empty surface"* — is a confession. This is a text list with padding. **It should not exist.** Its three currency numbers belong on the PlayerInfoCard (where they already are, duplicated), its cosmetic count belongs on the WardrobeCard header (where it already is, duplicated). Killing `/仓库` outright is a better outcome than carding it.

**WardrobeCard** (identity, P1). A grid of Chinese words in rounded boxes. `resources/` is empty; **no cosmetic in items.json has a `metadata` key at all** — I dumped all 23. A wardrobe that cannot show you the items is a text list of item names with a star row. The design acknowledges the risk in a footnote and then ships twelve chips anyway. Until art exists this is `/装扮` reformatted.

**PullHistoryCard** (identity, P2). Killing pagination is right. But "最近 30 抽" as thirty boxes containing the digit `3` is decoration masquerading as data — a player learns nothing from it that `137 抽 · 2 六星` doesn't say in eleven characters. The 六星记录 roll-call is the only real content on the card.

**BannerCard** (identity, P1) and **RankCard** (economy, P0). These are the text, tabulated. Better, honestly better — but "the columns now align" is not "images let us expand the interaction."

**SeasonPassportCard** (identity, P2). The genuinely valuable finding is that `SeasonRanking.reward_summary_json` is written at `season_service.py:309` and read by nothing. That's a **data bug**, not an interaction redesign. Fixing it costs a JSON decode; wrapping it in a card is the least interesting part.

**TaskCard** (economy, P1). Showing the pool is a good instinct. But look at what's in the pool — `plugins/daily_task/tasks.json` has exactly 5 tasks, every one of them "do X once", every one worth 80 stickers. A card that reveals a 5-row flat list reveals that the system is a 5-row flat list. The card is fine; the content it exposes is the problem, and nobody said so.

**EnvelopeListCard** (economy, P1). Rows with bars. Correctly kills `/红包列表`. Unremarkable.

Genuinely good, keep as-is: **TenPullRevealCard** (outcome-dependent composition is the single best idea in the batch), **EnvelopeCard** (creator's kit — the only correct social instinct in the batch), **CheckinCard**'s 7-dot streak strip, **TransferReceiptCard** (cheap, charming, aimed at a second person).

---

## 2. What every cluster missed

### MISS A — The theme economy does not exist, so none of this works

One item, eight kits, no shop, a dead currency. **This is not a rendering problem and no card fixes it.** Before any of these eighteen cards matter, `items.json` needs eight theme entries and 盆栽 needs to buy them. This is a ~40-line JSON + service change and it is worth more than every P1 and P2 card in the batch combined.

### MISS B — The highest-volume images in the bot were not designed at all

Count the sends:

| surface | images per interaction | who sees it |
|---|---|---|
| `plugins/mines/render/field.py` | **one per tile revealed** — `_render_field_image` at `mines/__init__.py:211, 254, 315, 339, 375` | whole channel |
| `plugins/one_stroke/render/graph.py` | **one per move** — `_render_image` at `one_stroke/__init__.py:137, 173, 246, 286` | whole channel |
| `plugins/blackjack/render.py::generate_table` | one per action | whole channel |
| `/资料` PlayerInfoCard | ~1/week | the player |

The batch spent its P0 budget on the last row. A mines game is 5-15 themed images in a row in a group chat; the theme is already being rendered (`field.py:55-58` calls `kit.background()`), and it is **completely anonymous** — there is no name, no avatar, nothing tying that visual to a person. The design doc explicitly built `player_card` to be *transparent* so that *"plugins decide where and how to place it"* (`docs/design/season-gacha-cosmetics.md:262-268`) and **not one design in the batch places it on a game board.**

This is the miss. Fixing it multiplies theme impressions by 10-50x for a fraction of the effort of any single new card.

### MISS C — No side-by-side. The comparison never happens.

`/我 @someone` is the batch's answer to the social loop. But it is **the answer, not the question** — an onlooker has to already be curious enough to type a command. Curiosity has to be generated by an *unsolicited* image where two themes appear at once. There is exactly one such image possible today, and nobody drew it: a **leaderboard where each row is rendered in that player's own theme.**

### MISS D — Every game result is still 3-4 messages, and no game cluster fixed it

Verified call sites, all of them `send` + `send` + `send`:
- `mines/__init__.py:252-286` — field+text, then task_msg, then level_msg. **Three messages.**
- `one_stroke/__init__.py:245-272` — same shape. **Three.**
- `cck/__init__.py:272-297` — answer text, full_image, task_msg, level_msg. **Four.**
- `guess_chart/__init__.py:349-379` — text, task, level, jacket. **Four.**
- `daily/__init__.py:123-131` — msg, then level_msg. **Two.**

The economy cluster invented `RewardStrip` as a shared Component to fix this and then applied it only to `CheckinCard`. The games — where it fires eight times — got nothing.

### MISS E — Progression, near-misses, personal bests: all invisible, all already in the DB

- `OneStrokeGame.elapsed_seconds` + `get_leaderboard()` — a new personal best is **indistinguishable from any other win** (`Messages.WIN` prints a time and a number).
- `mines/session.py:34-43` — the full-clear multiplier is a pure function of `(25, mines, revealed_count)`. "You took 3.2x; the full board was 47.8x" is one `comb()` call. Never shown.
- `BlackjackGame` has `result` + `timestamp` per hand — win/loss streaks are one query. Never shown.
- `settle_season()` writes a mail (`season_service.py:445-452`). The **season ending** — the single biggest emotional moment in the entire product — is a text mail body. Nobody designed it.

### MISS F — Three matplotlib charts, and the batch caught one

The identity cluster correctly flagged `inventory/season_render.py` as theme-breaking. It missed:
- `plugins/blackjack/stats_service.py::create_win_loss_chart`
- `plugins/mines/stats_service.py::create_win_loss_chart`

Both are attached to emoji-laden text blocks (`blackjack/__init__.py:240-244`, `mines/__init__.py:417-421`) using 🎴📊💰🎰🏆 — and `CHINESE_FONT` is `old.ttf`, which has no emoji coverage. Same bug the batch correctly caught for `🎉` at `daily/__init__.py:111` and `monetary/level_service.py:74`. Two matplotlib defaults survived the audit.

---

## 3. Proposals, ranked by delight ÷ effort

### ★ #1 — Put the player on the game board (`GameIdentityStrip`)

**Effort: S** (one shared Component, four call sites) · **Delight: enormous** · This is the whole product goal, delivered by a 96px strip.

```
plugins/render/strip.py :: identity_strip(kit, *, avatar, name, title, level, line) -> Component
Placed as the FIRST child of the existing mines / one_stroke / blackjack pages.
inner width 786, height 96 — costs ~8% of a page that already renders.

+==========================================================================+   <- mines field page, unchanged below
| (O)  香澄  Lv.24                        扬帆之星        3.20x · 640 Pt   |   96px strip
|  64px  28px  22px muted                 title pill 22px   24px right     |
| ------------------------------------------------------------------------ |   kit.separator()
|                                                                          |
|   [ 1 ][ 2 ][ 3 ][ 4 ][ 5 ]     <- the existing 5x5 field, untouched     |
|   [ 6 ][ * ][ 8 ][ 9 ][10 ]                                              |
|                    ...                                                   |
+==========================================================================+
```

The right-hand slot is the per-plugin status line, which **also deletes** `mines/__init__.py:73-78 _format_status()` and `Messages.PROGRESS` from one_stroke — those text lines move into the image where they belong.

Why this beats everything else in the batch: a single mines round posts 8-12 of these into a group chat, each one carrying an avatar, a name, a title and the theme's background/panel/text treatment. Nobody has to run a command. The onlooker's question generates itself. Manga: avatar is the only colour object and it is user art; everything else is ink text and a filled title pill.

Cost control: avatar must be **disk-cached by user_id** and resolved once at session creation, threaded into the renderer — never fetched inside `render`. `plugins/bang_avatar/utils.py:82` opens a fresh `aiohttp` session per call.

---

### ★ #2 — `/主题` gallery: the same card in all eight kits, one image

**Effort: S** (pure composition, zero new data) · **Delight: very high** · The only command in this entire review that is *impossible* as text.

```
AutoPage(min_width=896, padding=48) — 898 x ~1180, portrait
Each tile renders a MINIATURE PlayerInfoCard using that kit's OWN atoms.

+==========================================================================+
| 主题图鉴                                        已拥有 2 / 8             |
|                                                                          |
| +---------------------+ +---------------------+                          |  Grid(columns=2,
| |####################| |                     |                          |  column_track=Fixed(389),
| |# (O) 香澄  Lv.24  #| |  (O) 香澄  Lv.24    |                          |  row_track=Fixed(230), gap=24)
| |#  2,350 Pt  第3名 #| |   2,350 Pt  第3名   |                          |
| |####################| |                     |                          |  each tile is built with
| | 原色 Kasumi  使用中 | | 深夜巡演   1200 盆   |                          |  KITS[name]() — a REAL
| +=====================+ +---------------------+                          |  8-kit render, not a swatch
| +---------------------+ +---------------------+                          |
| | (O) 香澄  Lv.24     | | (O) 香澄  Lv.24     |                          |
| |  2,350 Pt  第3名    | |  2,350 Pt  第3名    |                          |
| | 网点纸      800 盆  | | 霓虹街机   1200 盆   |                          |
| +---------------------+ +---------------------+                          |
| +---------------------+ +---------------------+                          |
| | 樱色     赛季前50   | | 云母窗      800 盆   |                          |  locked tiles render the
| +---------------------+ +---------------------+                          |  kit REAL but at 45% opacity
| +---------------------+ +---------------------+                          |  + the acquisition line
| | 扬帆主题    已拥有   | | 极简       初始拥有  |                          |
| +---------------------+ +---------------------+                          |
|                                                                          |
|  /主题 霓虹街机  切换 · 盆栽 480 盆                                       |
+==========================================================================+
```

Every tile is a genuine render of that kit — the page is a **live eight-way theme comparison in one image**, which is exactly the artifact a curious onlooker needs and exactly what a text list cannot be. It doubles as the shop front (see #3) and as the manga-safety regression test the batch's own risk list asks for (*"Every one of these cards must be rendered in all eight kits before shipping"*) — here that check is the product.

Manga: locked/owned is opacity + the word 使用中/已拥有 + a price string. Three signals, no hue.

---

### ★ #3 — Make the seven missing themes real: 盆栽 shop + 8 theme items

**Effort: S** (JSON + one service function + reuse #2's page) · **Delight: this is the loop.**

```json
{"item_id": "theme_neon",   "category": "cosmetic", "name": "霓虹街机",
 "cosmetic": {"cosmetic_type": "theme", "rarity": 6},
 "metadata": {"kit": "neon", "price_bonsai": 1200}}
```

`kit_for_user` then reads `metadata.kit` instead of hard-coding one id — which is the mapping the foundation needs anyway and which nobody specified. Pricing lands naturally on the existing duplicate-compensation table (`service.py:34-54`: a duplicate 6★ standing art pays 60 盆; a duplicate theme pays 120): **~15 duplicate pulls per theme.** That single number converts the gacha's dead-end compensation into the acquisition ramp for the exact object the whole batch is trying to make desirable. `/主题 买 霓虹街机` returns the `/主题` gallery **re-rendered in the kit you just bought.**

Without this, cards #1, #2 and every card in the batch are chrome on an empty box.

---

### ★ #4 — One result card per game (`GameResultCard`), killing 3-4 sends

**Effort: M** (one shared page shape, four adopters) · **Delight: high** · Also the correct home for `RewardStrip`, which the economy cluster invented and then didn't deploy where it fires.

```
+==========================================================================+
| (O) 香澄  Lv.24                                          扬帆之星         |   the #1 strip, reused
| ------------------------------------------------------------------------ |
|                                                                          |
|   [ 1 ][ * ][ 3 ][ 4 ][ 5 ]        <- final board, mines revealed        |   existing renderer
|   [ 6 ][ 7 ][ 8 ][ * ][10 ]           (mines/__init__.py:249 already      |
|                  ...                   calls reveal_all_mines())          |
|                                                                          |
| +----------------------------------------------------------------------+ |
| |   ＋640          Pt              收手     3.20x     余 2,990 Pt       | |  80px / 34px / 24px
| +----------------------------------------------------------------------+ |
| |  还剩 6 格没翻 · 满盘 47.8x = 9,560 Pt                                | |  <-- NEAR MISS. one comb()
| +----------------------------------------------------------------------+ |      call. never shown today.
| | ▌任务完成  见好就收                              ＋80 星星贴纸        | |  \  RewardStrip rows —
| | ▌升级      Lv.23 → Lv.24                        ＋120 星星贴纸       | |  /  these are the 2 extra sends
| +----------------------------------------------------------------------+ |
|                                              | 香澄 的主题 · 霓虹街机    |
+==========================================================================+
```

Adopters and what dies:
- mines → `__init__.py:252-286` (3 sends → 1), `:314-324`, `_format_status` at `:73-78`
- one_stroke → `__init__.py:245-272` (3 → 1), `Messages.WIN` / `BIRTHDAY_WIN`
- cck → `__init__.py:272-297` (4 → 1; the `full_image` becomes the card's hero, which is the *right* place for it)
- guess_chart → `__init__.py:349-379` (4 → 1; jacket becomes the hero)

The near-miss line is the delight payload and it is free — `1/(comb(25-mines, n)/comb(25,n)) * 0.97` for `n = safe_cells`.

---

### ★ #5 — Ladder rows in each player's own theme (`SeasonLadderCard`, amended)

**Effort: M** (top 3 only — 3 extra kit instantiations) · **Delight: high** · The batch's ladder gives ranks 1-3 a filled panel in *the viewer's* kit. Wrong instinct. Give them their own.

```
| +----------------------------------------------------------------------+ |
| | /######################################################\             | |  rank 1 row drawn with
| | |( 1 )  彩纱          扬帆之星              4,980 Pt    |             | |  KITS[theme_of(user1)]()
| | \######################################################/             | |  —彩纱's neon panel
| | +------------------------------------------------------+             | |
| | |( 2 )  有咲          扬帆领奖台            2,530 Pt    |             | |  有咲's manga panel
| | +------------------------------------------------------+             | |
| | +======================================================+             | |
| | |( 3 )  香澄          扬帆之星              2,350 Pt    |             | |  香澄's sakura panel
| | +======================================================+             | |
| |   4     沙绫                              1,930 Pt                   | |  ranks 4+ : viewer's kit,
| |   5     日菜                              1,720 Pt                   | |  bare rows, no panel
```

Three different panel silhouettes stacked vertically in one unsolicited group-chat image, each labelled with a name. That is the comparison the batch never built, and it makes the podium **visually worth reaching** rather than just numerically. Manga-safe: a manga player's row is an ink-bordered white slab next to a neon player's dark slab — the difference is *structure*, and every row still carries `( n )`, a name and a numeral.

Cost: 3 extra `kit_for_user` calls, all resolved in the handler.

---

### ★ #6 — `SeasonFinaleCard` — the moment nobody designed

**Effort: M** · **Delight: very high, once per season** · Today the biggest event in the product is a mail body composed at `season_service.py:445-452`.

```
+==========================================================================+
| Kasumi，扬帆起航    赛季结束                                              |
|                                                                          |
| +----------------------------------------------------------------------+ |
| |                        第 3 名                                        | |  rank numeral 110px —
| |                      2,350 Pt                                        | |  the biggest object in
| |            2,350 → 0，下赛季从头开始                                   | |  the whole bot
| +----------------------------------------------------------------------+ |
| |  你解锁了                                                             | |  from reward_summary_json
| |  +-------------+ +---------------+ +-------------+                    | |  (currently DEAD DATA,
| |  | 扬帆领奖台  | | 前三头像框     | | 扬帆主题     |                   | |   written and never read)
| |  +-------------+ +---------------+ +-------------+                    | |
| |  ------------------------------------------------------------------  | |
| |  06-02  第 41 名  ......                                             | |  rank-over-time sparkline
| |  06-14  第 12 名     \___                                            | |  from SeasonRankSnapshot,
| |  06-29  第  3 名         \____                                       | |  ink polyline + 3 labels
| |  你从第 41 名爬到了第 3 名                                            | |
| +----------------------------------------------------------------------+ |
|                                              | 香澄 的主题 · 扬帆主题    |
+==========================================================================+
```

Rendered **in the theme the season just awarded them** — so the reward is demonstrated by the message announcing it. This is the batch's own best idea (equip-confirmation-is-the-demo) applied to the moment it matters most.

---

### ★ #7 — `/图鉴` collection sheet with acquisition sources

**Effort: M** · **Delight: high** · The batch prints `12 / 25` on four different cards and never draws the 25.

```
+==========================================================================+
| 图鉴                                        香澄 · 12 / 23               |
|                                                                          |
| 头像框  4 / 5   [##][##][##][##][  ]                                     |  Grid(columns=6,
| 称号    3 / 6   [##][##][##][  ][  ][  ]                                 |  column_track=Fixed(112),
| 主题    2 / 8   [##][##][  ][  ][  ][  ][  ][  ]                         |  row_track=Fixed(112))
| 立绘    3 / 9   [##][##][##][  ][  ][  ][  ][  ][  ]                     |  owned = filled + name
|                                                                          |  locked = outline + "?"
| ------------------------------------------------------------------------ |
| 还差一步                                                                 |
|   扬帆前三头像框     赛季前 3 名     你现在第 3 名                        |  <-- the payload:
|   霓虹街机           1200 盆栽      你有 480 盆                           |      every locked item
|   市谷有咲 扬帆立绘   限定卡池       保底 53 / 90                          |      with its EXACT source
+==========================================================================+
```

Every source string here already exists in config: `seasons.json:104-157` `reward_tiers`, the banner `entries`, and (with #3) `metadata.price_bonsai`. **Nothing needs to be invented — it needs to be joined and shown.** This is the card that makes people want things, and it is currently the only thing in the product that would.

---

### ★ #8 — Personal-best and streak marking on existing result cards

**Effort: S** (two queries, one row in `GameResultCard`) · **Delight: solid**

```
| ▌新纪录  一笔画 普通  47.2s   旧纪录 58.9s   本群第 2 快                   |
| ▌连胜 4 场  黑香澄                                                       |
```

`OneStrokeGame.elapsed_seconds` + `get_leaderboard(difficulty)` gives both the PB and the channel rank. `BlackjackGame.result` ordered by `timestamp` gives the streak. Both are one query and both currently produce **literally the same message as a mediocre win.**

---

### ★ #9 — `/对比 @someone` — two cards, two themes, one image

**Effort: S** (compose two existing `player_card`s side by side) · **Delight: good, self-limiting**

Portrait, split down the middle, each half rendered in that player's kit, one shared stat spine between them (Lv / Pt / 排名 / 收藏 / 连续签到). Explicit, deliberate theme comparison, and the natural follow-up to seeing #1 or #5 in a scrollback. Cheap because both halves already exist.

---

### ★ #10 — `/名片` — the poster

**Effort: S** · **Delight: good** · A deliberate *brag* command, distinct from `/资料`. Portrait ~900x1200, no stat grid, no season strip: big avatar, frame, name, title, one line of bio, the theme's fullest background treatment, and the theme name at the bottom. `/资料` is a dashboard; `/名片` is a poster you post because it looks good. Different jobs, and the batch conflated them into one card that has to be both and is therefore neither.

---

## 4. What stays text — additions to the batch's list

The batch's `stays_text` is good. Add:

- **Every mid-game prompt** — `Messages.PROMPT`, `INPUT_INVALID`, `ALREADY_REVEALED` (mines), `MOVE_FAIL_*` (one_stroke), `ACTION_PROMPT` (blackjack). These fire **between** image sends. Rendering them turns a 5-move game into 10 image uploads and makes the board itself feel slow. The board image is the state; the prompt is the nudge.
- **`/help`** (`plugins/help/__init__.py`) — a 210-line usage dictionary. Copy-pasteable as text, useless as an image.
- **`/设置昵称` / `/我的昵称`** — pure text-in/text-out. (Though `nickname/__init__.py:78-86` sending **two** messages on first set should become one.)
- **cck/guess_chart hints and wrong-answer silence** — latency-critical, mid-round.

---

## 5. Ship order I'd actually defend

If the answer to "where'd you get that theme" has to work, the order is:

1. **Eight theme items + 盆栽 prices** (#3) — without this nothing else is true
2. **`GameIdentityStrip`** (#1) — 10-50x the theme impressions of every card in the batch, at S effort
3. **`/主题` gallery** (#2) — the answer to the question #1 generates
4. **PlayerInfoCard** — keep it, it's correct, but it is **fourth**, not first
5. **`GameResultCard`** (#4) — deletes ~14 message sends
6. **TenPullRevealCard** — the batch's best card, unchanged
7. **Themed ladder rows** (#5) + **`/图鉴`** (#7)

Cut or defer: `InventoryCard` (delete the command), `WardrobeCard` (blocked on art — ship the slot structure only), `PullHistoryCard`'s 30-dot strip (keep the 六星 roll-call, drop the grid), `SeasonPassportCard` (fix the dead `reward_summary_json` read as a one-line bugfix; the card can wait).

**The single sentence I'd put in front of the team:** the batch built eighteen beautiful windows onto a room with one thing in it.