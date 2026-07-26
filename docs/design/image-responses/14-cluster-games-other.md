# 插件簇：games-other

涉及插件：plugins/one_stroke, plugins/cck, plugins/guess_chart

卡片 11 张 · 交互改动 12 项 · 保留文本 11 项

---

## 卡片设计

### OneStrokeBoardCard (extends existing render() in plugins/one_stroke/render/graph.py:404)  `[P0/M]`
- **插件**：plugins/one_stroke
- **触发**：/一笔画 [简单|普通|困难] — every in-round board post (start, reset, progress, failed step)
- **目的**：The single surface a player stares at for a whole round. Absorbs all four in-round text payloads into the image so a move produces exactly one message, and adds a decay meter that text literally cannot express.
- **展示数据**：difficulty label (session.difficulty_name), drawn_count / total_edges (session.py:44,40), live reward vs base reward, as both a meter and a numeral (apply_time_decay, graph.py:405), the board itself (OneStrokeBoard, graph.py:168), permanent WASD/R/Q control legend (replaces Messages.PROMPT), conditional failed-step reason (Messages.MOVE_FAIL_*, messages.py:22-24)
- **主题可见性**：Highest-frequency surface in the cluster — a player sees it 5-15 times per round. The kit owns the page background, the 786 board panel's corner radius (48 bangdream vs 8 fluent vs 14 manga — an unmistakable silhouette difference at this size), the header treatment (BD gets its two-band pill, others get a flat two-tier header), and the legend strip's separator style. The hard-coded board palette stays theme-invariant so the game reads identically in all eight kits while the frame around it does not.
- **manga 单色降级**：The board's five state colors are already glyph/shape-redundant (S label on start, circles for nodes vs rounded squares for walls, drawn ring on current node — graph.py:243-275); nothing new is added. The reward meter is a filled rounded rect inside an outlined one plus the literal "14 / 18 Pt" numeral, so fill-vs-outline carries it with the number as backup. The fail row is prefixed with a warning glyph and the full sentence. Zero hue dependency.
- **替代的文本响应**：plugins/one_stroke/__init__.py:136-147 (START + difficulty + reward + PROMPT), :172-177 (RESET + PROMPT), :274-289 (PROGRESS + PROMPT + optional fail_text). Three send sites collapse to one card call. Messages.START, Messages.PROMPT, Messages.RESET, Messages.PROGRESS, Messages.MOVE_FAIL_* (messages.py:14-24) all become card fields.

```
AutoPage(min_width=896, padding=56, background=_background(kit))    -> 898 x ~1237

 +--------------------------------------------------------------+
 | 56                                                        56 |
 |    /=============================================\            |  BD branch: kit.title_pill(
 |    | 一笔画                                       |  548x127   |    "一笔画", "普通 · 12/20 · 14 Pt",
 |    | 普通 · 12/20 · 14 Pt                         |            |    pill_width=560, pill_height=57)
 |    \=============================================/            |  other 7 kits: utils.cards header
 |                          gap 24                              |    title 30 / subtitle 24, Frame(align_x="start")
 |    +----------------------------------------------------+    |
 |    |  #### ####  ============ ####  ####                |    |  kit.panel(child, width=Fixed(786),
 |    |  #### ####  O          O ####  ####                |    |             height=Fixed(786))
 |    |             |          |                          |    |  radius OMITTED -> kit silhouette
 |    |  ####  (S)==O==========O------O   ####             |    |  child = OneStrokeBoard(session)
 |    |             |                |                    |    |  (graph.py:168, unchanged)
 |    |  #### ####  O------O    ####  O    ####            |    |
 |    +----------------------------------------------------+    |
 |                          gap 18                              |
 |    +----------------------------------------------------+    |  kit.panel(padding=Insets.only(
 |    |  奖励  [##############--------]   14 / 18 Pt       |    |    left=32,top=24,right=32,bottom=24))
 |    |         ^ Fixed(360)x28 meter, filled 14/18        |    |  label 26 muted / value 30
 |    |  --------------------------------------------------|    |  kit.separator()
 |    |  W A S D 移动     R 重置     Q 放弃                 |    |  font 26, muted_text_color, h=44
 |    |  ! 第 3 步：这条线段已经走过了                       |    |  CONDITIONAL row, font 24, h=40
 |    +----------------------------------------------------+    |
 | 56                                                        56 |
 +--------------------------------------------------------------+

Header subtitle is the only mutable string; title stays the fixed noun "一笔画"
(same split as the three existing _title_bar call sites).
```

### OneStrokeVictoryCard  `[P0/M]`
- **插件**：plugins/one_stroke
- **触发**：automatic on session.is_complete (the win)
- **目的**：Collapse the 3-message win sequence into one composed card and make the reward math visible. Today the player is told '获得 28 个Pt' with no idea the 18-base got a 0.78 speed multiplier — the whole speed mechanic is invisible.
- **展示数据**：elapsed_seconds (session.elapsed_seconds()), rank in this difficulty + positions gained (new query over get_leaderboard, database.py:33), session.reward (base), the decay factor as an explicit multiplier (calculate_time_decay_factor, difficulty.py:153), birthday multiplier and the character names (get_today_birthday, __init__.py:208), final_reward and monetary.get balance, daily-task completion line (check_progress, __init__.py:253), level-up line (monetary.add_xp, __init__.py:265), theme signature with owner nickname
- **主题可见性**：This is the terminal, screenshot-worthy card — the one a player posts. It carries the theme signature (per the foundation's tier-1 rule: composed response cards get it, mid-game boards do not), so a non-starter theme is explicitly named right where onlookers are already looking at a win.
- **manga 单色降级**：Every row is label + value text; the only non-text elements are two separator weights (2px vs 4px) that mark the sub-total boundary — a thickness difference, not a hue difference. The '^ 2 位' rank delta uses an arrow glyph plus the number. The completed board is the same monochrome-safe token set as the in-round card.
- **替代的文本响应**：plugins/one_stroke/__init__.py:245-250 (board image + Messages.WIN / Messages.BIRTHDAY_WIN), :259-262 (daily task msg), :267-270 (level-up msg). Three sends -> one. Messages.WIN and Messages.BIRTHDAY_WIN (messages.py:26-31) are deleted entirely; their format fields become card rows.

```
AutoPage(min_width=896, padding=56, background=_background(kit))    -> 898 x ~1430

 +--------------------------------------------------------------+
 |    /=============================================\            |
 |    | 一笔画                                       |  548x127   |
 |    | 挑战成功 · 普通                               |            |
 |    \=============================================/            |
 |                          gap 24                              |
 |    +----------------------------------------------------+    |
 |    |          [OneStrokeBoard, 20/20 drawn]             |    |  786x786, same panel as
 |    |          the completed figure = the trophy         |    |  the in-round card so the
 |    +----------------------------------------------------+    |  before/after reads
 |                          gap 24                              |
 |    +----------------------------------------------------+    |  786 x ~310
 |    |  耗时                                    12.47 s  |    |  label 26 muted / value 34
 |    |  排名                       普通 #4    ^ 2 位      |    |  rank + delta, 26 / 30
 |    |  --------------------------------------------------|    |  kit.separator(thickness=2)
 |    |  基础奖励                                  18 Pt  |    |  26 / 26
 |    |  速度加成                                 x 0.78  |    |  26 / 26
 |    |  生日翻倍                        x 2  (香澄)      |    |  CONDITIONAL, 26 / 26
 |    |  ====================================================|    |  kit.separator(thickness=4)
 |    |  获得                                      28 Pt  |    |  30 / 44  <- the big number
 |    |  余额                                  1 204 Pt   |    |  26 / 30 muted
 |    +----------------------------------------------------+    |
 |                          gap 18                              |
 |    +----------------------------------------------------+    |  CONDITIONAL panel
 |    |  每日任务【速通高手】完成                +3 贴纸  |    |  26 / 26
 |    |  升级   Lv.12 -> Lv.13                   +5 贴纸  |    |  26 / 26
 |    +----------------------------------------------------+    |
 |                          gap 12                              |
 |                          | 香澄 的主题 · 霓虹街机           |  signature, 22 muted,
 +--------------------------------------------------------------+  right-aligned, tick rule

All label/value rows are the leaderboard idiom: Frame(label, width=Fill(), align_x="start",
align_y="center") + Frame(value align="right", width=Fixed(200), align_y="center"), gap 12.
```

### OneStrokeSolutionCard  `[P1/M]`
- **插件**：plugins/one_stroke
- **触发**：Q (give up) and the 300s waiter timeout
- **目的**：Today Q and timeout are dead ends — '已放弃本局。' / '超时未操作，本局已结束。' and you never learn the answer. The Euler-trail solver already exists in the codebase for reward scoring; reuse it to reveal the solution. Turns the worst moment of the game into its most instructive image.
- **展示数据**：verdict word (放弃 / 超时), difficulty, drawn_count/total_edges reached, the full Euler trail drawn on the board with step numbers, the WASD solution string, how far the player got before stopping
- **主题可见性**：A new surface that only exists because output became visual — the theme frames a genuinely new artifact. Carries the signature. Onlookers see a fully-solved themed puzzle diagram, which is the most 'screenshot this' object in the plugin.
- **manga 单色降级**：Step numbers are the primary encoding, drawn white-on-token exactly like the existing 'S' start label (graph.py:243). Player-progress vs remainder is drawn/traversable — two existing tokens that already differ in lightness, and the numerals disambiguate regardless. The solution string is plain text.
- **替代的文本响应**：plugins/one_stroke/__init__.py:154-157 (Messages.TIMEOUT) and :164-168 (Messages.GIVE_UP). Both strings deleted from messages.py:19-20.

```
AutoPage(min_width=896, padding=56, background=_background(kit))    -> 898 x ~1180

 +--------------------------------------------------------------+
 |    /=============================================\            |
 |    | 一笔画                                       |            |
 |    | 放弃 · 普通 · 你走到 12/20                    |            |  or "超时 · 普通 · 你走到 12/20"
 |    \=============================================/            |  verdict is a WORD, not a color
 |                          gap 24                              |
 |    +----------------------------------------------------+    |
 |    |   O--(1)--O--(2)--O          #### ####             |    |  786x786, board rendered in
 |    |   |                |                               |    |  SOLUTION mode:
 |    |  (8)             (3)         O--(4)--O             |    |   - every edge of the trail
 |    |   |                |          |                    |    |     drawn, numbered 1..N
 |    |  (S)==(9)==O==(10)=O--(5)-----O   ####             |    |   - steps 1..12 (what the
 |    |   |                                |               |    |     player actually did) keep
 |    |  (11)             ####       (6)   (7)             |    |     the "drawn" token
 |    |   |                               |                |    |   - steps 13..20 use the
 |    |   O--(12)--O--(13)--O--(14)--O----O                |    |     "traversable" token
 |    +----------------------------------------------------+    |  numeral is the primary signal
 |                          gap 18                              |
 |    +----------------------------------------------------+    |  786 x ~160
 |    |  参考解法                                          |    |  26 muted
 |    |  D S A S D W D S A A W D S D W A S D S A           |    |  34, wrap=True, max_lines=2
 |    |  --------------------------------------------------|    |
 |    |  你到第 12 步为止都是对的                           |    |  24 muted
 |    +----------------------------------------------------+    |
 |                          | 主题 · 网点纸                      |
 +--------------------------------------------------------------+

Solution string: _find_euler_trail(graph) (difficulty.py:39) -> node list -> per-step delta
-> inverse of DIRECTION_DELTAS (session.py:13-18). Guard: if len(trail)-1 != total_edges,
drop the 参考解法 panel and keep only the header + partial board.
```

### OneStrokeLeaderboardCard (rework of render_leaderboard, plugins/one_stroke/render/leaderboard.py:71)  `[P1/M]`
- **插件**：plugins/one_stroke
- **触发**：/一笔画排行榜 [简单|普通|困难|全部]
- **目的**：The current card is the one wide surface in the codebase (max_width=1500, three 360px columns, 30 rows at font 23). After a group client downscales 1500px to fit, 23px body text is ~13px — unreadable, which is exactly the failure mode the constraints warn about. Narrow to one difficulty at house portrait width, triple the row font, and pin the viewer's own row so a 17th-place player learns something.
- **展示数据**：rank 1-10 for one difficulty (get_leaderboard, database.py:33), display name via plugins.nickname.get, masked user_id fallback, best elapsed_seconds, 2dp, the viewer's own rank + time, pinned below a rule when outside the top 10, placeholder rows for an under-filled board (existing idiom, leaderboard.py:22-29)
- **主题可见性**：A pure-chrome surface: there is no game art at all, so 100% of the pixels that are not text belong to the kit — background treatment, panel fill alpha, panel radius, separator style. This is the card where the difference between sakura (44 radius, cream panel) and neon (10 radius, near-black panel) is most obvious side by side. Carries the signature.
- **manga 单色降级**：Filled vs empty rows already use the two-signal idiom from leaderboard.py:22-29 (muted color AND an emptied value column). The pinned viewer row is marked with a '>' glyph and a separator above it — position and glyph, no hue. Rank numerals do all the ordering work.
- **替代的文本响应**：No text replaced — this is an existing image surface (plugins/one_stroke/__init__.py:95-98). What changes is the geometry, the row font (23 -> 30), and the addition of a viewer row; _build_leaderboard_rows (:58) gains a viewer_id.

```
AutoPage(min_width=896, padding=56, background=kit.background())    -> 898 x ~1050

 +--------------------------------------------------------------+
 |    /=============================================\            |
 |    | 一笔画                                       |            |
 |    | 竞速排行榜 · 普通                             |            |
 |    \=============================================/            |
 |                          gap 24                              |
 |    +----------------------------------------------------+    |  786 x ~810
 |    |   1    zhaomaoniu                       6.12 s     |    |  row = Frame(HStack([
 |    |   2    Arisa                            6.88 s     |    |    Frame(rank, width=Fixed(64),
 |    |   3    香澄                              7.03 s    |    |          align_x="start"),
 |    |   4    Tae                              7.41 s     |    |    Frame(name, width=Fill(),
 |    |   5    O-Tae                            8.02 s     |    |          align_x="start"),
 |    |   6    Rimi                             8.55 s     |    |    Frame(time, width=Fixed(150),
 |    |   7    Saya                             9.10 s     |    |          align_x="stretch")
 |    |   8    1234...                         10.44 s     |    |  ], gap=12), height=Fixed(56),
 |    |   9    --                                          |    |     align_y="center")
 |    |  10    --                                          |    |  rank/name/time all font 30
 |    |  - - - - - - - - - - - - - - - - - - - - - - - - - |    |  empty rows: muted_text_color
 |    |  17  > 你                              14.60 s     |    |     AND empty value string
 |    +----------------------------------------------------+    |  kit.separator() + '>' marker
 |                          | 主题 · 云母窗                      |  on the pinned viewer row
 +--------------------------------------------------------------+

/一笔画排行榜 全部 keeps today's 3-column max_width=1500 layout unchanged.
Name fallback is the existing _mask_user_id (one_stroke/__init__.py:52).
```

### OneStrokeRulesCard  `[P2/S]`
- **插件**：plugins/one_stroke
- **触发**：/一笔画 h  (also -h, help, --help)
- **目的**：The board uses five hard-coded state colors (graph.py:208-214) that are never explained anywhere in the product. A legend is inherently spatial. Also the plugin's first-touch surface, so it is the first place a new player sees their theme.
- **展示数据**：a live demo board using the real OneStrokeBoard component, legend for all five board state tokens, WASD / R / Q key table, the three difficulty labels, the decay rule stated as a concrete half-life (DECAY_TAU_BY_SCALE, difficulty.py:16-20)
- **主题可见性**：First-touch surface. A player who has never seen a themed card in this plugin sees one before their first game. The demo board also previews exactly how the kit will frame their real board.
- **manga 单色降级**：The legend is built from the same glyphs the board uses, each paired with a Chinese word — that pairing is the point of the card, so monochrome loses nothing that is not already lost on the board itself. The key table is pure text.
- **替代的文本响应**：plugins/one_stroke/__init__.py:113-116 (Messages.HELP). messages.py:2-12 deleted.

```
AutoPage(min_width=896, padding=56, background=_background(kit))    -> 898 x ~1120

 +--------------------------------------------------------------+
 |    /=============================================\            |
 |    | 一笔画                                       |            |
 |    | 玩法                                          |            |
 |    \=============================================/            |
 |                          gap 24                              |
 |    +----------------------------------------------------+    |  Frame(OneStrokeBoard(demo),
 |    |        (S)====O----O                               |    |     width=Fixed(560),
 |    |         |     |                                    |    |     height=Fixed(560),
 |    |        ####   O====@                               |    |     aspect_ratio=1)
 |    |               |                                    |    |  demo = a fixed 3x3 graph,
 |    |         O-----O----O                               |    |  4 of 8 edges drawn, so all
 |    +----------------------------------------------------+    |  five tokens appear at once
 |                          gap 18                              |
 |    +----------------------------------------------------+    |  786 x ~440
 |    |  (S) 起点        @ 当前位置       O 还没走过       |    |  legend: shape + word,
 |    |  === 已画的线    --- 还没画的线    ### 墙          |    |  font 26, 2 rows
 |    |  --------------------------------------------------|    |
 |    |  W A S D    移动并画线（可以一次输入多步）          |    |  key col Fixed(180) font 30,
 |    |  R          回到起点                               |    |  desc Fill() font 26
 |    |  Q          放弃本局                               |    |
 |    |  --------------------------------------------------|    |
 |    |  一笔画 简单 / 普通 / 困难                          |    |  font 26
 |    |  画得越快，Pt 越多（约 14s 后奖励减半）             |    |  font 24 muted
 |    +----------------------------------------------------+    |
 +--------------------------------------------------------------+
```

### CckPuzzleCard  `[P0/M]`
- **插件**：plugins/cck
- **触发**：/猜卡面 [难度]  — the puzzle post
- **目的**：Frame the crops instead of shipping a bare concatenation. Also fixes the crop-clipping bug by letting the layout engine space the strips instead of pre-compositing them onto an undersized canvas, and puts the attempt budget on the image where everyone in the channel can see it.
- **展示数据**：the N crops as separate images (random_crop_image returns list[Image.Image] instead of a MessageSegment), difficulty name from image_cut_settings.json cut_name, crop count, per-player attempt budget (3, hard-coded at cck/__init__.py:244), how to answer / how to give up
- **主题可见性**：The widest-audience message in the plugin — every member of the channel sees it and then engages with it. The kit supplies the page background visible around and between the crops, the holding panel, the header, and the crop corner radius. Because the crops are small and irregular, the themed frame is a large fraction of the image area.
- **manga 单色降级**：The crops are photographic card art and are unaffected by the kit either way. Everything the card adds is text plus panel geometry. Nothing encodes meaning by hue. Note that MangaKit's high-contrast monochrome frame around full-color anime art is a deliberately striking look, not a degradation.
- **替代的文本响应**：plugins/cck/__init__.py:180-185 — the crop image plus the trailing '[easy]获取帮助: @Kasumi /help 猜卡面' string.

```
AutoPage(min_width=896, max_width=1500, padding=32, background=_background(kit))
crop source = cut_width*4 x cut_length*4   (draw.py:73-78 doubling becomes quadrupling)
crop display = Fixed(min(cut_width*2, 1372)) x Fixed(cut_length*2)
  -> source is exactly 2x display, so at pixel_ratio=2 the paste is 1:1 (blackjack rule,
     render.py:462-465). Zero resample loss vs today.
[easy] 3 x (300x100) -> page 898 x ~920

 +----------------------------------------------------------+
 | 32                                                    32 |
 |    /=============================================\       |
 |    | 猜卡面                                       |       |
 |    | easy · 3 片 · 每人 3 次                       |       |
 |    \=============================================/       |
 |                        gap 24                            |
 |    +------------------------------------------------+    |  kit.panel(padding=18)
 |    |  +------------------------------------------+  |    |  radius OMITTED
 |    |  | %%%%%%%%%%  crop 1  600x200  %%%%%%%%%%% |  |    |  kit.image(pil_crop,
 |    |  +------------------------------------------+  |    |    width=Fixed(600),
 |    |                    gap 12                      |    |    height=Fixed(200),
 |    |  +------------------------------------------+  |    |    radius=8)
 |    |  | %%%%%%%%%%  crop 2           %%%%%%%%%%% |  |    |
 |    |  +------------------------------------------+  |    |  VStack(crops, gap=12,
 |    |                    gap 12                      |    |         align="center")
 |    |  +------------------------------------------+  |    |
 |    |  | %%%%%%%%%%  crop 3           %%%%%%%%%%% |  |    |
 |    |  +------------------------------------------+  |    |
 |    +------------------------------------------------+    |
 |                        gap 18                            |
 |    直接发送角色名或昵称  ·  bzd 看答案                     |  font 24 muted, centered
 +----------------------------------------------------------+

The 追加线索 variant (see interaction change) re-renders this card with one extra
crop appended and the subtitle changed to "easy · 4 片 · 追加线索".
```

### CckRevealCard  `[P0/M]`
- **插件**：plugins/cck
- **触发**：win / bzd / timeout — all three round exits
- **目的**：Collapse six send sites (three exit paths x two messages each) into one card per exit, and replace the useless raw 'card_id: 1234' with the card's actual identity. Also surfaces the wrong guesses that are currently thrown away silently.
- **展示数据**：full card illustration (already loaded as pil_full_image, cck/__init__.py:167), character display name (character_data[character_id][0]), card title from __processed_data__[card_id]['prefix'] via get_value_from_list-style server pick, rarity as repeated star glyphs (__processed_data__[card_id]['rarity']), card type (__processed_data__[card_id]['type']) + card_id, winner nickname and which attempt it was (player_counts, :241-252), reward amount, birthday multiplier and final amount (:258-269), wrong guesses made during the round (currently discarded at :251-253), daily-task and level-up lines (:281-296)
- **主题可见性**：The payoff moment — the whole channel is watching. It renders in the WINNER's theme (not the starter's), so winning literally shows off your theme to everyone present, and the signature names you: '香澄 的主题 · 樱色'. That is the exact 'yo dude where'd you get that' mechanic, attached to the most attention-dense moment the plugin has.
- **manga 单色降级**：Rarity is star glyph repetition, never a color. Verdict is a word in the subtitle. Card type is a word. The illustration itself is untouched by the kit. Every value row is text. The only kit-colored elements are panel fill and separators.
- **替代的文本响应**：plugins/cck/__init__.py:204-208 + :209-212 (timeout: text + full image), :226-228 + :229-231 (bzd: text + full image), :272-274 + :275-277 (win: text + full image), :287-289 (daily task), :294-296 (level-up). Eight sends collapse to three (one per exit path).

```
AutoPage(min_width=896, padding=56, background=_background(kit))    -> 898 x ~1340

 +--------------------------------------------------------------+
 |    /=============================================\            |
 |    | 猜卡面                                       |            |  verdict word only:
 |    | 正解 · 戸山 香澄                              |            |  正解 / 时间到 / 揭晓
 |    \=============================================/            |
 |                          gap 24                              |
 |    +----------------------------------------------------+    |  kit.panel(padding=18)
 |    |  +----------------------------------------------+  |    |
 |    |  |                                              |  |    |  kit.image(full_card_art,
 |    |  |         [full card illustration]             |  |    |    width=Fixed(667),
 |    |  |              667 x 501                       |  |    |    height=Fixed(501),
 |    |  |         source 1334x1002 = display x2        |  |    |    fit="contain", radius=16)
 |    |  |                                              |  |    |  1334 is confirmed by the
 |    |  +----------------------------------------------+  |    |  [寻找记忆] cut_width=1334
 |    +----------------------------------------------------+    |  in image_cut_settings.json
 |                          gap 18                              |
 |    +----------------------------------------------------+    |  786 x ~270
 |    |  角色                                 戸山 香澄  |    |  26 muted / 30
 |    |  卡面                     はじめてのステージ      |    |  26 / 30 max_lines=1 ellipsis
 |    |  稀有度                              * * * *     |    |  glyph repetition, not hue
 |    |  卡池                       期间限定 · #1234      |    |  26 / 26
 |    |  --------------------------------------------------|    |
 |    |  答对                   zhaomaoniu · 第 1 次      |    |  26 / 34   (win only)
 |    |  奖励           5 Pt   x2 生日  ->   10 Pt        |    |  26 / 34   (win only)
 |    +----------------------------------------------------+    |
 |                          gap 12                              |
 |    +----------------------------------------------------+    |  CONDITIONAL
 |    |  也有人猜过                                        |    |  24 muted
 |    |  Arisa -> 有咲 · Tae -> たえ · Rimi -> りみ        |    |  24, wrap, max_lines=2
 |    +----------------------------------------------------+    |
 |    +----------------------------------------------------+    |  CONDITIONAL
 |    |  每日任务【一击必中】完成                +3 贴纸  |    |
 |    |  升级   Lv.12 -> Lv.13                   +5 贴纸  |    |
 |    +----------------------------------------------------+    |
 |                          | 香澄 的主题 · 樱色                 |
 +--------------------------------------------------------------+
```

### CckDifficultyGalleryCard  `[P2/M]`
- **插件**：plugins/cck
- **触发**：/猜卡面 -h
- **目的**：'可用难度：easy、normal、hard、expert、hard++、expert++、黑白木筏、高闪大图、五只小猫、超级猫猫、寻找记忆、6块床板' is twelve opaque names. The thing that actually distinguishes them is a geometry — how many strips, how big, and whether they are desaturated. Draw the geometry.
- **展示数据**：all 12 cut_name values from image_cut_settings.json, cut_counts and cut_width per difficulty, drawn to relative scale, is_black treatment as a word (黑 for 1, 亮 for 2, 灰 for 3, nothing for 0), the start command
- **主题可见性**：Pure-chrome surface (no game art), so like the leaderboard it is 100% kit. Twelve panels in a grid make the kit's corner radius and fill alpha unmistakable.
- **manga 单色降级**：The strip bars are shape-only (length and count), which is the entire encoding; the is_black flag is a word. No hue anywhere. This card is arguably clearest in manga.
- **替代的文本响应**：plugins/cck/__init__.py:106-122 (the -h help block, including the HTML-escape dance at :117-120 which becomes unnecessary once it is not a text message).

```
AutoPage(min_width=896, padding=56, background=_background(kit))    -> 898 x ~980

 +--------------------------------------------------------------+
 |    /=============================================\            |
 |    | 猜卡面                                       |            |
 |    | 12 种难度                                     |            |
 |    \=============================================/            |
 |                          gap 24                              |
 |    +----------------------------------------------------+    |  Grid(children=tiles,
 |    | +------------+ +------------+ +------------+       |    |    columns=3, rows=4,
 |    | | easy       | | normal     | | hard       |       |    |    column_track=Fixed(248),
 |    | | ========== | | ========   | | ======     |       |    |    row_track=Fixed(186),
 |    | | ========== | | ========   | | ======     |       |    |    gap=18)
 |    | | ========== | | ========   | | ======     |       |    |
 |    | | 3 片 300px | | 3 片 250px | | 3 片 200px |       |    |  each tile = kit.panel(
 |    | +------------+ +------------+ +------------+       |    |    VStack([name(26),
 |    | +------------+ +------------+ +------------+       |    |      strips, spec(22 muted)]))
 |    | | expert     | | hard++   黑| | expert++ 黑|       |    |
 |    | | =====      | | ========   | | ========   |       |    |  strips: cut_counts bars,
 |    | | =====      | | ========   | | ========   |       |    |  each Fixed(cut_width//5) x
 |    | |            | | ========   | | ========   |       |    |  Fixed(max(4,cut_length//8))
 |    | | 2 片 160px | | 4 片 250px | | 4 片 250px |       |    |  drawn as kit.separator(
 |    | +------------+ +------------+ +------------+       |    |    thickness=...) rows
 |    | +------------+ +------------+ +------------+       |    |
 |    | | 黑白木筏 黑| | 高闪大图 亮| | 五只小猫   |       |    |  is_black flag becomes a
 |    | | ========== | | ########## | | ==         |       |    |  short word: 黑 / 亮 / 灰
 |    | | ...        | | ########## | | ==  ==  == |       |    |
 |    | | 4 片 600px | | 1 片 800px | | 5 片 130px |       |    |
 |    | +------------+ +------------+ +------------+       |    |
 |    | +------------+ +------------+ +------------+       |    |
 |    | | 超级猫猫   | | 寻找记忆 灰| | 6块床板    |       |    |
 |    | | ==         | | ========== | | ========== |       |    |
 |    | | 1 片 150px | | 1 片 1334px| | 6 片 1200px|       |    |
 |    | +------------+ +------------+ +------------+       |    |
 |    +----------------------------------------------------+    |
 |    /猜卡面 <难度> 开始  ·  /猜卡面 不带参数 = 随机           |  font 24 muted
 +--------------------------------------------------------------+
```

### GuessChartPuzzleCard  `[P1/M]`
- **插件**：plugins/guess_chart
- **触发**：/猜谱面 [ez|nm|hd|ex|<等级>] — the puzzle post
- **目的**：Frame the chart and put the round's parameters (difficulty, slice count, hints remaining) on the image instead of in a trailing string. Critically: render this one at pixel_ratio=1 so the note pixels are byte-exact — a chart is game-critical art, and a 2x upsample/downsample round trip softens the note edges players read.
- **展示数据**：the chart image (bestdori render or render_to_slices, guess_chart/__init__.py:196-200), game difficulty label, slice count (3 for hd/ex, whole chart otherwise), hints remaining out of 3 (len(tips), :223-227), how to answer / how to request a hint / how to give up
- **主题可见性**：The chart is a dark rectangle; every non-chart pixel is the kit. On the light kits (sakura, minimal, fluent, manga) the contrast between the themed frame and the near-black chart is dramatic. This is also the message that starts the round, so it sets the visual register for everything that follows.
- **manga 单色降级**：MangaKit's monochrome frame around a dark chart is high-contrast and clean. Nothing on the card encodes state by hue — the difficulty and hint count are words and numerals in the header.
- **替代的文本响应**：plugins/guess_chart/__init__.py:231-236 — the chart image plus '获取帮助: @Kasumi /help 猜谱面'.

```
AutoPage(max_width=1500, padding=32, background=_background(kit))
page.render(RenderContext(pixel_ratio=1))   <- layout.py:175-177 returns the canvas
                                               untouched when pixel_ratio == 1
chart display = Fixed(chart.width) x Fixed(chart.height), 1:1 paste, no resample
[expert] render_to_slices -> ~345 x 1152     [normal] render() -> ~546 x 1500
  -> page ~612 x 1712 (BD title pill measures 548 wide, so it sets the floor)

 +--------------------------------------------+
 | 32                                      32 |
 |    /=============================\         |
 |    | 猜谱面                       |         |
 |    | expert · 3 段 · 提示 3/3     |         |
 |    \=============================/         |
 |                  gap 24                    |
 |    +--------------------------------+      |  kit.panel(padding=18)
 |    | ############################## |      |  chart bg is (16,16,16) so the
 |    | # o   o  # o    o # o   o    # |      |  panel padding is what keeps it
 |    | #  ====  #   o    #  ====    # |      |  legible on midnight/neon where
 |    | # o    o #  o  o  # o    o   # |      |  the page is also dark
 |    | #        #        #          # |      |
 |    | # slice1 # slice2 # slice3   # |      |  kit.image(chart_pil,
 |    | #        #        #          # |      |    width=Fixed(w), height=Fixed(h))
 |    | ############################## |      |
 |    +--------------------------------+      |
 |                  gap 18                    |
 |    发送曲名或昵称 · 「提示」要线索 · bzd     |  font 24 muted, centered,
 +--------------------------------------------+  wrap=False, max_lines=1

At pixel_ratio=1 the 24px caption rasterizes at 24 real px, clearing the ~22px floor.
```

### GuessChartHintBoardCard  `[P1/S]`
- **插件**：plugins/guess_chart
- **触发**：提示
- **目的**：Today a hint is a single line ('这首曲子的 BPM 是 178 哦') that scrolls away; by the third hint nobody remembers the first two. A card that redraws all three slots — revealed and locked — makes the accumulated intel one persistent scrollback anchor instead of three lost lines.
- **展示数据**：hint slot index and label (等级 / BPM / 乐队), revealed hint values (level, chart_statistics.main_bpm, band_name — :223-227), locked slots as '?' placeholders, how many hints remain, the reward penalty for the next hint, if the cost mechanic ships
- **主题可见性**：Small (620 x ~480), fast (~0.05s), and posted mid-round — a second dose of the theme between the puzzle and the reveal. Because it is small and text-dense, the kit's panel fill, radius and separator style are the entire visual identity of the card.
- **manga 单色降级**：Locked vs revealed uses the codebase's existing two-signal rule verbatim: muted_text_color AND the value replaced by '? ? ? ?'. Slot numbers are numerals. Survives monochrome completely.
- **替代的文本响应**：plugins/guess_chart/__init__.py:290-293 (the bare tip line). Also absorbs :285-288 ('没有更多提示了哦' becomes the all-locked-slots-consumed state of the card) and, if the hint-cost change ships, :279-282 ('hard 和 expert 难度没有提示哦').

```
AutoPage(min_width=620, padding=32, background=_background(kit))    -> 620 x ~480

 +----------------------------------------------+
 | 32                                        32 |
 |    /================================\        |
 |    | 猜谱面                          |        |
 |    | 情报板 · 2/3                    |        |
 |    \================================/        |
 |                    gap 24                    |
 |    +----------------------------------+      |  kit.panel(padding=Insets.only(
 |    |  (1) 等级                 LV.28  |      |    left=32,top=24,right=32,bottom=24))
 |    |  --------------------------------|      |  row h=64, label Fill() font 26
 |    |  (2) BPM                    178  |      |  value Fixed(200) align="right"
 |    |  --------------------------------|      |  font 34, text_color
 |    |  (3) 乐队               ? ? ? ?  |      |  LOCKED row: '?' glyphs AND
 |    |         发送「提示」解锁          |      |  muted_text_color -- two signals,
 |    +----------------------------------+      |  the leaderboard idiom
 |                    gap 12                    |  (leaderboard.py:22-29)
 |    再要一条提示，奖励 -20%                     |  font 24 muted, conditional
 +----------------------------------------------+
```

### GuessChartRevealCard  `[P0/M]`
- **插件**：plugins/guess_chart
- **触发**：win / bzd / 不知道 / timeout — all three round exits
- **目的**：Six sends across three exit paths become three cards. Puts the jacket, the song identity, and the reward math in one object, and finally shows the note count that :214-216 explicitly discarded because 'the information can be found in the chart image' — which it no longer needs to be.
- **展示数据**：jacket image (get_jacket_image, utils.py:383), song_name, band_name, difficulty, playLevel (:208-219), chart_statistics.main_bpm and .notes (:186; notes currently thrown away, :214-216), potential_song_number — the size of the pool the song was drawn from, which is what the reward is computed from (:317-324), hints consumed, winner nickname, reward, birthday multiplier, final amount, wrong guesses made during the round (currently only logger.debug, :382-384), daily-task and level-up lines (:356-373)
- **主题可见性**：Renders in the WINNER's theme with the signature naming them. Because the jacket is a small 320px square rather than a full-bleed illustration, the kit occupies most of the card — this is a theme showcase that happens to contain an answer. Also the only card in this plugin at the house 898 portrait width, so it reads as the plugin's 'real' surface.
- **manga 单色降级**：Verdict is a word. Difficulty is the literal 'EXPERT' string, never a hue. Every stat is a labelled numeral. The jacket art is untouched. Nothing depends on color.
- **替代的文本响应**：plugins/guess_chart/__init__.py:253-257 + :258-262 (timeout: text + jacket), :298-303 + :304-308 (bzd: text + jacket), :349-353 + :375-379 (win: text + jacket), :362-365 (daily task), :370-373 (level-up). Nine sends collapse to three.

```
AutoPage(min_width=896, padding=56, background=_background(kit))    -> 898 x ~940

 +--------------------------------------------------------------+
 |    /=============================================\            |
 |    | 猜谱面                                       |            |  正解 / 时间到 / 揭晓
 |    | 正解 · 用了 2 条提示                           |            |
 |    \=============================================/            |
 |                          gap 24                              |
 |    +----------------------------------------------------+    |  786 x 356
 |    |  +------------+                                    |    |  HStack([jacket, info],
 |    |  |            |  ときめきエクスペリエンス！        |    |         gap=24, align="start")
 |    |  |   jacket   |  ---------------------------------  |    |
 |    |  |  320 x 320 |  Poppin'Party                      |    |  jacket source 640x640
 |    |  |            |  EXPERT · LV.28                    |    |  -> Fixed(320) x Fixed(320)
 |    |  |  src 640   |  BPM 178 · 892 notes               |    |  = source/2, radius=16
 |    |  +------------+  ---------------------------------  |    |
 |    |                  候选池 271 首                      |    |  title  34, wrap, max_lines=2
 |    +----------------------------------------------------+    |  band   26 muted
 |                          gap 18                              |  diff   30
 |    +----------------------------------------------------+    |  stats  26
 |    |  答对                                zhaomaoniu   |    |  CONDITIONAL (win only)
 |    |  奖励          12 Pt   x2 生日  ->   24 Pt        |    |  26 muted / 34
 |    +----------------------------------------------------+    |
 |                          gap 12                              |
 |    +----------------------------------------------------+    |  CONDITIONAL
 |    |  有人猜过                                          |    |  24 muted
 |    |  Arisa -> 六兆年 · Tae -> Ringing Bloom            |    |  24, wrap, max_lines=2
 |    +----------------------------------------------------+    |
 |    +----------------------------------------------------+    |  CONDITIONAL
 |    |  每日任务【谱面大师】完成                +3 贴纸  |    |
 |    |  升级   Lv.12 -> Lv.13                   +5 贴纸  |    |
 |    +----------------------------------------------------+    |
 |                          | 香澄 的主题 · 深夜巡演             |
 +--------------------------------------------------------------+
```

---

## 交互改动

### plugins/one_stroke
- **现在**：Every board message repeats the same four lines of chrome. START (`一笔画开始！从起点出发...`) + `当前难度：普通，预计奖励：18 个Pt。` + PROMPT (`请输入 WASD 序列，或输入 R 重置 / Q 放弃。`) at __init__.py:136-147; RESET + PROMPT at :172-177; PROGRESS + PROMPT at :274-289. A 20-edge round emits PROMPT eight to fifteen times.
- **改为**：The board card carries a permanent control legend strip (`W A S D 移动  R 重置  Q 放弃`) and a live reward meter. Messages.PROMPT, Messages.START, Messages.RESET, Messages.PROGRESS are deleted from messages.py. Every in-round action produces exactly one image and zero text.
- **为什么更好**：The status text was 100% redundant with what the board already shows plus one fixed instruction. Moving the instruction into the frame means it is always visible and never repeated in the transcript. Scrollback goes from an alternating image/wall-of-text ladder to a clean strip of themed boards — which is exactly what makes a theme legible to a third party scrolling past.
- **移除命令**：一笔画 h loses its reason to be a text dump (becomes OneStrokeRulesCard)

### plugins/one_stroke
- **现在**：`Q` -> '已放弃本局。' (:164-168). Waiter timeout -> '超时未操作，本局已结束。' (:154-157). In both cases the player never learns the solution, and the generated puzzle is destroyed by game_manager.end_game with nothing to show for it.
- **改为**：Both paths render OneStrokeSolutionCard: the board with the full Euler trail drawn and every step numbered, plus the WASD solution string and a marker for how far the player actually got.
- **为什么更好**：The solver already exists — `_find_euler_trail` (difficulty.py:39-59) is used to compute the branching factor for rewards, so the answer is free. Giving up currently teaches nothing; giving up with a numbered solution diagram teaches the whole game. It converts the plugin's worst moment into its most shareable image, and it is a card that could not exist as text (a 20-step path on a 5x5 lattice is not describable in a sentence).

### plugins/one_stroke
- **现在**：A win emits three separate messages: board + win_message (:245-250), then the daily-task notification (:259-262), then the level-up notification (:267-270). The win_message states '获得 28 个Pt' with no explanation of how 18 became 28.
- **改为**：One OneStrokeVictoryCard with an explicit reward ledger: 基础奖励 18 Pt / 速度加成 x0.78 / 生日翻倍 x2 / 获得 28 Pt / 余额 1204 Pt, plus rank-in-difficulty and its delta, plus the task and level rows as footer strips.
- **为什么更好**：Three messages in a group chat get separated by other people's chatter and read as spam. More importantly, the speed-decay mechanic is the whole point of the game (DECAY_TAU_BY_SCALE, difficulty.py:16-20) and it is currently invisible — players cannot tell that finishing 5s faster nearly doubles the payout. A ledger is a table, and tables are what images are for.

### plugins/one_stroke
- **现在**：/一笔画排行榜 renders one 1500px-wide card with three 360px columns of 10 rows at font_size 23 (leaderboard.py:71-98, :144-145). A group client downscales that to roughly 1000px, putting body text at about 15 real pixels. A player outside the top 10 appears nowhere and learns nothing.
- **改为**：/一笔画排行榜 defaults to one difficulty at the house 898 portrait width with rows at font_size 30, and pins the viewer's own row below a separator when they are outside the top 10. /一笔画排行榜 简单|普通|困难 selects; /一笔画排行榜 全部 keeps today's 3-up.
- **为什么更好**：This is the one surface in the codebase that violates the 'prefer portrait, avoid very wide' constraint, and it is the surface most likely to be screenshotted. Narrowing triples the effective text size after client downscale. The pinned viewer row turns a leaderboard you are not on from a dead end into a progress readout — the same information, one query wider.
- **新增命令**：一笔画排行榜 <难度> / 一笔画排行榜 全部

### plugins/one_stroke
- **现在**：A multi-step WASD input that fails partway sends a text sentence naming the step index and the reason — '第 3 步无效：这条线段已经走过了。' (:187-198, messages.py:22-24) — plus a board that shows the position *before* the failing move. The player has to mentally replay their own input to find where they went wrong.
- **改为**：The board card draws the attempted-but-rejected step in place: the failing edge is marked at its actual location with the step number, and the fail sentence moves into the card's strip as secondary confirmation.
- **为什么更好**：'第 3 步' is a coordinate in the input string; the player needs a coordinate on the board. This is a pure translation from an index the machine knows to a position the human is looking at, and it only becomes expressible once the response is an image. Requires GameSession to retain the last rejected (node, direction) — a two-field addition next to move_history (session.py:31).

### plugins/cck
- **现在**：Wrong guesses are counted silently (`player_counts[user_id] += 1; continue`, :251-253). On the third strike the player gets a refusal: '你已经回答三次啦，可以回复 bzd 查看答案～' (:245-248). The channel has no idea how many attempts anyone has burned.
- **改为**：The third strike posts the puzzle card again with one additional crop revealed and the subtitle '追加线索' — burning your attempts buys the channel more of the picture. Attempts beyond that still get the text refusal.
- **为什么更好**：A refusal is a dead end; a progressive reveal is a mechanic. This is only possible because the response is an image — you cannot 'reveal more' of a text answer. It also makes a stuck round self-resolving instead of drifting to the 180s timeout, and it converts the plugin's most-seen surface into a surface people see twice. Requires random_crop_image (draw.py:24-84) to generate cut_counts+1 crops up front and return a list.

### plugins/cck
- **现在**：Every round exit sends two messages: an answer sentence then the raw full card image. The sentence is `f"答案是———{character_name}card_id: {card_id}"` (:226) — note the missing space, producing '香澄card_id: 1234'. 'card_id: 1234' is an internal database key that no player can do anything with.
- **改为**：One CckRevealCard carrying the illustration, the character name, the card's actual title from __processed_data__[card_id]['prefix'], rarity as star glyphs, card type (期间限定 / 生日 / 梦幻祭 ...), and the id as a small '#1234' suffix.
- **为什么更好**：The plugin already has all of this data loaded — Card._get_data (card.py:34-48) fetches bestdori's cards/all.5.json which carries prefix, rarity, type and stat for every card — and throws all of it away, showing the primary key instead. Collapsing two messages to one also fixes an entire class of string-concatenation bug by construction.

### plugins/cck
- **现在**：Wrong-but-valid guesses are discarded at :251-253 — matched to a character, counted, and dropped. The funniest part of a group round (who thought that crop was Arisa) is invisible.
- **改为**：The reveal card carries a '也有人猜过' roll: `Arisa -> 有咲 · Tae -> たえ · Rimi -> りみ`, truncated to two lines.
- **为什么更好**：Echoing each wrong guess as its own text message would be intolerable spam; collecting them onto the terminal card costs zero extra messages and turns a discarded list into the social payoff. This is a textbook case of an image unlocking content that text could not carry.

### plugins/guess_chart
- **现在**：Hints are three one-line text messages consumed from a list (tips at :223-227, sent at :290-293). They scroll away. hard and expert get no hints at all — '`hard 和 expert 难度没有提示哦`' (:279-282) — which is the difficulty where players most need them.
- **改为**：'提示' renders GuessChartHintBoardCard: three slots, revealed ones showing their value, locked ones showing '? ? ? ?' in muted_text_color. Hints become available at every difficulty, priced against the reward (the card shows '再要一条提示，奖励 -20%').
- **为什么更好**：Persistence: one re-rendered card replaces three lines that get buried under guesses, so the accumulated intel is always one scroll-stop away. Availability: banning hints on hard/expert is a blunt instrument that makes the hardest mode feel unplayable; a visible price turns the ban into a trade-off the player can see and choose. The price is only legible because the card can show the struck reward — as text it would be another line nobody reads.
- **移除命令**：the 'hard 和 expert 难度没有提示哦' refusal at :279-282

### plugins/guess_chart
- **现在**：Every one of the three round exits sends the answer text, then the jacket image as a separate trailing message (:253-262 timeout, :298-308 bzd, :349-379 win — where the jacket lands *after* the daily-task and level-up messages, so the reveal arrives fourth). The note count computed at :186 is deliberately discarded (:214-216).
- **改为**：One GuessChartRevealCard per exit: jacket + title + band + difficulty + level + BPM + note count + candidate-pool size + reward ledger + wrong-guess roll + task/level footer rows.
- **为什么更好**：Ordering alone is worth it — today the picture of the answer shows up after two unrelated reward notifications, so the reveal is the least prominent part of the reveal. Beyond that, the note count and pool size explain *why* the reward was 12 Pt (amount is derived from potential_song_number, :317-324), turning an opaque number into a legible one.

### plugins/guess_chart
- **现在**：Wrong guesses go to logger.debug only (:382-384). Players never see what anyone else tried, and a near-miss from the fuzzy matcher (utils.py:108-145) is completely invisible.
- **改为**：The reveal card lists the round's wrong guesses as '有人猜过  Arisa -> 六兆年 · Tae -> Ringing Bloom'.
- **为什么更好**：Same reasoning as cck, plus a diagnostic bonus: the fuzzy matcher has a dynamic CJK threshold (utils.py:126-128) and surfacing what it resolved a guess to makes matcher failures visible to the maintainer without a log dive.

### plugins/cck
- **现在**：Both cck and guess_chart are channel-scoped multiplayer games (GamersStore keys on event.channel.id, cck/store.py:17-32). kit_for_user is per-user, so there is no obvious 'whose theme is this'.
- **改为**：Explicit rule, applied identically in both plugins: the PUZZLE card renders in the round starter's theme; the REVEAL card renders in the winner's theme (falling back to the starter's on timeout/bzd). The signature line names the owner: '香澄 的主题 · 樱色'.
- **为什么更好**：This is the 'yo dude where'd you get that' mechanic doing real work instead of being decoration. Winning a group game makes your theme the thing everyone in the channel is currently looking at, with your name attached and the theme's name printed. It also gives the theme a social cost/benefit loop that a single-player plugin cannot: two different themes can appear in one round, which is the clearest possible demonstration to an onlooker that themes exist and differ.

---

## 保留为文本
- **plugins/one_stroke** — Messages.INVALID_INPUT — '输入无效，请只使用 WASD（可多字符）、R 或 Q。' (__init__.py:181-184)：Fires on every typo, mid-round, while the player is in a speed-scored timer that is actively decaying their reward (apply_time_decay, difficulty.py:164). A 100ms+ render on a typo literally costs the player points. It is also the one message where nothing spatial is being communicated.
- **plugins/one_stroke** — '你已经在进行一笔画挑战了。' (__init__.py:131-134) and the error-code reply '错误码：{code}' + Messages.ERROR (:296-301)：Refusal and crash paths. The crash path in particular must not depend on the render stack, since a render failure is one of the things that can land you there.
- **plugins/cck** — '已强制结束猜卡面' (:126-129), '没有正在进行的猜卡面，你可以直接使用 @Kasumi /猜卡面 来开始' (:132-136), '你已经在猜卡面咯' (:152-155)：Acknowledgements and refusals with no payload. Rendering a card to say 'ok, stopped' is pure latency and pure clutter, and it dilutes the signal that a card means something happened.
- **plugins/cck** — '未知难度：{arg}\n可用难度：{...}\n可使用 /猜卡面 -h 查看帮助' (:144-149)：An input error. It should be instant and it already points at the gallery card for anyone who wants to browse. Making the error itself a card punishes a typo with a download.
- **plugins/cck** — '你已经回答三次啦，可以回复 bzd 查看答案～' (:245-248), for the 4th and later attempts once the 追加线索 reveal has fired：Once the extra-crop reveal has already been spent, further attempts genuinely have nothing new to show. A repeated card would be identical pixels, which is worse than a sentence.
- **plugins/cck** — Wrong-but-valid guesses produce no message at all (:251-253)：Current behaviour and it is correct — a group round can produce a dozen wrong guesses. They are collected and shown once on the reveal card. Do not add per-guess feedback in any medium.
- **plugins/guess_chart** — '正在加载谱面...' (:124-127)：This is the latency ack that exists precisely because the next steps are a bestdori network fetch (Chart.get_chart_async, :185) plus a heavy chart render. Making it an image defeats its only purpose. It must remain the fastest possible message in the plugin.
- **plugins/guess_chart** — '已强制退出猜谱面' (:104-107), '没有正在进行的猜谱面' (:110-113), '已经在猜谱面了哦，如果有异常，请使用 @Kasumi /猜谱面 -f 以强制结束游戏' (:115-120)：Session-control acknowledgements and refusals. Same reasoning as cck.
- **plugins/guess_chart** — '{level} 的曲子一共只有 {n} 首，太简单了哦！试试换个等级吧' (:146-149) and '没有符合条件的谱面' (:172-175)：Pre-round validation errors that abort before any game state exists. They fire before the 'loading' phase, so a render here would be the slowest part of a failed command.
- **plugins/guess_chart** — '发生错误！重新开一把吧\n错误码：{code}' (:190-194), '发生谱面渲染错误！重新开一把吧' (:203-206), '未知游戏类型！' (:330-333)：Crash paths. The chart-render MemoryError branch (:201-206) is specifically a memory-exhaustion path — attempting another large PIL composition there is the exact wrong response.
- **plugins/guess_chart** — '没有更多提示了哦' (:285-288) if the hint-board card is not built：Standalone fallback only. If GuessChartHintBoardCard ships, this becomes the all-slots-revealed state of the card and the text is deleted; until then it stays a one-line refusal.

---

## 风险
- CCK CROP CLIPPING IS A REAL EXISTING BUG, and moving to a VStack of separate crops changes puzzle difficulty. draw.py:45-59 allocates a canvas of height cut_length*cut_counts but pastes at y = i*(cut_length+6), so the last crop is clipped by 6*(cut_counts-1) px. For [6块床板] (6 strips of 40px) that is 30 of the last strip's 40 rows — the sixth strip is 75% gone today. Laying the crops out with the layout engine fixes it, but every player of those difficulties suddenly gets meaningfully more pixels. Either accept the difficulty shift explicitly or trim cut_counts on the affected settings at the same time.
- GUESS_CHART PUZZLE CARD PIXEL FIDELITY. At the default pixel_ratio=2 (core.py:171), kit.image(chart, width=Fixed(w), height=Fixed(h)) upsamples the chart to 2w x 2h with LANCZOS and then AutoPage.render downsamples the whole page back (layout.py:175-179). That round trip softens note edges on the one image whose pixels are the game. Mitigation used in the design: render this card with page.render(RenderContext(pixel_ratio=1)), which returns the canvas untouched (layout.py:175-177). The cost is 1x-rasterized kit corners and shadows on that one surface — verify it does not look cheap in fluent (8px radius) and neon.
- GUESS_CHART PUZZLE CARD SIZE AND MEMORY. render(chart) for easy/normal produces (chart_w - 24) * num_slices x 1500, which for a long song can exceed 900px wide. The framed card then approaches 1030 x 1712. MemoryError is already a live, handled failure mode in this plugin (__init__.py:201-206), so wrapping the chart in another full-page RGBA canvas measurably raises the odds of hitting it. Wrap the card render in the same try/except MemoryError and fall back to today's bare-image send.
- CCK WIDE DIFFICULTIES LOSE RESOLUTION IN A FRAMED CARD. [寻找记忆] is cut_width 1334 (doubled to 2668) and [6块床板] is 1200 (doubled to 2400). Capping the card at max_width=1500 forces those crops down to about 1372 — a 1.94x linear reduction versus what is sent today. Clients downscale to roughly 1000px anyway so the practical loss is small, but it is a real difficulty change for three of twelve settings. Either accept it or halve cut_width for those entries in image_cut_settings.json (a data edit, no code).
- BANGDREAM BACKGROUND COST, MULTIPLIED. graph.py:338-345 calls random.choice(list(Path(BG_DIR).glob(...))) on every render — an uncached directory scan — and the image-treatment background is roughly 3x the simple pattern (measured 0.25s vs 0.08s at 898x898). one_stroke pays this on every single move today. Adding a victory card, a solution card and a rules card multiplies it. Hoist the glob to module scope, and use kit.background() (no source) for the high-frequency in-round board, reserving the image treatment for the terminal cards.
- IN-MEMORY PIL SOURCES ARE COPIED ON EVERY RENDER AND NEVER CACHED (atoms.py:416-421: an Image.Image source is .convert('RGBA').copy() each time, only Path goes through ctx.image_cache). The cck full card art, the cck crops, the guess_chart chart and the guess_chart jacket are all in-memory. Each renders once per round so it is acceptable — but do not put any of them on a surface that re-renders per move, and prefer passing card_path (a Path, already available at cck/__init__.py:159) to the reveal card instead of pil_full_image.
- MULTIPLAYER THEME OWNERSHIP MEANS ONE ROUND CAN CHANGE THEMES MIDWAY. The design deliberately renders the cck/guess_chart puzzle in the starter's kit and the reveal in the winner's kit. That is the mechanic, but it can read as a bug to someone who does not know themes exist. The signature line naming the owner is what makes it legible — so the signature must NOT be suppressed on a reveal card just because the winner is on a starter theme. Consider overriding the starter-suppression rule for the multiplayer reveal specifically, or the flip will look unexplained.
- PASSIVE GENERATOR PLUMBING MUST SURVIVE EVERY REWRITE. Every send in all three plugins appends gens[msg_id].element and passes referrer=gens[msg_id].event.referrer (one_stroke/__init__.py:94-98 is the canonical form). Collapsing N sends into 1 means N-1 gens entries are created and never used — harmless, but the surviving send must use the LATEST message id, which is the id the loop most recently wrote (latest_message_id / msg_id / message_id depending on plugin). Getting this wrong silently breaks reply threading.
- CCK VARIABLE SHADOWING WILL BITE THE REVEAL CARD. At cck/__init__.py:257 the loop reuses `msg = Message()`, destroying the player's guess string that was read at :215. Any reveal card that wants to print the winning guess (or feed the wrong-guess roll) must capture it before that line. Related: the birthday branch at :259-266 compares character_name (which is character_data[character_id][0], e.g. '戸山 香澄') against get_today_birthday() output; if those name forms differ, the x4 branch is dead code today. Rendering '生日 x4 (香澄)' on a card will make that latent mismatch visible for the first time.
- EULER TRAIL IS NOT GUARANTEED TO BE A FULL SOLUTION. _find_euler_trail (difficulty.py:39-59) assumes an Eulerian path exists; generate_graph builds by walking so it normally does, but it can break early when candidates run out (graph_generator.py:85-86) and the reward path never checks the trail's completeness. The solution card MUST assert len(trail) - 1 == graph.total_edges() and drop the 参考解法 panel when it does not, or it will confidently print a wrong answer.
- NARROWING /一笔画排行榜 CHANGES AN EXISTING COMMAND'S OUTPUT. Anyone used to seeing all three difficulties at once loses that by default. The '全部' escape hatch is mandatory, not optional, and the default difficulty should be the one the viewer played most recently rather than a hard-coded 普通 (derivable from OneStrokeGame rows, models.py:56-65).
- VICTORY / REVEAL CARDS EXCEED THE 0.15s PER-MESSAGE BUDGET. An 898 x ~1430 page at pixel_ratio=2 is a 1796 x 2860 canvas — roughly 1.5x the area of the measured 898x987 reference, so the bangdream image background lands near 0.4s. These are once-per-round terminal cards behind an existing await, so it is defensible, but every one of them must use await page.render_async() (layout.py:181-199) or a slow render will block the event loop and stall other channels' games.
- NONE OF THESE PLUGINS CURRENTLY PASS A KIT AT ALL. one_stroke/__init__.py:49 calls render(session) and :94 calls render_leaderboard(easy, normal, hard) with no kit argument, so both silently fall back to BanGDreamKit() despite already accepting the parameter. Every new call site needs kit=kit_for_user(event.get_user_id()) resolved on the event-loop thread before the render — never inside render_async, since the inventory Session is process-global and not thread safe.
