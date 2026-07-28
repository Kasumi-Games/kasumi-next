# 插件簇：identity

涉及插件：plugins/inventory, plugins/gacha

卡片 10 张 · 交互改动 10 项 · 保留文本 10 项

---

## 卡片设计

### PlayerInfoCard (page: plugins/inventory/render/profile.py::render_profile; component: kit.player_card)  `[P0/L]`
- **插件**：plugins/inventory
- **触发**：/资料 · /个人资料 · new aliases /我 /profile — and it becomes the reply to every equip action
- **目的**：The single highest-value surface in the bot. Today `/资料` with no argument prints ONLY the bio string (plugins/inventory/__init__.py:381-386) — level, Pt, rank, stickers, bonsai, equipped cosmetics and collection count all live one plugin away and are invisible here. This card makes the profile the identity hub, and it is the card a player deliberately posts to show off. `BaseKit.player_card` is declared and raises NotImplementedError (plugins/render/kit.py:162-182); this is the design that fills it.
- **展示数据**：avatar (bang_avatar.utils.get_group_member_head, 640x640 -> displayed 160 = 640/4, integral divisor per house style §2), equipped avatar_frame overlay (get_equipped(user_id)['avatar_frame'] -> Item.name; NO art asset exists today), equipped title as a text pill (Item.name e.g. 扬帆之星) + its CosmeticItem.rarity as a 6-slot star row, nickname (plugins/nickname) falling back to user_id, per _display_name at plugins/inventory/__init__.py:452-458, level (monetary.get_level), season Pt (get_quantity(user_id, SEASON_POINT_ITEM_ID)) and rank (get_user_season_rank), star_sticker + bonsai balances (get_quantity), collection count owned/total cosmetics (list_inventory(category='cosmetic') vs catalog count), gacha total_pulls + pity_count (gacha.service.get_state), profile description (get_profile_description, 100-char validated), season name, start/end times, days remaining, Pt gap to the next rank up
- **主题可见性**：This is THE theme card. Three independent theme signals stack: (1) `kit.player_card` is the one component the design doc explicitly says each kit should compose itself (plugins/render/kit.py:178-181) — bangdream gets the pill/stroke treatment, neon gets tube-glow name text, manga gets a hard ink frame around the avatar, fluent gets a mica-translucent identity slab; (2) the enclosing panels carry each kit's silhouette because `radius` is OMITTED, so the corner alone reads 48 (bangdream) / 8 (fluent) / 10 (neon) / 14 (manga); (3) the background is the kit's own treatment. An onlooker sees the same layout everyone else's card has, with only the theme different — which is exactly what makes cross-comparison in a scrollback work.
- **manga 单色降级**：Nothing carries meaning by hue. Rank/level/Pt are numerals; the title is a word in a pill; rarity is filled-vs-empty star slots; the season bar is solid ink vs outline; collection is '12 / 25'. The avatar is the only color object and it is user art, not state. In manga the identity panel gains a heavy ink border from MangaPanel and the screentone paper sits behind it — arguably the most legible of the eight after client downscale, since text is pure #121214 on #F6F3EC.
- **替代的文本响应**：plugins/inventory/__init__.py:383-386 (`个人简介：\n{description}`) entirely. Absorbs the equip acknowledgement at :144-147 (`已装备 {item} 到 {slot}。`) and the equipped-items line built at :128-130 (`当前装备：k: v, ...`). Also absorbs the two per-user numbers currently only reachable via `/赛季` at :239-245.

```
AutoPage(min_width=896, padding=56, background=_background(kit), child=VStack([...], gap=32))
898 x ~1040 actual

+==========================================================================+
| /==========================\                                             |  header via utils.cards.response_card
| | 资料                     |   title    30px (BD: title_pill band 1)     |  BD -> kit.title_pill("资料", "香澄 · Lv.24 · 第 3 名", 500x57) => measures 548x127
| | 香澄 · Lv.24 · 第 3 名   |   subtitle 37px BD / 24px fallback         |  fallback -> Frame(two-tier header, align_x="start")
| \==========================/                                             |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  kit.panel(radius OMITTED) width=Fixed(786) padding=32 -> inner 722
| |  +-----------+                                                       | |
| |  |###########|   香澄                        +--------------------+  | |  <-- kit.player_card(width=Fixed(722), height=Fixed(240))
| |  |## avatar #|   34px  wrap=False max_lines=1 |   扬帆之星  ★6     |  | |      TRANSPARENT — draws no panel/border of its own
| |  |# 160x160 #|                                +--------------------+  | |      (design doc "Player Info Card", docs/design/...md:261-315)
| |  |###########|                                title pill 24px h=44   | |
| |  +-----------+   Lv.24   ·   2,350 Pt   ·   第 3 名                   | |  stat line 24px, ' · ' separated, wrap=False
| |   frame 200x200                                                       | |  frame drawn via Overlay(avatar, frame) — None today, no asset ships
| |   (Overlay, align center)  --------------------------------------     | |  kit.separator(length=Fill())
| |                  每天都想打黑香澄，输光了就来一笔画混口饭吃。          | |  desc 22px wrap=True max_lines=2 overflow=ellipsis
| +----------------------------------------------------------------------+ |  empty desc -> muted "这个人还没有写简介。"
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  kit.panel(radius omitted) padding=32
| |  Grid(columns=3, rows=2, column_track=Fixed(224), row_track=Fixed(78),| |  3*224 + 2*24 = 720
| |       gap=24)                                                         | |
| |  +----------------+ +----------------+ +----------------+             | |  each cell = utils.cards.stat_row
| |  | 星星贴纸        | | 盆栽            | | 本赛季 Pt      |             | |    label 22px muted, value 40px text_color
| |  |  240           | |  480           | |  2,350        |             | |    Frame(value, align_x="start", align_y="center")
| |  +----------------+ +----------------+ +----------------+             | |
| |  +----------------+ +----------------+ +----------------+             | |
| |  | 装扮收藏        | | 抽卡次数        | | 保底计数       |             | |
| |  |  12 / 25       | |  137           | |  53 / 90      |             | |
| |  +----------------+ +----------------+ +----------------+             | |
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  season strip panel
| |  Kasumi，扬帆起航                                    剩余 6 天         | |  24px left / 22px muted right, one HStack
| |  [######################################............]                 | |  SeasonProgressBar 722x20 r=10 (shared raw-PIL component)
| |  06-01                                                       06-29    | |  22px muted, HStack(start/Fill()/end)
| |  距离第 2 名还差 180 Pt                                                | |  22px — NEW data, computed from _season_point_query neighbours
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
|                                              | 香澄 的主题 · 霓虹街机     |  utils.cards.signature_for(kit, owner) — right aligned,
+==========================================================================+  22px muted, suppressed entirely on starter themes

OFF-STATE: no season open -> the season strip becomes "休赛期 · 临时 Pt 100"
           and the progress bar is replaced by a muted full-width rule.
```

### TenPullRevealCard (plugins/gacha/render/pull.py::render_pull)  `[P0/L]`
- **插件**：plugins/gacha
- **触发**：/抽卡 十连 · /十连 (plugins/gacha/__init__.py:53-58)
- **目的**：Today a ten-pull returns a flat 12-line text list built by `_format_pull_results` (plugins/gacha/__init__.py:115-122) — `- 稀有度 6 户山香澄 扬帆立绘（already_owned_compensated:120）`. It leaks raw machine strings to players and gives the single most screenshot-worthy moment in the bot zero visual weight. This card makes the ten-pull the thing people post in the group, and it changes shape based on the outcome so a good pull LOOKS different, not just reads different.
- **展示数据**：per pull: rarity, entry name, item_id, featured flag (GachaResult, plugins/gacha/service.py:39-49), NEW vs duplicate + bonsai compensation amount — decoded from GrantResult.message ('already_owned_compensated:120' / 'already_owned' / '' , plugins/inventory/service.py:171-178), the extra grants a featured 6★ triggers: gacha_character_frame_item_id + gacha_theme_item_id (plugins/inventory/season_service.py:368-383) resolved to Item.name, pity_before / pity_after (GachaResult), banner.soft_pity_start=70, banner.hard_pity=90 (seasons.json:35-36), banner.name, banner.season_name, total cost paid (banner.ten_cost = 1200 张星星贴纸) and remaining sticker balance after the pull
- **主题可见性**：The tile grid is 10 instances of the kit's panel silhouette side by side — the corner radius difference between fluent (8) and bangdream (48) is unmissable at that repetition count. The hero band is the kit's largest single panel and takes a BanGDreamKit-only upgrade branch (`kit.titled_panel` with the character name as the title, `kit.pill` for the 限定 ribbon) guarded by isinstance, with a five-atom fallback of the same 786x300 box. Because a ten-pull is the message people volunteer into a group chat, this is the card most likely to be seen by a non-owner.
- **manga 单色降级**：Rarity is carried by four redundant non-color cues: the 40px numeral in the tile corner, the filled/empty star slots, the tile's presence-or-absence in the hero band, and the 限定/六星 word. NEW vs duplicate is a word and a number, never a tint. The pity bar is solid ink against an outlined track. Nothing in this card requires reading a hue. Hard-coded rarity tokens (if any are added later) must follow the house rule at field.py:34 / graph.py:208-214: theme-invariant color ALWAYS paired with a glyph.
- **替代的文本响应**：plugins/gacha/__init__.py:53-58 and the `_format_pull_results` helper at :115-122 in full, including the raw `grant_message` leak at :118 and the bare `当前保底计数：{n}` at :121.

```
AutoPage(min_width=896, padding=56, background=_background(kit), child=VStack([...], gap=32))
898 x ~1200 actual (6★ variant) / ~900 (no-hero variant)

=== VARIANT A: max rarity == 6 ===============================================
+==========================================================================+
| /==============================\                                          |  response_card header
| | 十连                         |                                          |  title 30px
| | Kasumi，扬帆起航 限定卡池     |                                          |  subtitle = banner.name (truncated max_lines=1)
| \==============================/                                          |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  HERO BAND — kit.panel(radius omitted) 786 x 300, padding=32
| | +--------+                                              +----------+  | |
| | |        |  户山香澄 扬帆立绘                            |   限定   |  | |  hero art 200x200 if metadata.art exists,
| | | 立绘   |  40px  wrap=False max_lines=1                 +----------+  | |  else a 200x200 kit.panel placeholder with
| | |200x200 |                                          ribbon pill 24px   | |  the character name at 30px centered
| | |        |  [*][*][*][*][*][*]   六星                                  | |  StarRow(filled=6, slots=6, size=28)  + word 30px
| | +--------+                                                             | |
| |            ------------------------------------------------------     | |  kit.separator()
| |            同时获得   +--------------+ +--------------+                | |  <-- HUMANISED grant_message. Today this is the raw
| |            22px muted | 扬帆六星头像框| | 扬帆主题      |               | |      string 'already_owned_compensated:120' printed
| |                       +--------------+ +--------------+               | |      verbatim at __init__.py:118
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  Grid(columns=5, rows=2,
| | +-----+ +-----+ +-----+ +-----+ +-----+                              | |       column_track=Fixed(146), row_track=Fixed(196), gap=14)
| | |  6  | |  3  | |  4  | |  3  | |  5  |   <- rarity numeral 40px TL    | |  5*146 + 4*14 = 786 exactly
| | |     | |     | |     | |     | |     |                               | |  2*196 + 14  = 406
| | |香澄 | |占位 | |占位 | |占位 | |占位 |   <- name 22px wrap max_lines=2| |  tile = kit.panel(radius=16), padding=12 -> 122 usable
| | |扬帆 | |3-1  | |4-2  | |3-2  | |5-1  |                               | |
| | |立绘 | |     | |     | |     | |     |                               | |
| | |*****| |*..  | |**.  | |*..  | |***. |   <- StarRow 6 slots @16px     | |  6*16 + 5*2 = 106 <= 122
| | | NEW | |+30盆| | NEW | |+30盆| | NEW |   <- tag 22px                  | |  NEW / +N盆 / (nothing)
| | +-----+ +-----+ +-----+ +-----+ +-----+                              | |
| | +-----+ +-----+ +-----+ +-----+ +-----+                              | |
| | |  3  | |  4  | |  3  | |  3  | |  4  |                              | |
| | | ... | | ... | | ... | | ... | | ... |                              | |
| | +-----+ +-----+ +-----+ +-----+ +-----+                              | |
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  PITY GAUGE — shared component, also used on
| |  保底计数                                              0 / 90         | |  SinglePullCard and BannerCard
| |  [.....................................................]              | |  bar 722x20 r=10; ink-filled portion = pity/hard_pity
| |          ^软保底 70                                                    | |  notch + label 22px at soft_pity_start (seasons.json:35)
| |  六星重置了保底                                                        | |  22px status line
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
|                                              | 香澄 的主题 · 霓虹街机     |  signature_for(kit, owner)
+==========================================================================+

=== VARIANT B: max rarity == 5 ==============================================
Same page; HERO BAND shrinks to 786x180, art 120x120, name 34px, no ribbon,
no "同时获得" row.

=== VARIANT C: max rarity <= 4 ==============================================
HERO BAND IS DROPPED ENTIRELY. The pity gauge moves to the TOP of the body
and grows to 786x160 with the countdown promoted to 40px:
| +----------------------------------------------------------------------+
| |  距离保底还有 37 抽                                    53 / 90        |   40px numeral line
| |  [################################.....................]              |
| |          ^软保底 70   还有 17 抽进入软保底                              |   22px
| +----------------------------------------------------------------------+
A bad pull still returns a card with a reason to pull again. Today a bad
ten-pull is ten identical-looking text lines and one bare number (:121).
```

### SinglePullCard (same module, plugins/gacha/render/pull.py::render_pull with count=1)  `[P0/M]`
- **插件**：plugins/gacha
- **触发**：/抽卡 单抽 · /抽卡 抽 (plugins/gacha/__init__.py:45-51)
- **目的**：A single pull is the highest-frequency gacha interaction, so it must be cheap, but it is also where a solo 6★ deserves the most weight. Same renderer, no grid: hero band + pity gauge only. Keeps the page short (~760px tall) so it uploads fast and reads on a phone without pinching.
- **展示数据**：single GachaResult: rarity, name, featured, NEW/duplicate + bonsai, extra grants for a first featured 6★, pity_after / hard_pity / soft_pity_start, single_cost (120 张) and star_sticker balance after the pull
- **主题可见性**：One large kit panel plus the kit background at a short page height — the theme occupies proportionally more of the image than on any other card in the cluster. The pity gauge fill uses `getattr(kit, 'primary', kit.text_color)` per house rule §9 (MinimalKit has no `primary`), so it tints where a kit has an accent and stays ink where it doesn't.
- **manga 单色降级**：Same as the ten-pull: numerals, star slots, words. The gauge is ink-solid vs outline.
- **替代的文本响应**：plugins/gacha/__init__.py:45-51 (via the same `_format_pull_results` at :115-122).

```
AutoPage(min_width=896, padding=56) — 898 x ~760

+==========================================================================+
| /==============================\                                          |
| | 单抽                         |                                          |
| | Kasumi，扬帆起航 限定卡池     |                                          |
| \==============================/                                          |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  HERO BAND 786 x 300 (rarity 6) / 220 (rarity <= 5)
| | +--------+                                              +----------+  | |
| | |        |  户山香澄 扬帆立绘                            |   限定   |  | |
| | | 立绘   |  40px                                        +----------+  | |
| | |200x200 |                                                            | |
| | |        |  [*][*][*][*][*][*]   六星        NEW                       | |  StarRow 28px + word 30px + NEW tag 24px
| | +--------+                                                            | |
| |            ------------------------------------------------------     | |
| |            同时获得  +--------------+ +------------+                   | |
| |                     | 扬帆六星头像框| | 扬帆主题    |                  | |
| |                     +--------------+ +------------+                   | |
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |
| |  保底计数                                              0 / 90         | |  identical PityGauge component
| |  [.....................................................]              | |
| |          ^软保底 70                                                    | |
| |  120 张星星贴纸 · 余 120 张                                            | |  cost + remaining balance, 22px muted
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
|                                              | 香澄 的主题 · 霓虹街机     |
+==========================================================================+

Low-rarity single pull: hero band drops to 220px, name 34px, no ribbon,
no 同时获得 row, and the pity line reads "距离保底还有 37 抽" at 30px.
```

### WardrobeCard (plugins/inventory/render/wardrobe.py::render_wardrobe)  `[P1/M]`
- **插件**：plugins/inventory
- **触发**：/装扮 with no argument (plugins/inventory/__init__.py:123-138)
- **目的**：Today `/装扮` prints `装扮：` then `当前装备：theme: theme_s1_sailing，avatar_frame: frame_default` then one `- 名字 (item_id)` line per owned cosmetic (:126-134). It exposes raw item_ids and slot keys to players, and gives no sense of what a slot even is. A four-slot grid makes the wardrobe legible at a glance AND makes the equip command usable by name.
- **展示数据**：all owned cosmetics grouped by CosmeticItem.cosmetic_type (list_inventory(user_id, category='cosmetic', include_season=False), plugins/inventory/service.py:275-288), the four slots in fixed order 头像框 / 称号 / 主题 / 立绘 — matching the alias table at plugins/inventory/service.py:404-415, equipped item per slot (get_equipped, :333-337) resolved to Item.name instead of item_id, CosmeticItem.rarity as a 6-slot star row, owned/total collection count in the header subtitle
- **主题可见性**：12+ chips means 12 repetitions of the kit's corner radius and panel fill in one image — the highest silhouette-repetition count of any card here. The theme slot section literally lists the theme the card is being rendered in, with 使用中 on it: the card names its own skin. Slot panels take the BanGDreamKit `titled_panel` upgrade branch (slot name as the stroked title) with a five-atom label+separator fallback of the same box.
- **manga 单色降级**：Equipped state is a double ink rule PLUS the word 使用中 (two signals, following the leaderboard's filled-vs-empty precedent at one_stroke/render/leaderboard.py:22-29). Rarity is filled/empty star slots. Slot identity is a Chinese word. No hue anywhere.
- **替代的文本响应**：plugins/inventory/__init__.py:126-138 in full (the `装扮：` header, the `当前装备：` join at :128-130, the `- {name} ({item_id})` loop at :132, and the `还没有可用装扮。` empty state at :134).

```
AutoPage(min_width=896, padding=56, background=_background(kit), child=VStack([...], gap=32))
898 x ~1180

+==========================================================================+
| /==============================\                                          |
| | 装扮                         |                                          |
| | 香澄 · 已解锁 12 / 25        |                                          |
| \==============================/                                          |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  SLOT PANEL — kit.panel(radius omitted), padding=32, one per slot
| |  头像框                                          扬帆冠军头像框        | |  slot label 24px / equipped name 24px right-aligned
| |  ------------------------------------------------------------------  | |  kit.separator()
| |  +---------------------+ +---------------------+ +------------------+ | |  Grid(columns=3, column_track=Fixed(230),
| |  | 默认头像框     ***. | | 扬帆冠军头像框 ****** | | 扬帆前十头像框 **.. | |       row_track=Fixed(76), gap=16) -> 3*230+2*16 = 722
| |  |                     | |          使用中  ####| |                  | | |  chip = kit.panel(radius=16), padding 12
| |  +---------------------+ +=====================+ +------------------+ | |  name 22px wrap=False max_lines=1 ellipsis
| +----------------------------------------------------------------------+ |  StarRow 6 slots @14px right-aligned
|                                                            gap 32        |  EQUIPPED chip: double-rule border (3px inset,
| +----------------------------------------------------------------------+ |  kit.text_color) + the word 使用中 — two signals
| |  称号                                                  扬帆之星        | |
| |  ------------------------------------------------------------------  | |
| |  +---------------------+ +---------------------+ +------------------+ | |
| |  | 初始之星       ****.| | 扬帆之星    ****** | | 扬帆启程    ***.. | | |
| |  |                     | |         使用中  ####| |                  | | |
| |  +---------------------+ +=====================+ +------------------+ | |
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |
| |  主题                                                  霓虹街机        | |
| |  ------------------------------------------------------------------  | |
| |  +---------------------+ +---------------------+ +------------------+ | |
| |  | Kasumi 原色    ***..| | 霓虹街机    ****** | | 扬帆主题    ****** | | |
| |  |                     | |         使用中  ####| |                  | | |
| |  +---------------------+ +=====================+ +------------------+ | |
| |                                          详细预览 → /主题             | |  22px muted pointer to the gallery card
| +----------------------------------------------------------------------+ |  (the /主题 gallery is the theme-plumbing foundation's Tier 2)
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |
| |  立绘                                                  未装备          | |  unequipped slot: muted "未装备"
| |  ------------------------------------------------------------------  | |
| |  +---------------------+ +---------------------+                      | |  fewer than 3 owned -> grid just ends;
| |  | 户山香澄 扬帆  ******| | 占位角色立绘5-1 ****.|                     | |  no placeholder chips (that's the ladder card's job)
| |  +---------------------+ +---------------------+                      | |
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
|                                              | 香澄 的主题 · 霓虹街机     |
+==========================================================================+

EMPTY SLOT with zero owned items -> a single full-width muted row
"还没有这个位置的装扮" at 22px, no chip grid. The panel still renders so the
four-slot structure stays constant across players.
```

### SeasonStatusCard (plugins/inventory/render/season.py::render_season)  `[P1/M]`
- **插件**：plugins/inventory
- **触发**：/赛季 with no argument (plugins/inventory/__init__.py:223-245)
- **目的**：Today `/赛季` prints four lines: name, ISO date range, `当前 Pt: {n} Pt`, `当前排名：第 {n} 名` (:239-245). The whole reward ladder — five tiers with concrete titles, frames, themes and sticker counts — exists in seasons.json:104-157 and is shown to a player exactly once, inside a settlement mail (season_service.py:445-452). This card surfaces the ladder while the season is still running, which is the entire motivation to keep playing.
- **展示数据**：season.name, season.start_time, season.end_time formatted like _format_time (plugins/inventory/__init__.py:446-449), plus days remaining, current Pt and rank (get_user_season_rank, plugins/inventory/season_service.py:203-211), Pt gap up to the next rank and lead over the rank below — both new, both computable from the same _season_point_query rows, the five reward tiers from season metadata (reward_tiers + participation_reward, seasons.json:104-157) with item_ids resolved to Item.name, which tier the player currently qualifies for (_reward_tier_for_rank logic, season_service.py:478-484), off-season: temporary Pt balance and the latest settled season's personal result
- **主题可见性**：The 80px Pt numeral is the largest text object in the cluster and is drawn with `kit.text` — on bangdream it picks up the CHINESE_FONT weight, on neon the tube-glow palette, on fluent the flat mica text color. The current-tier highlight is a filled kit panel at pill radius, which is the one place a kit's `primary` shows as a large solid area (guarded with getattr fallback for MinimalKit).
- **manga 单色降级**：Rank is a numeral; the current tier is marked by BOTH a filled ink row and the literal words "你在这"; the progress bar is ink-solid vs outlined track; time is dates and a day count. The reward ladder is pure text rows. Fully monochrome-safe.
- **替代的文本响应**：plugins/inventory/__init__.py:239-245 (the four-line season status) and :229-236 (the off-season block).

```
AutoPage(min_width=896, padding=56, background=_background(kit), child=VStack([...], gap=32))
898 x ~1060

+==========================================================================+
| /==============================\                                          |
| | 赛季                         |                                          |
| | Kasumi，扬帆起航 · 剩余 6 天  |                                          |
| \==============================/                                          |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  kit.panel(radius omitted), padding=32
| |                                                                      | |
| |   2,350                                          第 3 名             | |  Pt numeral 80px (house glanceable size, cf mines field.py:26)
| |   Pt                            30px             30px                | |  rank 40px inside a rank pill for top 3
| |   22px muted                                                         | |
| |   ------------------------------------------------------------------ | |
| |   距离第 2 名还差 180 Pt          ·          领先第 4 名 420 Pt        | |  24px — both NEW, from _season_point_query neighbours
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |
| |  赛季进度                                     06-01 → 06-29          | |  24px / 22px muted
| |  [######################################............]                | |  SeasonProgressBar 722x20 r=10
| |  已过 22 天 · 剩余 6 天                                                | |  22px
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  REWARD LADDER — five rows, current tier marked
| |  赛季奖励                                                            | |  24px
| |  ------------------------------------------------------------------  | |
| |  第 1 名     贴纸500 · 扬帆之星 · 冠军头像框 · 扬帆主题               | |  rank cell Fixed(120) 24px,
| |  第 2-3 名   贴纸300 · 扬帆领奖台 · 前三头像框 · 扬帆主题   << 你在这  | |  rewards Fill() 22px wrap=False ellipsis,
| |  第 4-10 名  贴纸200 · 扬帆十强 · 前十头像框                          | |  marker Fixed(90)
| |  第 11-50 名 贴纸100 · 扬帆同航                                       | |  CURRENT tier row: filled kit.panel(radius=height//2)
| |  参与奖励    扬帆启程                                                 | |  behind the row + the words "你在这"
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
|                                              | 香澄 的主题 · 霓虹街机     |
+==========================================================================+

OFF-SEASON VARIANT (replaces __init__.py:229-236) — same page, body swaps to:
| +----------------------------------------------------------------------+
| |   100                                                                |   80px
| |   临时 Pt                                                            |
| |   ------------------------------------------------------------------ |
| |   休赛期 Pt 可以游玩和转账，但不会计入下一赛季。                       |   22px wrap
| +----------------------------------------------------------------------+
| +----------------------------------------------------------------------+
| |  最近赛季   Kasumi，扬帆起航      你的成绩  第 3 名 · 2,350 Pt        |   from SeasonRanking
| +----------------------------------------------------------------------+
```

### SeasonLadderCard (plugins/inventory/render/ladder.py::render_ladder)  `[P1/M]`
- **插件**：plugins/inventory
- **触发**：/赛季排行 · /赛季排行榜 (plugins/inventory/__init__.py:253-285)
- **目的**：Today this dumps up to FIFTY lines of `{n}. {nickname}: {pts} Pt` into a chat message (:260-278). Nobody reads rank 37. The information a player actually wants is: who is on top, and where am I relative to the people immediately around me. A card gives top 10 at a readable size and pins the player's own neighbourhood — and it removes the 50-row wall from the group chat entirely.
- **展示数据**：top 10 of get_active_ranking(limit=50) (plugins/inventory/season_service.py:196-201) — the limit drops from 50 to 10 for the board, settled seasons use list_settled_rankings(season, limit=50) -> rank + final_points (:386-394), nicknames via _display_name (plugins/inventory/__init__.py:452-458), the requesting player's own rank and Pt plus the two neighbours above/below, Pt gap to the next rank up, rank-10 and rank-50 point thresholds over time from SeasonRankSnapshot (list_snapshots, :397-404)
- **主题可见性**：This is the card an onlooker is MOST likely to see without asking for it, because a ladder gets posted for everyone else's benefit. Ranks 1-3 get filled kit panels at pill radius — the one high-contrast branded shape in the image. The sparkline strokes use kit.text_color and kit.muted_text_color, so a dark kit (midnight/neon) renders it light-on-dark and it still reads.
- **manga 单色降级**：Top-3 status is a FILLED pill plus parentheses around the numeral, not a gold tint. 'You' is a 3px ink tick plus full-strength ink text against muted neighbours. The two sparkline series are solid vs dashed with end-of-line text labels, never two colors. Empty ladder slots are muted text plus an empty value column.
- **替代的文本响应**：plugins/inventory/__init__.py:256-285 in full (the up-to-50-row `lines.extend` at :262-265 and :275-278, the `暂无排行数据。` at :281). The sparkline block absorbs plugins/inventory/season_render.py::render_snapshot_trend and the image reply at :311-314.

```
AutoPage(min_width=896, padding=56, background=_background(kit), child=VStack([...], gap=32))
898 x ~1150 — deliberately PORTRAIT, not the wide one_stroke leaderboard shape,
because this is one column of 13 rows, not three columns of 10.

+==========================================================================+
| /==============================\                                          |
| | 赛季排行                     |                                          |
| | Kasumi，扬帆起航 · 剩余 6 天  |   (settled season -> "最终排行榜")         |
| \==============================/                                          |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  kit.panel(radius omitted), padding=32 -> inner 722
| |  ( 1 )  彩纱                                            4,980 Pt     | |  ROW h=56, gap=18 -> 10*56 + 9*18 = 722
| |  ( 2 )  有咲                                            2,530 Pt     | |  rank cell  Fixed(72), align_x="stretch", align_y="center"
| |  ( 3 )  香澄                                            2,350 Pt     | |    ranks 1-3: kit.panel(radius=22) filled, numeral 30px inverted
| |   4     沙绫                                            1,930 Pt     | |    ranks 4+ : bare numeral 30px, no panel
| |   5     日菜                                            1,720 Pt     | |  name Frame(width=Fill(), align_x="start") 23px wrap=False max_lines=1
| |   6     友希那                                          1,540 Pt     | |  value Frame(width=Fixed(140), align_x="stretch") 22px align="right"
| |   7     莉莎                                            1,210 Pt     | |  — exactly the idiom at one_stroke/render/leaderboard.py:30-67
| |   8     千圣                                              980 Pt     | |
| |   9     つぐみ                                            870 Pt     | |  empty slot -> "  n   --" with muted color and an EMPTY value string
| |  10     兰                                                760 Pt     | |     (two signals, per leaderboard.py:22-29)
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  YOUR NEIGHBOURHOOD — only rendered when the player is outside the top 10
| |  你的位置                                                            | |  24px
| |  ------------------------------------------------------------------  | |
| |  16     まりな                                            410 Pt     | |  rank-1
| | |17     香澄                                              380 Pt     | |  YOU: 3px vertical tick on the left + the row drawn at
| |  18     つくし                                            350 Pt     | |       kit.text_color while neighbours are muted_text_color
| |  ------------------------------------------------------------------  | |
| |  距离第 16 名还差 30 Pt                                               | |  22px
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  THRESHOLD SPARKLINE — replaces the matplotlib chart of /赛季趋势
| |  前 10 / 前 50 门槛                                                   | |  24px
| |         ___/‾‾\__/‾‾‾‾                    前10  760 Pt               | |  raw-PIL Component, 722x120, TWO polylines
| |    ____/                                  前50  180 Pt               | |  distinguished by SOLID vs DASHED stroke + end labels
| |  06-01                                              06-27            | |  data: SeasonRankSnapshot rows (list_snapshots)
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
|                                              | 香澄 的主题 · 霓虹街机     |
+==========================================================================+
```

### BannerCard (plugins/gacha/render/banner.py::render_banner)  `[P1/M]`
- **插件**：plugins/gacha
- **触发**：/抽卡 with no argument · /抽卡 卡池 · /抽卡 信息 (plugins/gacha/__init__.py:38-42)
- **目的**：`_format_banner_info` (plugins/gacha/__init__.py:91-112) produces a 12+ line block that lists every pool entry including the six `占位角色立绘 3-1` placeholders, and prints the probability table as one crammed slash-joined string. Rates are the thing players squint at; a table with base vs current-with-pity makes soft pity visible for the first time (the `current_rates` maths at service.py:129-141 is computed today and then flattened into one line).
- **展示数据**：banner.name, banner.season_name, banner.single_cost=120, banner.ten_cost=1200 (seasons.json:32-34), featured 6★ entries (GachaEntry.featured) with character name and rarity, base_rates (seasons.json:37-42) vs current_rates(banner, pity) (plugins/gacha/service.py:129-141), pity_count / soft_pity_start=70 / hard_pity=90 (GachaState + banner), star_sticker balance and how many ten-pulls it affords — new, not shown today
- **主题可见性**：The rate bars are the kit's ink/primary as long horizontal solids — a big flat area that shows a kit's palette cleanly. The featured lineup panel takes the BanGDreamKit `titled_panel` branch (限定六星 as the stroked title). Cost line uses the kit's separator and muted color.
- **manga 单色降级**：Rarity is the star row, not a color. The rate bars are ink-solid on outlined tracks and each is labelled with its own percentage, so the bar is decoration, not the data channel. Soft-pity divergence is marked by a ↑ glyph and a numeric delta.
- **替代的文本响应**：plugins/gacha/__init__.py:38-42 and `_format_banner_info` at :91-112 in full, including the pool dump loop at :109-111.

```
AutoPage(min_width=896, padding=56, background=_background(kit), child=VStack([...], gap=32))
898 x ~1080

+==========================================================================+
| /==============================\                                          |
| | 卡池                         |                                          |
| | Kasumi，扬帆起航 限定卡池     |                                          |
| \==============================/                                          |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  FEATURED LINEUP — 2 columns
| |  限定六星                                                            | |  Grid(columns=2, column_track=Fixed(349), row_track=Fixed(190), gap=24)
| |  ------------------------------------------------------------------  | |  2*349 + 24 = 722
| |  +---------------------------+  +---------------------------+       | |
| |  | +------+                  |  | +------+                  |       | |  art 120x120 if metadata.art exists,
| |  | |立绘  |  户山香澄        |  | |立绘  |  市谷有咲        |       | |  otherwise a kit.panel placeholder with
| |  | |120² |  30px            |  | |120² |  30px            |       | |  the character name at 24px
| |  | +------+  [******] 六星   |  | +------+  [******] 六星   |       | |  StarRow 6/6 @20px + word
| |  +---------------------------+  +---------------------------+       | |
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  RATE TABLE — 4 rows h=52 gap=12
| |  出货概率                                       保底 53 抽后          | |
| |  ------------------------------------------------------------------  | |
| |  稀有度        基础            当前            [bar]                 | |  cols: rarity Fixed(140) 24px |
| |  [******]      1.00%           1.00%           |                     | |        base   Fixed(140) 22px right |
| |  [*****.]      9.00%           9.00%           [#####                | |        now    Fixed(140) 22px right |
| |  [****..]     30.00%          30.00%           [###############      | |        bar    Fill()  ink bar, width = rate
| |  [***...]     60.00%          60.00%           [############################
| +----------------------------------------------------------------------+ |  when pity >= soft_pity_start the 当前 column diverges
|                                                            gap 32        |  and gains a "↑" glyph + the delta in 22px
| +----------------------------------------------------------------------+ |
| |  保底计数                                             53 / 90         | |  the SAME PityGauge component as the pull cards
| |  [################################.....................]              | |
| |          ^软保底 70   还有 17 抽进入软保底                             | |
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |
| |  单抽 120 张      十连 1200 张      你有 2,400 张  ·  可十连 2 次      | |  24px / 24px / 22px — the affordability line is NEW
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
|                                              | 香澄 的主题 · 霓虹街机     |
+==========================================================================+

The 8-entry pool dump at __init__.py:109-111 (which lists six placeholder
items by name) IS DROPPED. Rarity rates replace it; nobody needed to know
that 占位角色立绘 3-2 exists. If a pool ever ships real non-featured art,
it comes back as a 4-column chip grid under the rate table.
```

### PullHistoryCard (plugins/gacha/render/history.py::render_history)  `[P2/M]`
- **插件**：plugins/gacha
- **触发**：/抽卡 记录 · /抽卡 历史 (plugins/gacha/__init__.py:60-65)
- **目的**：Today history is paginated 10 rows at a time (`get_history`, plugins/gacha/service.py:113-126) and each row prints internal fields: `#{row.id} {row.banner_key} 稀有度 {n} {name}（{raw message}）` (:138-140). Pagination exists only because text lines are expensive. A card fits 30 pulls as a dot strip plus every 6★ ever pulled, so the pagination command disappears.
- **展示数据**：GachaState.total_pulls and pity_count (plugins/gacha/service.py:68-80), count of rarity-6 pulls and the mean gap between them (derived from GachaPull.pity_before), every rarity-6 GachaPull with its lifetime pull index and item name resolved via inventory.get_item, the last 30 GachaPull rows as rarity numerals, newest first
- **主题可见性**：Thirty small kit panels in a 10-wide grid: the corner-radius signature at maximum repetition. Nothing else in the cluster shows a kit's small-panel treatment this densely.
- **manga 单色降级**：Rarity in the strip is a numeral, full stop — no fill, no hue. 6★ additionally gets a heavier border and a larger numeral. The 6★ roll call is a text list. Fully monochrome-native.
- **替代的文本响应**：plugins/gacha/__init__.py:60-65 and `_format_history` at :125-143 in full, including the `#{id} {banner_key}` internal-field leak at :138-140 and the page counter at :127.

```
AutoPage(min_width=896, padding=56, background=_background(kit), child=VStack([...], gap=32))
898 x ~900

+==========================================================================+
| /==============================\                                          |
| | 抽卡记录                     |                                          |
| | 香澄 · 累计 137 抽           |                                          |
| \==============================/                                          |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  LIFETIME STRIP — Grid(columns=4, column_track=Fixed(167), row_track=Fixed(88), gap=18)
| |  +------------+ +------------+ +------------+ +------------+          | |  4*167 + 3*18 = 722
| |  | 累计抽数   | | 六星       | | 平均间隔   | | 当前保底   |          | |  label 22px muted / value 40px
| |  |   137      | |    2       | |   68 抽    | |  53 / 90   |          | |
| |  +------------+ +------------+ +------------+ +------------+          | |
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  SIX-STAR ROLL CALL — every 6★ ever, no pagination
| |  六星记录                                                            | |
| |  ------------------------------------------------------------------  | |
| |  +--------------------------------+ +------------------------------+ | |  Grid(columns=2, column_track=Fixed(349), row_track=Fixed(72), gap=24)
| |  | 户山香澄 扬帆立绘   第 72 抽   | | 市谷有咲 扬帆立绘  第 131 抽 | | |  name 22px wrap=False ellipsis + index 22px right
| |  +--------------------------------+ +------------------------------+ | |  empty -> one muted row "还没有六星记录"
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  RECENT 30 — the pagination killer
| |  最近 30 抽                                          新 → 旧          | |
| |  ------------------------------------------------------------------  | |
| |  [6] [3] [3] [4] [3] [5] [3] [3] [4] [3]                             | |  Grid(columns=10, rows=3,
| |  [3] [4] [3] [3] [5] [3] [4] [3] [3] [3]                             | |       column_track=Fixed(64), row_track=Fixed(64), gap=10)
| |  [3] [3] [4] [3] [3] [3] [3] [4] [3] [3]                             | |  10*64 + 9*10 = 730 (fits 722 inner at gap=9)
| |                                                                      | |  cell = kit.panel(radius=12) with the rarity numeral at 30px
| |  6★ cell: heavy 3px ink border + numeral at 40px                      | |  centered; 6★ cells get a 3px border and a bigger numeral
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
|                                              | 香澄 的主题 · 霓虹街机     |
+==========================================================================+

NEEDS A SERVICE ADDITION: gacha/service.py currently only exposes the paged
`get_history`. Add `list_recent_pulls(user_id, limit=30)` and
`list_six_star_pulls(user_id)` — both trivial variants of the existing
GachaPull query at service.py:116-125.
```

### InventoryCard (plugins/inventory/render/inventory.py::render_inventory)  `[P2/M]`
- **插件**：plugins/inventory
- **触发**：/仓库 · /背包 · /inventory (plugins/inventory/__init__.py:68-108)
- **目的**：Today `/仓库` takes a category argument validated against a 9-key map (:76-90), and prints one `- {display_item_amount} [{scope}]` line per row (:99-103). One card holds every category at once, which makes the category argument — and its error message — unnecessary.
- **展示数据**：all UserItem rows via list_inventory(user_id) grouped by Item.category (currency / cosmetic / item), CurrencyItem.unit_name and the scope label from display_scope (plugins/inventory/service.py:391-400) — season Pt shows its season name, off-season Pt shows 休赛期临时 Pt, cosmetic counts per cosmetic_type plus owned/total against the catalog, item chips with quantity
- **主题可见性**：Three big numerals in kit panels at the top, then two more kit panels — a clean, uncluttered showcase of the kit's panel fill and radius. Low information density is the point: this card is where a kit's background treatment is most visible because there is the most empty surface.
- **manga 单色降级**：All values are numerals and unit words. Scope is a text label. Nothing encoded by fill.
- **替代的文本响应**：plugins/inventory/__init__.py:99-108 (the `仓库：` header and per-row loop), :94-97 (`仓库里还没有对应物品。` — becomes an in-card empty row), and :86-90 (the category-argument error, which the command no longer needs).

```
AutoPage(min_width=896, padding=56, background=_background(kit), child=VStack([...], gap=32))
898 x ~880

+==========================================================================+
| /==============================\                                          |
| | 仓库                         |                                          |
| | 香澄                         |                                          |
| \==============================/                                          |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  CURRENCY — the three balances get numeral treatment
| |  +----------------+ +----------------+ +----------------+             | |  Grid(columns=3, column_track=Fixed(224), row_track=Fixed(118), gap=24)
| |  | 赛季积分       | | 星星贴纸       | | 盆栽           |             | |  label 22px muted
| |  |  2,350         | |  2,400         | |   480          |             | |  value 40px
| |  |  Pt            | |  张            | |   盆           |             | |  unit  22px muted (CurrencyItem.unit_name)
| |  |  Kasumi，扬帆… | |  永久          | |  永久          |             | |  scope 22px muted (display_scope, service.py:391-400)
| |  +----------------+ +----------------+ +----------------+             | |
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  COSMETICS — count + a link, not a full list
| |  装扮                                                    12 / 25      | |
| |  ------------------------------------------------------------------  | |
| |  头像框 4   ·   称号 3   ·   主题 3   ·   立绘 2                      | |  24px, per-slot owned counts
| |                                                    详情 → /装扮       | |  22px muted pointer to WardrobeCard
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  ITEMS — chip grid
| |  道具                                                                | |
| |  ------------------------------------------------------------------  | |
| |  +---------------------+ +---------------------+ +------------------+ | |  Grid(columns=3, column_track=Fixed(230),
| |  | 体力药水      x3    | | 改名卡        x1    | | 复活币      x2   | | |       row_track=Fixed(76), gap=16)
| |  +---------------------+ +---------------------+ +------------------+ | |  name 22px wrap=False ellipsis + qty 24px right
| |                                                                      | |  empty -> one muted row "还没有道具"
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
|                                              | 香澄 的主题 · 霓虹街机     |
+==========================================================================+

The cosmetics section deliberately does NOT list items — it delegates to
/装扮. This is what keeps the inventory card one screen tall no matter how
many cosmetics a whale owns, and it is why the category argument can die.
```

### SeasonPassportCard (plugins/inventory/render/passport.py::render_passport)  `[P2/M]`
- **插件**：plugins/inventory
- **触发**：/赛季历史 (plugins/inventory/__init__.py:322-365)
- **目的**：Today this prints `- {season}: 第 {rank} 名，{pts} Pt` for up to 5 seasons, with a raw inline SQLAlchemy query in the handler (:338-354). `SeasonRanking.reward_summary_json` is written at season_service.py:309 and READ BY NOTHING (verified by grep) — so what a player actually earned in each season is stored and never shown. The passport is the long-term status object: what you won, season by season.
- **展示数据**：the last 5 Season rows (the query currently inlined at plugins/inventory/__init__.py:338-345 — move it into season_service as list_recent_seasons), per-season SeasonRanking.rank and final_points (:346-354), per-season earned rewards decoded from SeasonRanking.reward_summary_json['items'] — currently dead data, best-ever rank and seasons-participated count for the header subtitle
- **主题可见性**：A vertical stack of rank badges is a strong kit-silhouette repetition (radius 36 rounds differently against each kit's panel fill), and the reward chips reuse the wardrobe chip shape so the two cards read as one family. The header subtitle carries the brag ('最佳 第 3 名') at the kit's largest header size.
- **manga 单色降级**：Rank is a numeral in a badge that is FILLED for top 3 and OUTLINED otherwise. Non-participation is a '--' badge plus muted text plus an empty value column plus no chips. Reward chips are words.
- **替代的文本响应**：plugins/inventory/__init__.py:333-365 in full (the `赛季历史：` header, the per-season `- {name}: 第 {rank} 名，{pts} Pt` loop at :356-360, and the `暂无个人结算记录` fallback at :360).

```
AutoPage(min_width=896, padding=56, background=_background(kit), child=VStack([...], gap=32))
898 x ~900 (5 seasons)

+==========================================================================+
| /==============================\                                          |
| | 赛季历史                     |                                          |
| | 香澄 · 参与 3 季 · 最佳 第 3 名|                                         |
| \==============================/                                          |
|                                                            gap 32        |
| +----------------------------------------------------------------------+ |  ONE PANEL, one row per season, h=112, gap=18
| |  +--------+                                                          | |
| |  |   3    |  Kasumi，扬帆起航                          2,350 Pt      | |  rank badge = kit.panel(radius=36) Fixed(72x72),
| |  |  第 名 |  24px                                      24px right     | |    numeral 40px; top-3 badge is FILLED, 4+ is outlined
| |  +--------+  +------------+ +--------------+ +-----------+           | |  reward chips from reward_summary_json items[],
| |              | 扬帆领奖台 | | 前三头像框    | | 扬帆主题  |          | |    item_id -> Item.name, 22px, kit.panel(radius=14)
| |              +------------+ +--------------+ +-----------+           | |    overflow -> "+2" chip
| |  ------------------------------------------------------------------  | |  kit.separator() between seasons
| |  +--------+                                                          | |
| |  |   11   |  第零赛季 试航                              1,120 Pt     | |
| |  |  第 名 |                                                          | |
| |  +--------+  +------------+                                          | |
| |              | 扬帆同航   |                                          | |
| |              +------------+                                          | |
| |  ------------------------------------------------------------------  | |
| |  +--------+                                                          | |
| |  |   --   |  预备赛季                                   未参与        | |  no SeasonRanking row -> muted badge "--",
| |  +--------+                                             22px muted   | |  muted name, empty value, no chips (three signals)
| +----------------------------------------------------------------------+ |
|                                                            gap 32        |
|                                              | 香澄 的主题 · 霓虹街机     |
+==========================================================================+
```

---

## 交互改动

### plugins/inventory
- **现在**：`/装扮 装备 theme_s1_sailing` -> the text `已装备 theme_s1_sailing 到 theme。` (plugins/inventory/__init__.py:142-147). The player must then run another command to see any effect, and must have copied an internal item_id out of the list at :132.
- **改为**：`/装扮 霓虹街机` (bare name or alias, no `装备` verb, no item_id) -> resolves the name to a slot, equips it, and replies with the PlayerInfoCard ALREADY RENDERED WEARING IT. For a theme change specifically, the card is rendered in the newly-equipped kit, so the confirmation IS the demo.
- **为什么更好**：This is the brief's 'multi-step confirmation becomes one card with the outcome already shown'. It removes a message, removes the item_id from the player-facing vocabulary, and removes the `/装扮 装备 X` -> `/资料` two-step. It also makes equipping self-verifying: if the theme is broken the player sees it immediately rather than being told 'success'. Name resolution mirrors `theme_by_token` from the theming foundation, extended to all four cosmetic slots (the slot itself is derivable from CosmeticItem.cosmetic_type, so the user never names a slot).
- **移除命令**：/装扮 装备 <item_id> (kept as a hidden alias for one release, then dropped)
- **新增命令**：/装扮 <名字|别名>

### plugins/inventory
- **现在**：There is no way to look at another player. `/资料` is self-only and prints your own bio (plugins/inventory/__init__.py:373-386).
- **改为**：`/我 @某人` (or `/资料 @某人`) renders that player's PlayerInfoCard **in THEIR equipped theme**, not the caller's — `kit_for_user(target_id)`, not `kit_for_user(event.get_user_id())`. The signature footer switches to the shared-surface wording `香澄 的主题 · 霓虹街机`.
- **为什么更好**：This is the literal mechanic the product goal describes. An onlooker sees a sick theme in a group chat, wants to know what it is, and the bot answers with one command — and the answer is another instance of the theme, which propagates it further. It is the only interaction in the cluster where a theme is deliberately shown to a non-owner by a non-owner. It also gives the signature line something to point at: the name it prints is exactly the token `/主题 <name>` accepts.
- **新增命令**：/我 @user · /资料 @user

### plugins/gacha
- **现在**：`/抽卡 记录 2` — paginated, 10 rows per page, `抽卡记录 第 2/14 页，共 137 条` (plugins/gacha/__init__.py:60-65, service.py:113-126).
- **改为**：`/抽卡 记录` with no argument -> one PullHistoryCard: lifetime stats + EVERY 6★ ever pulled + the last 30 pulls as a dot strip. The `<页码>` argument is deleted and `get_history`/`HistoryPage` stop being player-facing (keep them for tests).
- **为什么更好**：Pagination in this bot is a workaround for text being one-dimensional. 30 pulls as a 10x3 grid of rarity numerals is denser AND more scannable than 3 pages of 10 lines, and the '六星记录' section answers the only question anyone asks of a pull history ('how many and when') without any paging at all. Deleting the argument also deletes an int-parse crash path (`int(parts[1])` at :61 is unguarded — `/抽卡 记录 abc` raises ValueError today and lands in the generic `抽卡失败：{e}` handler at :75-78).

### plugins/inventory
- **现在**：`/仓库 装扮` — a category argument validated against a 9-entry map, with a dedicated error message `仓库分类可用：全部 / 货币 / 装扮 / 道具` (plugins/inventory/__init__.py:76-90).
- **改为**：`/仓库` with no argument -> one InventoryCard showing all three categories; the cosmetics section is a per-slot count that links to `/装扮` rather than a list. The category argument and its error branch are deleted.
- **为什么更好**：The argument existed to keep a text dump short. A card holds all three categories in one screen, so filtering is pointless. Deleting it removes a response site, an error message, and a nine-key alias table that had to be kept in sync with nothing.

### plugins/gacha
- **现在**：Every pull result has the same shape regardless of outcome — 12 identical text lines whether you hit a 6★ or ten 3★s (plugins/gacha/__init__.py:115-122). The only signal of a good pull is the digit `6` appearing somewhere in the list.
- **改为**：The ten-pull card's COMPOSITION changes with the outcome: max rarity 6 -> a 300px hero band with a 限定 ribbon and the bonus frame/theme chips; max rarity 5 -> a quiet 180px band; max rarity <=4 -> no hero band at all, and the pity gauge is promoted to the top of the card at 40px with `距离保底还有 37 抽`.
- **为什么更好**：Two things at once. (1) A good pull becomes physically shaped like a good pull, which is what makes it worth screenshotting into a group — the shape carries the news before anyone reads a character name. (2) A bad pull stops being a wall of nothing and instead answers the only question a player has after ten misses: how close am I? The pity numbers already exist (`GachaResult.pity_after`, banner.soft_pity_start=70, hard_pity=90) and are currently rendered as one bare integer at :121.

### plugins/inventory
- **现在**：`/赛季排行` prints up to 50 rows of `{n}. {nickname}: {pts} Pt` into the chat (plugins/inventory/__init__.py:260-278).
- **改为**：One SeasonLadderCard: top 10 at readable size + a pinned three-row 'your neighbourhood' band + the Pt gap to the next rank up. Ranks 11-50 are no longer enumerated for anyone.
- **为什么更好**：Fifty rows is not a leaderboard, it is a database dump wearing a leaderboard's name; nobody reads rank 37 and everyone below rank 10 currently has to eye-scan for their own nickname. The neighbourhood band gives every player their own personal stake in the image, and `距离第 16 名还差 30 Pt` turns a passive ranking into an actionable target. This also stops a 50-line message from flooding a group chat every time someone is curious.

### plugins/inventory
- **现在**：The five-tier reward ladder in seasons.json:104-157 (titles, frames, the 扬帆主题 theme, sticker counts) is shown to a player exactly once — inside the settlement mail body composed at plugins/inventory/season_service.py:445-452, i.e. AFTER the season is over and the outcome is fixed.
- **改为**：The SeasonStatusCard renders the whole ladder while the season is running, with the player's current tier marked by a filled row and the words 你在这, plus the Pt gap to the tier above.
- **为什么更好**：This is data that already exists, is already validated at sync time (`_validate_reward_items`, season_service.py:537-568), and has zero player-facing surface. Showing it mid-season converts the ranking from an abstract number into a visible ladder with named prizes on each rung — and the top two rungs award a theme (`theme_s1_sailing`), which is the exact object the whole cluster is trying to make desirable. Not an image trick: an image just makes a five-row ladder cheap to show.

### plugins/gacha
- **现在**：`GrantResult.message` machine strings are printed verbatim to players: `- 稀有度 6 户山香澄 扬帆立绘（already_owned_compensated:120）` (plugins/gacha/__init__.py:118, message values produced at plugins/inventory/service.py:171-178). The gacha history does the same with `GachaPull.message` at :137.
- **改为**：The message is parsed in the render layer into card affordances: `''` -> a `NEW` tag; `already_owned` -> no tag; `already_owned_compensated:{n}` -> a `+{n}盆` tag; `done` (idempotent replay) -> no tag. For a featured 6★, the semicolon-joined multi-grant string built at gacha/service.py:164-166 becomes the 同时获得 chip row naming the frame and theme by their Item.name.
- **为什么更好**：Not a medium change — a correctness change that the card forces. Players are currently reading an internal enum. The duplicate-compensation economy (12/60/120 盆栽, service.py:34-54) is the entire justification for the 盆栽 currency and it is presently communicated as a colon-delimited debug token. Making it a visible tag on the exact tile that produced it is the first time a player can see where their 盆栽 came from.

### plugins/inventory
- **现在**：`/资料` returns only `个人简介：\n{description}` (plugins/inventory/__init__.py:381-386). Level and XP live in `monetary`, Pt and rank in `inventory.season_service`, stickers and 盆栽 in `inventory.service`, cosmetics in `equipped_items` — four sources, no single command shows them together. The UPDATE.md plan (§6) already specifies `/个人信息` as an image; it was never built.
- **改为**：`/资料` (and new aliases `/我`, `/profile`) becomes the PlayerInfoCard: avatar + frame + title + nickname + level + Pt + rank + stickers + 盆栽 + collection + pity + season progress + bio, in one card. `/资料 简介 <text>` keeps its existing text behaviour.
- **为什么更好**：The profile is the object a player identifies with, and it is currently the thinnest response in the plugin. Merging makes one command worth running, gives the theme its best canvas, and — crucially — gives the equip flow somewhere to land (see the equip-confirmation change above). It also implements `BaseKit.player_card`, which is declared and raises NotImplementedError at plugins/render/kit.py:182 and is listed under 'Implement now' in docs/design/season-gacha-cosmetics.md:410.

### plugins/inventory
- **现在**：`/赛季趋势` returns a raw matplotlib PNG (plugins/inventory/season_render.py:25-64) — white figure, default matplotlib palette, English axis labels `Rank 10` / `Pt`, `figsize=(9,5)` landscape. It ignores the kit entirely.
- **改为**：The threshold trend becomes a kit-rendered sparkline panel inside the SeasonLadderCard (two polylines, solid vs dashed, end-labelled). `/赛季趋势` is kept as a deprecated alias that returns the ladder card.
- **为什么更好**：This is the single most theme-breaking image in the bot: a player with the 霓虹街机 theme running `/赛季趋势` gets a white matplotlib chart with a blue/orange default cycle. Every other image in the cluster says 'this is my theme' and this one says 'this is matplotlib'. Folding it in also removes a command whose entire content is two numbers over time — which is a 120px strip, not a 900px figure. Honest cost: this is a real rewrite (raw-PIL `Component` per house style §12, with `ctx.scale_px` on every literal), so it is P1-inside-a-P1 card, not free.
- **移除命令**：/赛季趋势 (kept as a deprecated alias to /赛季排行)

---

## 保留为文本
- **plugins/gacha** — `星星贴纸不足，需要 1200 张` — raised at plugins/gacha/service.py:104 and surfaced by the generic handler at plugins/gacha/__init__.py:75-78.：A refusal must be instant. The whole message is one number; an image adds a 0.1s render plus an upload for zero information. It is also the highest-frequency failure in the plugin — a player at 800 stickers will hit it repeatedly.
- **plugins/gacha** — `用法：/gacha info /gacha pull /gacha pull 10 /gacha history <页码>` (plugins/gacha/__init__.py:67-71) and `只能单抽或十连` (:88). Both need updating for the new command shape, but stay text.：Usage strings are read once, are copy-pasteable as text and not as an image, and are exactly the response a confused player needs fastest.
- **plugins/gacha** — `抽卡失败：{e}` (plugins/gacha/__init__.py:75-78), including `当前没有开放的限定卡池` (service.py:89) and the config-validation failures from `_validate_banner_rewards` (:253-284).：These are error paths, some of them operator-facing config errors. Rendering a themed card around `卡池奖励配置缺失：standing_art_x` would be absurd. Note the strings themselves should be split — the config errors should log rather than reach a player — but the medium stays text.
- **plugins/inventory** — `/资料 简介 <text>` results: the validation errors from `validate_profile_description` (`个人简介最多 180 个字符` / `个人简介只能使用常见中日英文字…`, plugins/inventory/service.py:365-367, surfaced at __init__.py:394-397) and the success ack `已更新个人简介。` (:398-401).：Validation feedback must be instant and precise; the player is mid-edit and will retype immediately. The success ack is arguable — one could return the refreshed PlayerInfoCard — but a bio edit is often several attempts in a row, and rendering a full card per keystroke-fix is a latency tax on the one flow that is pure text input. If it ever becomes a card, it should be rate-limited to the last edit.
- **plugins/inventory** — `用法：/资料 或 /资料 简介 <180字以内文本>` (:403-406) and `用法：装扮 / 装扮 装备 <item_id> / 装扮 卸下 <…>` (:157-161).：Usage help. Same reasoning as the gacha usage string.
- **plugins/inventory** — `装扮操作失败：{e}` (:164-168), which today surfaces raw English service errors (`item is not cosmetic`, `cosmetic not owned`, `unknown cosmetic slot` from service.py:298/300/417).：Error path. It should be given Chinese messages and, per the theming foundation's rule, an actionable pointer (`你还没有这个装扮，看看 /装扮`) — but as text. Rendering a card to say 'no' is the anti-pattern.
- **plugins/inventory** — `/装扮 卸下 <slot>` -> `已卸下装扮。` / `这个位置没有装备装扮。` (:149-155).：Symmetry with the theming foundation's rule about `/主题 卸下`: rendering a card in the cosmetic the player just removed is confusing, and rendering it in the fallback theme reads as a downgrade notification. Text is honest and fast. (Exception worth considering later: unequipping a *frame* or *title* could return the refreshed PlayerInfoCard, since the theme is unchanged — but not for the theme slot.)
- **plugins/inventory** — All superuser/admin surfaces: the silent finishes at :185, :203 and :423; `未知赛季。` (:206-209, :430-433); `已结算 {name}，记录 {n} 名玩家。` (:211-214, :435-438); the grant-character result dump `已发放六星角色奖励：\n{item_id}: {msg}` (:186-199); and `用法：/season-admin settle <season_key>` (:440-443).：Operator tooling. item_ids and raw grant messages are the correct output here — an admin needs the internal identifier, not a themed presentation of it. Zero onlooker value, and admin commands should not pay a render cost.
- **plugins/inventory** — Hard empty states that precede any data: `还没有赛季记录。` (:269-272), `还没有赛季趋势数据。` (:298-301), `还没有足够的赛季趋势快照。` (:306-309), `还没有赛季历史。` (:328-331).：These fire before the season system has produced anything — typically on a fresh deployment or a fresh install. A themed card that says 'there is nothing' costs a render to communicate an absence. Contrast with the *partial* empty states (an empty ladder slot, an empty wardrobe slot, zero 6★ pulls), which DO belong inside their card as muted rows, because there the surrounding structure is the information.
- **plugins/gacha, plugins/inventory** — The PassiveGenerator element and `referrer=` on every reply.：Not a design choice — a call-site convention that must be preserved verbatim when the medium changes. Every new call site becomes `await cmd.finish(image_segment(img) + pg.element, referrer=pg.event.referrer)`, with the image segment FIRST, matching plugins/one_stroke/__init__.py:94-98.

---

## 风险
- NO ART ASSETS EXIST. `resources/` at the repo root is empty, and items.json carries no image paths for any of the 12 cosmetic items — `frame_default`, `frame_s1_champion`, `standing_art_s1_kasumi` etc. are names and rarities only. Every card above is therefore designed to be complete with zero art: frames render as a text pill, standing art renders as a named kit.panel placeholder. This is the right fallback, but it means the ten-pull hero band and the banner lineup — the two most 'gacha-looking' surfaces — will look like typography until art ships. Plan the `metadata.art` path key and the placeholder branch together, or the first art drop will need a layout change.
- `BaseKit.player_card` raises NotImplementedError for all eight kits (plugins/render/kit.py:182) and the ABC docstring says each kit 'should override this with their own composition'. Shipping eight bespoke player cards is the single biggest cost in this cluster. Recommended discipline: `utils/cards.py::player_card(kit, ...)` checks `type(kit).player_card is not BaseKit.player_card` (an explicit identity test, NOT the `hasattr` probe banned by house style §9) and falls back to a five-atom composition of the same 722x240 box. Implement bespoke versions for bangdream, neon and manga first — the three most visually distinct — and let the other five ride the fallback. Do not let the fallback be the excuse to never write the other five: the fallback looking fine in all eight is exactly how a theme system dies.
- The `player_card` signature in the design doc (docs/design/season-gacha-cosmetics.md:280-293, mirrored at kit.py:162-175) takes `title1_image` and `title2_image`, but `EquippedItem` has a UNIQUE(user_id, slot) constraint (plugins/inventory/models.py:101), so a player can equip exactly ONE title, and no title art exists anyway. The signature cannot be satisfied as written. Resolution: render titles as text pills from `Item.name`, keep the image parameters in the signature as `None` for a future asset drop, and either add a `title_texts: tuple[str, ...]` parameter or accept that the two image slots stay unused. Decide before implementing, or every kit will invent its own answer.
- Avatar fetching is a NETWORK CALL with no cache: `get_group_member_head` opens a fresh aiohttp ClientSession per call (plugins/bang_avatar/utils.py:96-104). Putting it on the PlayerInfoCard path means every `/我` does an uncached HTTP round trip to q.qlogo.cn. Two rules follow: (1) fetch on the event-loop thread in the handler and pass the result into the renderer — never inside `render`, same discipline as `kit_for_user`; (2) cache avatars TO DISK by user_id, because `atoms.py:416-421` re-copies a live `Image.Image` source on every render and only `Path` sources hit `ctx.image_cache`. Without the disk cache, the highest-value card is also the slowest and the only one that can fail on a network hiccup.
- Time budget. Measured house baseline is 0.03-0.13s for a two-panel 898x987 page, and the PlayerInfoCard has five panels plus an avatar composite while the ten-pull has fourteen. Expect 0.15-0.30s on bangdream and sakura/neon. That is over the ~0.15s per-message guideline. Mitigations, in order: use `await page.render_async()` everywhere (all these handlers are async); do not use `kit.background(source=...)` on these cards — the BanG Dream! image treatment costs 0.25s vs 0.08s for the tiled pattern; and never call `random.choice(list(BG_DIR.glob(...)))` per render (the un-cached directory scan copied from one_stroke/render/graph.py:338-345).
- `get_current_season()` calls `sync_seasons_config()` on EVERY invocation (plugins/inventory/season_service.py:95), which re-reads seasons.json from disk, re-validates every reward item id against the items table (`_validate_reward_items`, :537-568), rewrites five Season columns and commits. Several of the new cards need season data, and `gacha.get_current_banner()` (service.py:59-65) triggers it too — so a ten-pull card could fire this several times per message. Resolve the season ONCE per handler and thread it into the renderer, exactly as the theming foundation resolves the kit once. Do not let a render-time helper reach for `get_current_season()`.
- The 10-wide history grid at `column_track=Fixed(64), gap=10` measures 730 against a 722 inner width and will overflow. Use `gap=9` (730-9=721) or `Fixed(63)` — and more generally, EVERY grid track total in this design must be re-measured against the real inner width after padding, because `AutoPage(min_width=896)` does not bind (the mines page measures 898 from `Fixed(786) + 2*56`, per house style §3). Treat the pixel arithmetic in these mockups as intent, not as verified geometry.
- `VStack` defaults to `align="stretch"` and a stretched child gets `child_w = rect.width` regardless of its own `Fixed` width (layout.py:869, KitPanel paints what it is given at atoms.py:235-247). This is the exact bug that makes the existing `_title_bar` a compact pill on bangdream and a full-width bar on the other seven kits. Every header in this cluster must go through `utils.cards.response_card` with `Frame(header, align_x="start")`, and no renderer here may copy a fourth `_title_bar`. If eight of these cards ship with inconsistent header widths across kits, the 'same layout, only the theme differs' comparison property — which is what makes a theme legible to an onlooker — is dead on arrival.
- Scope honesty: this is ten new cards, one new kit component implemented up to eight times, one raw-PIL sparkline, one raw-PIL star-row component, one shared pity-gauge component, plus service additions in two plugins (`list_recent_pulls` / `list_six_star_pulls` in gacha, `list_recent_seasons` and a rank-neighbour query in inventory). If only three things ship, ship PlayerInfoCard, TenPullRevealCard and the `/我 @someone` cross-theme view — those three carry the entire 'where did you get that sick theme' loop, and everything else is polish on top of a loop that already works.
- Every one of these cards must be rendered in all eight kits before shipping (house checklist §15.10), and the two that matter most are manga (is any state still readable with color removed?) and fluent (does an 8px radius plus a 178-alpha panel fill still separate from the background at these panel densities?). The wardrobe and pull-history cards stack 12-30 panels; a near-transparent fluent panel repeated 30 times may read as noise rather than as a grid. Budget a pass to tune per-card padding for the low-radius / low-alpha kits, and be prepared to pass an explicit `radius` on the small tiles only — never on the large surfaces, where the omitted radius IS the theme signature.
