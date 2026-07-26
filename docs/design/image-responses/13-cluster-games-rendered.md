# 插件簇：games-rendered

涉及插件：plugins/blackjack, plugins/mines

卡片 9 张 · 交互改动 8 项 · 保留文本 15 项

---

## 卡片设计

### MinesBoardCard (extend plugins/mines/render/field.py::render)  `[P0/M]`
- **插件**：plugins/mines
- **触发**：/探险 <bet> [mines] — every dig, and the opening board
- **目的**：The mid-game board absorbs everything currently sent as text beside it: progress, multiplier, cash-out value, and the input prompt. Adds a next-tier payout preview so the dig-or-cash-out decision is actually informed. Turns the 25 unrevealed tiles — the single largest visual mass in the game — from hard-coded #DFDFDF into kit.panel_fill, which is the biggest theme-visibility win in this cluster.
- **展示数据**：revealed_count / safe_cells (session.py:28-33), session.multiplier formatted x8.33 (session.py:35-44), session.get_payout() (session.py:46-47), next-tier multiplier and payout — comb(total,r+1)/comb(gems,r+1)*(1-house_edge), same formula as session.py:41-44, one extra call, the 25 cell states from field.field (models.py:26), index of the cell just revealed (new render kwarg last_index), the controls, as a persistent hint strip
- **主题可见性**：Four surfaces at once. (1) The 25 unrevealed tiles become kit.panel_fill — bangdream translucent white, midnight #1E2438, neon near-black #0E0C1C, fluent 70% mica white. That is 360,000 px of the 786x786 board changing identity per theme, versus zero today. (2) The header pill is the kit's own two-band pill on bangdream and a kit panel elsewhere. (3) The ladder strip's three vertical dividers are kit.separator, which each kit styles differently. (4) kit.background() already carries the page.
- **manga 单色降级**：Best-case kit. Unrevealed tile = MangaKit panel_fill (255,255,255,242) with (18,18,20) ink numerals at 80px — the strongest contrast of any kit, and manga's 14px radius makes the grid read as inked panel borders. The two revealed-state colors stay hard-coded per §10 but never carry meaning alone: safe = Kasumi stamp, mine = Arisa stamp, and the just-dug cell adds a ring (geometry). The ladder strip is label/value text only. Nothing in this card needs hue.
- **替代的文本响应**：mines/__init__.py:210-221 (opening board + Messages.START 4-line block + _format_status + Messages.PROMPT) and mines/__init__.py:374-385 (per-dig board + Messages.SAFE_REVEAL + _format_status + Messages.PROMPT). Deletes _format_status (mines/__init__.py:73-78), Messages.PROMPT (messages.py:24), Messages.SAFE_REVEAL (messages.py:28) and the body of Messages.START (messages.py:18-23).

```
MinesBoardCard  —  AutoPage(min_width=896, padding=56, background=_background(kit))
measured output: 898 x 1279 (bangdream) / 898 x 1209 (other seven)

┌────────────────────────────────────────────────────────────────────────┐ 898
│ ┌ kit.title_pill("探险", sub, pill_width=717, pill_height=57) ───────┐ │
│ │▐ 探险 ▌                                             786 x 127      │ │  BD: title band 30px,
│ │  8/20 · x8.33 · 1,665 Pt                                           │ │  subtitle band 37px
│ └────────────────────────────────────────────────────────────────────┘ │  fallback: kit.panel 786x57, 24px
│                            ↕ gap 32                                    │  (717*625//570 == 786 exactly, so
│ ┌ kit.panel(HStack, width=Fixed(786), height=Fixed(116), padding=24)─┐ │   the BD pill and the stretched
│ │ 已翻开     │ 当前倍率    │ 可结算      │ 再挖一格                  │ │   fallback agree on width in all
│ │ 8/20       │ x8.33       │ 1,665 Pt    │ x11.80 → 2,359 Pt         │ │   eight kits — kills the §8b bug)
│ └────────────┴─────────────┴─────────────┴───────────────────────────┘ │
│    labels 22px kit.muted_text_color · values 36px kit.text_color        │
│    dividers = kit.separator(orientation="vertical", length=Fill())      │
│                            ↕ gap 32                                    │
│ ┌ kit.panel(Frame(Grid, 786,786, padding=50, aspect_ratio=1), r=32) ─┐ │
│ │  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐   Grid(columns=5, rows=5,     │ │
│ │  │ 1  │ │[K] │ │ 3  │ │ 4  │ │[K] │        column_track=Fixed(120),│ │
│ │  └────┘ └────┘ └────┘ └────┘ └────┘        row_track=Fixed(120),   │ │
│ │  ┌────┐ ╔════╗ ┌────┐ ┌────┐ ┌────┐        gap=21)                 │ │
│ │  │[K] │ ║[K]!║ │ 8  │ │ 9  │ │ 10 │   ╔╗ = the cell just dug      │ │
│ │  └────┘ ╚════╝ └────┘ └────┘ └────┘                                │ │
│ │  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐                                │ │
│ │  │ 11 │ │[K] │ │ 13 │ │ 14 │ │ 15 │                                │ │
│ │  └────┘ └────┘ └────┘ └────┘ └────┘                                │ │
│ │  … rows 4 and 5 identical …                                        │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                            ↕ gap 18                                    │
│ ┌ kit.panel(width=Fixed(786), height=Fixed(56)) ─────────────────────┐ │
│ │ 输入 1-25 挖下一格（可一次多个：7 13 19）·「收手」带走 1,665 Pt    │ │  24px muted, wrap=False
│ └────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
NO theme signature — mid-game surface, foundation §5 suppression rule 2.

CELL STATES (120 x 120, radius=16)
  unrevealed          just-dug (safe)     revealed safe       revealed Arisa
  ┌──────────┐        ╔══════════╗        ┌──────────┐        ┌──────────┐
  │          │        ║ ▒▒▒▒▒▒▒▒ ║        │ ▒▒▒▒▒▒▒▒ │        │ ░░░░░░░░ │
  │    13    │        ║ ▒kasumi▒ ║        │ ▒kasumi▒ │        │ ░arisa░░ │
  │          │        ║ ▒▒▒▒▒▒▒▒ ║        │ ▒▒▒▒▒▒▒▒ │        │ ░░░░░░░░ │
  └──────────┘        ╚══════════╝        └──────────┘        └──────────┘
  kit.panel()         same as revealed    fill (255,124,85)   fill (184,130,225)
  fill= OMITTED       + 4px inset ring    stamp 110x110       stamp 110x110
  → kit.panel_fill      in kit.text_color  (theme-invariant     (theme-invariant
  text kit.text_color                       state token, §10)    state token, §10)
  font_size=80

  CHANGE FROM TODAY: field.py:34 hard-codes fill=(223,223,223,255) and field.py:25
  hard-codes color=(255,255,255,255) — white on #DFDFDF is 1.35:1 contrast, below any
  legibility floor, and it is the most-repeated glyph in the game. Dropping both to
  kit.panel_fill / kit.text_color fixes the contrast AND makes 25/25 tiles themed.
```

### MinesResultCard (plugins/mines/render/result.py::render_result)  `[P0/M]`
- **插件**：plugins/mines
- **触发**：「收手」/「结算」/s, full clear, and hitting an Arisa
- **目的**：Collapses the three-message end sequence (result+board, daily-task notice, level-up notice) into one card, and gives the game's emotional peak a themed surface instead of a text tail. This is the card people screenshot, so it carries the theme signature.
- **展示数据**：result verb + shape glyph (▲/▼) from GameResult, signed net Pt at 64px — the headline, revealed_count / safe_cells and final multiplier, the fully revealed board including every Arisa position, the fatal cell, ringed, when result is LOSE, bet / payout / multiplier / new balance ledger, daily-task reward, when check_progress returned a message, level-up, when add_xp returned a message, theme signature (non-starter themes only)
- **主题可见性**：Same four surfaces as the board card plus the signature line, which is the only place the theme is ever named. Because a cash-out is the moment a player is most likely to screenshot or a bystander is most likely to look at, this is the card that has to answer 'where did you get that'. The reward chips use radius=height//2 pills so each kit's pill treatment shows.
- **manga 单色降级**：The verdict is a triangle glyph plus a Chinese verb plus a signed number — three non-colour cues. The signature is ink text plus an ink tick and is arguably most legible in manga. The revealed board degrades exactly as MinesBoardCard. Nothing reads by hue.
- **替代的文本响应**：mines/__init__.py:252-262 (cashout board + CASHOUT + payout + balance), :271-274 (daily-task message), :281-284 (level-up message); mines/__init__.py:338-348 + :357-360 + :367-370 (the identical full-clear trio); mines/__init__.py:314-324 (mine hit board + HIT_MINE + loss + balance). Three call sites, up to three messages each, become one image each.

```
MinesResultCard — AutoPage(min_width=896, padding=56, background=_background(kit))
measured output: 898 x 1445 (bangdream) / 898 x 1375 (other seven)

┌────────────────────────────────────────────────────────────────────────┐ 898
│ ┌ kit.title_pill("探险", "收手 · +1,465 Pt", 717, 57) → 786x127 ─────┐ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                            ↕ gap 32                                    │
│ ┌ kit.panel(width=Fixed(786), height=Fixed(132), padding=32) ────────┐ │
│ │  ▲  带着战利品跑掉了                              +1,465 Pt       │ │  verb 34px text_color
│ │     8/20 挖开 · x8.33                                  (64px)     │ │  detail 24px muted
│ └────────────────────────────────────────────────────────────────────┘ │  amount 64px, right
│   verdict glyph is a SHAPE not a colour:                               │
│     ▲ 收手/全清   ▼ 踩雷   ■ 平局(n/a here)                            │
│                            ↕ gap 32                                    │
│ ┌ kit.panel(Frame(Grid,…), 786 x 786, radius=32) ────────────────────┐ │
│ │  same grid as MinesBoardCard, after field.reveal_all_mines()       │ │
│ │  ┌────┐ ┌────┐ ┌────┐ ╔════╗ ┌────┐                                │ │
│ │  │[K] │ │[A] │ │[K] │ ║[A]!║ │[K] │  ╔╗ = the fatal cell, when     │ │
│ │  └────┘ └────┘ └────┘ ╚════╝ └────┘       result is LOSE          │ │
│ │  … 4 more rows …                                                   │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                            ↕ gap 32                                    │
│ ┌ kit.panel(width=Fixed(786), height=Fixed(140), padding=32) ────────┐ │
│ │  下注              200 Pt   │   结算            1,665 Pt          │ │  stat_row(kit,l,v)
│ │  倍率              x8.33    │   余额            3,096 Pt          │ │  label 24 muted / val 30
│ └─────────────────────────────┴──────────────────────────────────────┘ │  kit.separator vertical
│                            ↕ gap 18                                    │
│ ┌ HStack(gap=12) — rendered ONLY when the reward actually fired ─────┐ │
│ │ ( 每日任务 · +3 星星贴纸 )   ( 升级 Lv.7 → Lv.8 · +5 贴纸 )        │ │  pill-shaped kit.panel,
│ └────────────────────────────────────────────────────────────────────┘ │  radius=height//2, 24px
│                            ↕ gap 18                                    │
│                                    ▏ 主题 · 霓虹街机   ← 22px muted,   │
│                                                          right-aligned │
└────────────────────────────────────────────────────────────────────────┘
signature_for(kit) → None on starter themes, so most players see a clean card.

VERDICT COPY (verb line, from GameResult):
  CASHOUT  ▲ 带着战利品跑掉了        LOSE  ▼ 被 Arisa 逮到了
  WIN      ▲ 地下室搬空了！(full clear)
```

### MinesOddsCard (plugins/mines/render/odds.py::render_odds)  `[P1/M]`
- **插件**：plugins/mines
- **触发**：/探险 (no bet) — and a new /探险 赔率
- **目的**：The mines payout curve is the whole game and it is currently invisible: the only hint is one line of Messages.HELP saying 'more Arisas = higher multiplier'. This card is the bet prompt, the rules, and the odds table in one surface — and it is the first image a new player sees, so it is the first impression of the theme.
- **展示数据**：multiplier grid: 7 mine counts x 5 depths + full-clear column, computed from the live session.py:41-44 formula, the default (5 Arisa) row emphasised via kit.text_color vs muted, the player's current Pt balance (monetary.get), the player's most recent MinesGame row, if any, the exact input syntax, as a worked example
- **主题可见性**：A dense 6x8 grid of text is the purest test of a kit's typography and panel treatment — this is where fluent's 8px corners look nothing like bangdream's 48px. It arrives before the player has spent anything, so it is the theme's opening statement. Carries the signature.
- **manga 单色降级**：Pure text on a panel. The one semantic distinction (default row vs the rest) uses text_color vs muted_text_color, the exact two-signal idiom leaderboard.py:22-29 already relies on, plus a ★ glyph on the row. Fully monochrome-safe.
- **替代的文本响应**：mines/__init__.py:109-112 (Messages.BET_PROMPT, a bare '要下注多少Pt呢？' with no balance and no odds), and most of Messages.HELP (messages.py:43-61) — specifically the 奖励规则 block and the 探险 [下注] [Arisa数] usage line, mines/__init__.py:150-153.

```
MinesOddsCard — AutoPage(min_width=896, padding=56, background=_background(kit))
measured output: 898 x 1001 (bangdream) / 898 x 931 (other seven)

┌────────────────────────────────────────────────────────────────────────┐ 898
│ ┌ kit.title_pill("探险", "开一局 · 余额 3,096 Pt", 717, 57) ─────────┐ │
│ └────────────────────────────────────────────────────────── 786x127 ─┘ │
│                            ↕ gap 32                                    │
│ ┌ kit.panel(width=Fixed(786), padding=Insets.only(30,28,30,28)) ─────┐ │
│ │  赔率表 · Arisa 数 × 挖开格数                       (24px muted)   │ │
│ │  ┌──────┬──────┬──────┬──────┬──────┬──────┐                       │ │
│ │  │Arisa │ 1 格 │ 3 格 │ 5 格 │10 格 │ 全清 │  header row 22px muted│ │
│ │  ├──────┼──────┼──────┼──────┼──────┼──────┤                       │ │
│ │  │  1   │ 1.01 │ 1.10 │ 1.21 │ 1.62 │24.25 │  Grid(columns=6,      │ │
│ │  │  3   │ 1.10 │ 1.45 │ 1.96 │ 4.90 │ 2231 │    column_track=       │ │
│ │  │ 5 ★  │ 1.21 │ 1.96 │ 3.32 │17.16 │51536 │      Fixed(116),      │ │
│ │  │  8   │ 1.43 │ 3.28 │ 8.33 │  163 │ 1.0M │    row_track=Fixed(48)│ │
│ │  │ 12   │ 1.87 │ 7.80 │40.04 │11086 │ 5.0M │    gap=6)             │ │
│ │  │ 18   │ 3.46 │63.74 │ 2454 │  --  │ 466K │  6*116+5*6 = 726 =    │ │
│ │  │ 24   │24.25 │  --  │  --  │  --  │24.25 │    786 - 2*30  ✓      │ │
│ │  └──────┴──────┴──────┴──────┴──────┴──────┘                       │ │
│ │  ★ 默认 · 值为倍率，-- 表示格子不够                  (22px muted)  │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│   every number above is real: comb(25,r)/comb(25-m,r)*0.97              │
│   the ★ row is drawn with kit.text_color, the rest with                │
│   kit.muted_text_color — the leaderboard.py:22-29 filled/empty idiom    │
│                            ↕ gap 32                                    │
│ ┌ kit.panel(width=Fixed(786), height=Fixed(112), padding=28) ────────┐ │
│ │  回复「下注额 雷数」开始，例如   100 5              (26px)         │ │
│ │  上一局：收手 8/20 · x8.33 · +1,465 Pt              (22px muted)   │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                            ↕ gap 18                                    │
│                                    ▏ 主题 · 霓虹街机                   │
└────────────────────────────────────────────────────────────────────────┘

The grid body is identical for every user — @lru_cache(maxsize=8) the Component
keyed on the kit name. Only the header subtitle and the bottom panel are per-user.
```

### MinesStatsCard (plugins/mines/render/stats.py::render_stats)  `[P0/L]`
- **插件**：plugins/mines
- **触发**：/探险统计 (aliases minesstats, 探险统计, mks)
- **目的**：Kills the emoji text block plus the matplotlib PNG. The matplotlib chart is currently the single most theme-breaking image the bot produces: green/red bars on a white 1800x1200 canvas, identical in all eight themes. Replacing it makes the brag surface themed.
- **展示数据**：MinesStats.net_profit as an 80px signed numeral with a ▲/▼ glyph, win_rate, total_games, wins/losses, total_wagered / total_won / total_lost, avg_bet / avg_win / avg_loss / biggest_win / biggest_loss, max(revealed_count) and mode(mines) across records — data already in MinesGameRecord (stats_service.py:29-30) that the current text never surfaces, last 30 games as a bar strip plus a cumulative-profit polyline, theme signature
- **主题可见性**：This replaces the one image in the plugin that is provably theme-blind. The page background, four panel corners, all typography, and the polyline colour come from the kit; the sparkline sits on kit panel_fill. It is also the natural bragging screenshot, so it gets the signature line.
- **manga 单色降级**：Deliberately designed for it. Wins and losses are distinguished by position relative to the zero rule AND by solid-vs-hollow fill — two geometric cues, zero hue dependence. The net-profit sign is a triangle glyph plus a leading +/-. The polyline is kit.text_color, which is ink in manga. This card is fully readable printed in black and white.
- **替代的文本响应**：mines/__init__.py:417-436 — the 🏚️📊💰🎰🏆 text block plus create_win_loss_chart's matplotlib PNG, plus the '📊 图表生成需要至少2局游戏记录' fallback string at :433. Makes stats_service.create_win_loss_chart (stats_service.py, the matplotlib half) dead code.

```
MinesStatsCard — AutoPage(min_width=896, padding=56, background=_background(kit))
measured output: 898 x 1163 (bangdream) / 898 x 1093 (other seven)

┌────────────────────────────────────────────────────────────────────────┐ 898
│ ┌ kit.title_pill("探险", "战绩 · 137 局", 717, 57) → 786 x 127 ──────┐ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                            ↕ gap 32                                    │
│ ┌ kit.panel(width=Fixed(786), height=Fixed(176), padding=32) ────────┐ │
│ │  净收益                                            胜率           │ │  24px muted
│ │  ▲ +2,840 Pt                                       41.6%          │ │  80px / 40px
│ └────────────────────────────────────────────────────────────────────┘ │
│    ▲ when net_profit >= 0, ▼ when < 0 — shape carries the sign         │
│                            ↕ gap 32                                    │
│ ┌ kit.panel(width=Fixed(786), padding=Insets.only(30,28,30,28)) ─────┐ │
│ │  局数           137   │  胜 / 负            57 / 74               │ │  Grid(columns=2,
│ │  总投入      27,400   │  平均下注              200                │ │    row_track=Fixed(48),
│ │  总赢得      18,240   │  平均赢得              320                │ │    gap=(30,8))
│ │  总输掉      15,400   │  平均输掉              208                │ │  stat_row(kit,label,value)
│ │  最高赢       1,200   │  最高输              1,000                │ │  label 24 muted, wrap=False
│ │  最深         14 格   │  常挖雷数            5 个                 │ │  value 30 text_color, right
│ └───────────────────────┴────────────────────────────────────────────┘ │
│   最深/常挖雷数 come free from MinesGameRecord.revealed_count / .mines  │
│   (stats_service.py:29-30) which the current text block never shows     │
│                            ↕ gap 32                                    │
│ ┌ kit.panel(width=Fixed(786), height=Fixed(300), padding=32) ────────┐ │
│ │  最近 30 局                              累计 +2,840   (22 muted) │ │
│ │                                                                    │ │
│ │      █                 ██                        ╱‾‾‾‾╲___╱‾‾‾‾   │ │  SparkStrip: raw-PIL
│ │   █  █  █   █    █    ████   █     █        ╱‾‾‾╱                 │ │  Component (§12)
│ │ ──█──█──█───█────█────████───█─────█────────────────────────────  │ │  zero rule = kit.separator
│ │   ▽     ▽ ▽   ▽▽   ▽▽      ▽   ▽▽▽    ▽                          │ │  colour
│ │      ▽     ▽    ▽      ▽      ▽                                   │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│   30 slots across 722px → 24px slot, 18px bar, 6px gap                 │
│   WIN  = SOLID bar ABOVE the rule   (2 cues: position + fill)          │
│   LOSS = HOLLOW bar BELOW the rule  (outline only, 3px stroke)         │
│   cumulative profit = 3px polyline in kit.text_color, drawn last       │
│   every literal through ctx.scale_px()                                 │
│                            ↕ gap 18                                    │
│                                    ▏ 主题 · 霓虹街机                   │
└────────────────────────────────────────────────────────────────────────┘
```

### BlackjackTableCard (plugins/blackjack/render/table.py, extends generate_table)  `[P0/L]`
- **插件**：plugins/blackjack
- **触发**：/黑香澄 <bet> — the interactive table, every hit/double/split turn
- **目的**：Puts the stake on the table and turns the action prompt into a row of chips computed from game state, so an action that isn't legal is simply not shown. Also pins the page to a constant 896px for every hand size, fixing an existing unbounded-width problem.
- **展示数据**：bet_amount and current Pt balance, in the header — neither is on the table today, dealer hand with the hole card, and its partial score, player hand and score, the legal actions for this exact turn, which split hand is in play, when split_state > 0
- **主题可见性**：The blackjack table is the most-viewed image the bot produces and today it is locked to a single kit at process startup (render.py:92, __init__.py:93-109). Threading kit through makes the background, both hand pills, both card panels and the chip row per-user. The chip row is the loudest new signal: four kit-styled pills at the bottom of every turn, with bangdream's 48px radius versus fluent's 8px versus manga's 14px reading as an obviously different UI.
- **manga 单色降级**：The two tag colours stay hard-coded (§10) but each pill already contains the literal word Kasumi or You, so identity survives. The action chips are text-in-a-panel with no colour role. The card art itself is full-colour BanG Dream! photography in every kit — that is unavoidable and correct; the chrome around it is what changes. In manga the chrome is crisp black-on-white and the art reads as an inset photo, which is a legitimate manga convention.
- **替代的文本响应**：handlers.py:200-210 (table + ACTION_PROMPT / ACTION_PROMPT_SPLIT), :252-264 (table + ACTION_HIT_PROMPT), :313-324 (double table), :561-573 (split hand at 21 + 【第 N 幅牌】). Pre-empts and deletes messages.py:17-19,23 (ACTION_PROMPT, ACTION_PROMPT_SPLIT, ACTION_INVALID_SPLIT, ACTION_HIT_PROMPT) and messages.py:25-27 (DOUBLE_AFTER_SPLIT, DOUBLE_NOT_FIRST, DOUBLE_NOT_ENOUGH), plus their send sites handlers.py:237-240, :286-290, :293-296, :300-306. Removes the '你现在还有 X 个Pt' tail from handlers.py:136-139 and :166-169.

```
BlackjackTableCard — AutoPage(min_width=896, padding=32, background=kit.background())
measured output: 896 x 1461 (bangdream, 2v2) / 896 x 1391 (other seven)
WIDTH IS 896 FOR EVERY HAND SIZE — see the card ladder below.

┌──────────────────────────────────────────────────────────────────────┐ 896
│ ┌ kit.title_pill("黑香澄", "下注 200 · 余额 1,340", 759, 57) ──────┐ │
│ │▐ 黑香澄 ▌                                        832 x 127       │ │  759*625//570 == 832,
│ │  下注 200 · 余额 1,340                                           │ │  the exact content width
│ └──────────────────────────────────────────────────────────────────┘ │
│                          ↕ gap 24                                    │
│ ┌ kit.panel(padding=32)  stretched to 832 ─────────────────────────┐ │
│ │ ( Kasumi )  共 8 + ? 点                                          │ │  pill 240x48, fill
│ │   ↕ 18                                                           │ │  DEALER_TAG_COLOR
│ │        ┌──────────┐  ┌──────────┐                                │ │  (0xFF,0x55,0x22) — kept,
│ │        │  card    │  │  BACK    │   320 x 448, gap 32            │ │  §10 state token, and the
│ │        │  art     │  │          │   centred in 768px inner       │ │  word "Kasumi" is the
│ │        │      [8] │  │          │   [8] = value badge            │ │  redundant cue
│ │        └──────────┘  └──────────┘                                │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                          ↕ gap 24                                    │
│ ┌ kit.panel(padding=32) ───────────────────────────────────────────┐ │
│ │ ( You )  共 15 点                                                │ │  PLAYER_TAG_COLOR
│ │        ┌──────────┐  ┌──────────┐                                │ │  (0x34,0x74,0xD6)
│ │        │  card    │  │  card    │                                │ │
│ │        │      [7] │  │      [8] │                                │ │
│ │        └──────────┘  └──────────┘                                │ │
│ │   ↕ 18                                                           │ │
│ │ ( 补牌 h )  ( 停牌 s )  ( 双倍 d )  ( 投降 q )                   │ │  ← ACTION CHIPS
│ └──────────────────────────────────────────────────────────────────┘ │    kit.panel,
└──────────────────────────────────────────────────────────────────────┘    radius=h//2, 26px

ACTION CHIPS ARE COMPUTED, NOT CONSTANT:
  补牌 h / 停牌 s   always
  双倍 d            only when play_round == 1 AND split_state == 0
                    AND monetary.get(uid) >= bet_amount
  投降 q            always
  → the three states messages.py:25-27 exist to punish (DOUBLE_AFTER_SPLIT,
    DOUBLE_NOT_FIRST, DOUBLE_NOT_ENOUGH) become unreachable by construction.
  On a split hand the header pill gains a third element: "第 1/2 幅牌".

CARD SIZE LADDER (source art is 640x896; inner width after panel padding is 768):
  n<=2 → Fixed(320) x Fixed(448)   2*320+32  = 672  ✓   numeral src font 64  → 32 eff
  n==3 → Fixed(213) x Fixed(298)   3*213+64  = 703  ✓   numeral src font 96  → 32 eff
  n>=4 → Fixed(160) x Fixed(224)   4*160+96  = 736  ✓   numeral src font 128 → 32 eff
           laid out as Grid(columns=min(n,4), column_track=Fixed(160),
                            row_track=Fixed(224), gap=(32,24))
  320/213/160 are 640÷2, ÷3, ÷4 — integral reductions, per house rule §2.
  CARD_TEXT_FONT_SIZE must become round(64 * 320 / card_w) instead of the fixed 64
  at render.py:470, or the value numeral drops to 16px effective on a 4-card hand.
```

### BlackjackResultCard (plugins/blackjack/render/result.py::render_result)  `[P0/M]`
- **插件**：plugins/blackjack
- **触发**：end of every round — stand, bust, surrender, natural, split settle
- **目的**：One card replaces the dealer-turn narration, the redundant dealer-only hand image, the result text, the balance line, the daily-task notice and the level-up notice. A normal round goes from 7 messages to 4; a natural blackjack goes from 3 messages to 1. Retires generate_hand entirely.
- **展示数据**：result verb + shape glyph + signed net Pt at 64px, final player score : dealer score, how many cards the dealer drew (replaces DEALER_TURN + DEALER_DRAWN/DEALER_STAND), bet amount and new balance, both hands fully revealed, dealer hole card face-up, per-hand verdict and net for split rounds, daily-task and level-up rewards, when they fired, theme signature
- **主题可见性**：This is the message a bystander sees when someone wins — the moment they ask. It is the only blackjack surface that carries the signature line, and it is 896x1431 of themed background, five themed panels and a themed header. Today that same moment is a plain text line: '21 > 23，你获胜啦！赢得了 200 个Pt，你现在有 1,540 个Pt'.
- **manga 单色降级**：Verdict is glyph + verb + signed number. Both hand pills keep their hard-coded tag colours but carry the literal names. The scores are numerals. No hue is load-bearing anywhere in the chrome.
- **替代的文本响应**：handlers.py:56-77 play_dealer_turn in full (DEALER_TURN + DEALER_DRAWN/DEALER_STAND + a whole generate_hand image of just the dealer), sent at :591 and :665; handlers.py:699-702 (result text + balance); handlers.py:592-623 (split multi-line result); handlers.py:133-142 handle_player_bust (text-only today, no image at all); handlers.py:157-172 handle_surrender; handlers.py:413-426 (BLACKJACK_PUSH) and :438-469 (BLACKJACK_WIN + task + level, three messages); the reward tails at :458-468, :628-637, :708-717. Makes render.py:430-452 generate_hand dead outside tests/test_renderer_migration.py:75.

```
BlackjackResultCard — AutoPage(min_width=896, padding=32, background=kit.background())
measured output: 896 x 1431 (bangdream) / 896 x 1361 (other seven)

┌──────────────────────────────────────────────────────────────────────┐ 896
│ ┌ kit.title_pill("黑香澄", "你赢了 · +200 Pt", 759, 57) → 832x127 ─┐ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                          ↕ gap 24                                    │
│ ┌ kit.panel(width=832, height=Fixed(180), padding=32) ─────────────┐ │
│ │  ▲ Kasumi 爆牌，你获胜！              +200 Pt                    │ │  verb 34 / amount 64
│ │    21 : 23                                                       │ │  score 40px
│ │    ──────────────────────────────────────────────────            │ │  kit.separator
│ │    下注 200   ·   Kasumi 补了 2 张   ·   余额 1,540              │ │  24px muted
│ └──────────────────────────────────────────────────────────────────┘ │
│    'Kasumi 补了 2 张 / Kasumi 不需要补牌' is the entire content of    │
│    Messages.DEALER_TURN + DEALER_DRAWN/DEALER_STAND, reduced to a     │
│    clause. The dealer's cards are visible below, so the narration     │
│    and the separate dealer-hand image are both redundant.             │
│                          ↕ gap 24                                    │
│ ┌ kit.panel(padding=32) ───────────────────────────────────────────┐ │
│ │ ( Kasumi )  共 23 点  爆牌                                       │ │
│ │      ┌──────┐ ┌──────┐ ┌──────┐                                  │ │  cards forced to
│ │      │ [10] │ │  [3] │ │ [10] │   213 x 298, gap 32              │ │  Fixed(213) here —
│ │      └──────┘ └──────┘ └──────┘   ALL revealed                   │ │  the round is over,
│ └──────────────────────────────────────────────────────────────────┘ │  verdict > detail
│                          ↕ gap 24                                    │
│ ┌ kit.panel(padding=32) ───────────────────────────────────────────┐ │
│ │ ( You )  共 21 点                                                │ │
│ │      ┌──────┐ ┌──────┐ ┌──────┐                                  │ │
│ │      │  [9] │ │  [2] │ │ [10] │                                  │ │
│ │      └──────┘ └──────┘ └──────┘                                  │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                          ↕ gap 24                                    │
│ ┌ HStack(gap=12) — only when the reward fired ─────────────────────┐ │
│ │ ( 每日任务 · +3 星星贴纸 )   ( 升级 Lv.7 → Lv.8 · +5 贴纸 )      │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                          ↕ gap 18                                    │
│                                  ▏ 主题 · 霓虹街机                   │
└──────────────────────────────────────────────────────────────────────┘

VERDICT ROW (verb, glyph, from the branch at handlers.py:669-683):
  BLACKJACK  ★ BlackKasumi！        WIN  ▲ 你获胜啦
  DEALER BUST ▲ Kasumi 爆牌          PUSH ■ 平局，下注返还
  PLAYER BUST ▼ 你爆牌啦             LOSE ▼ Kasumi 获胜
  SURRENDER   ◤ 你投降了

SPLIT VARIANT — the single player panel becomes an HStack of two 404-wide panels:
┌ HStack(gap=24) ────────────────────────────────────────────────────┐
│ ┌ 第 1 幅牌  ▲ +100 ──────┐   ┌ 第 2 幅牌  ▼ -100 ──────────────┐ │
│ │ 共 20 点                │   │ 共 17 点                        │ │  cards Fixed(160),
│ │  ┌────┐ ┌────┐          │   │  ┌────┐ ┌────┐                  │ │  gap 20, wrap at 2 cols
│ │  │[10]│ │[10]│          │   │  │ [7] │ │[10]│                  │ │  (2*160+20 = 340
│ │  └────┘ └────┘          │   │  └────┘ └────┘                  │ │   = 404 - 2*32 ✓)
│ └─────────────────────────┘   └─────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
The two per-hand verdicts replace the multi-line evaluate_hand_result text block.

OUTPUT MODE: keep result.convert("RGB") as generate_table does at render.py:634.
The card is dominated by photographic art; utils.theming.image_segment sends RGBA
as PNG unconditionally, and a 896x1431 PNG of card art is 3-4x a q92 JPEG.
Returning RGB lets image_segment pick JPEG above its 900 KB switch.
```

### BlackjackSplitCard (plugins/blackjack/render/split.py::render_split_offer)  `[P1/M]`
- **插件**：plugins/blackjack
- **触发**：the split offer, when the opening two cards match
- **目的**：Today the player is asked 是/否 about splitting while looking at an undifferentiated table and with no idea what the split would cost or produce. This card shows both prospective hands, the extra stake, and the resulting total — and if the player cannot afford it, the offer is never made at all.
- **展示数据**：the dealer's up card, for context, both prospective hands with the matching pair split apart, a dashed placeholder for each card still to be dealt, the additional stake, the post-split total stake, and the balance after paying it, the two answers as chips
- **主题可见性**：A three-panel composition with a chip footer — the split card is where the kit's panel nesting shows most clearly (a 404 panel inside an HStack inside an 832 page). Sakura's 44px radius versus neon's 10px changes the whole silhouette. Deliberately no signature; it is mid-game.
- **manga 单色降级**：Everything is text, panels and card art. The dashed placeholder is a stroke outline, not a fill. No colour role.
- **替代的文本响应**：handlers.py:490-503 (table image + Messages.SPLIT_PROMPT + Messages.SPLIT_CHOICE, two strings in one message). Deletes messages.py:42-43 and messages.py:46-48 (SPLIT_NOT_ENOUGH) plus handlers.py:526-532.

```
BlackjackSplitCard — AutoPage(min_width=896, padding=32, background=kit.background())
measured output: 896 x 1093 (bangdream) / 896 x 1023 (other seven)

┌──────────────────────────────────────────────────────────────────────┐ 896
│ ┌ kit.title_pill("黑香澄", "要分牌吗？", 759, 57) → 832 x 127 ─────┐ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                          ↕ gap 24                                    │
│ ┌ kit.panel(padding=32) ───────────────────────────────────────────┐ │
│ │ ( Kasumi )  共 8 + ? 点                                          │ │
│ │      ┌──────┐ ┌──────┐        213 x 298                          │ │
│ │      │ [8]  │ │ BACK │                                           │ │
│ │      └──────┘ └──────┘                                           │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│                          ↕ gap 24                                    │
│ ┌ HStack(gap=24) — the two hands you WOULD get ────────────────────┐ │
│ │ ┌ kit.panel 404 ─────────┐   ┌ kit.panel 404 ─────────────────┐  │ │
│ │ │ 第 1 幅牌   下注 200   │   │ 第 2 幅牌   下注 200          │  │ │  24px muted
│ │ │   ┌──────┐  ┌ ? ─┐     │   │   ┌──────┐  ┌ ? ─┐            │  │ │  160 x 224 + a
│ │ │   │ [8]  │  │ ?? │     │   │   │ [8]  │  │ ?? │            │  │ │  dashed placeholder
│ │ │   └──────┘  └────┘     │   │   └──────┘  └────┘            │  │ │  for the card to
│ │ └────────────────────────┘   └───────────────────────────────┘  │ │  be dealt
│ └──────────────────────────────────────────────────────────────────┘ │
│                          ↕ gap 24                                    │
│ ┌ kit.panel(width=832, height=Fixed(148), padding=32) ─────────────┐ │
│ │  追加下注              200 Pt   │   分牌后总注         400 Pt   │ │  stat_row
│ │  余额（分牌后）      1,140 Pt   │                               │ │
│ │  ────────────────────────────────────────────────────────────   │ │
│ │  ( 是 )   ( 否 )                                                │ │  chips, 26px,
│ └──────────────────────────────────────────────────────────────────┘ │  radius=h//2
└──────────────────────────────────────────────────────────────────────┘
NO signature — mid-game interactive surface.

SUPPRESSION RULE: if monetary.get(uid) < bet_amount, this card is NEVER rendered.
The handler goes straight to handle_normal_game and the next BlackjackTableCard's
header subtitle reads "下注 200 · 余额 140 · 余额不足，本局不分牌".
That deletes Messages.SPLIT_NOT_ENOUGH (messages.py:46-48) and its awkward
post-hoc send at handlers.py:527-531, which today fires AFTER the player has
already answered 是.
```

### BlackjackStatsCard (plugins/blackjack/render/stats.py::render_stats)  `[P0/M]`
- **插件**：plugins/blackjack
- **触发**：/黑香澄统计 (aliases bkstats, bjstats, bk统计, bks)
- **目的**：Same job as MinesStatsCard on the other plugin: replace the emoji text block and the unthemed matplotlib PNG. Blackjack's chart is worse than mines' — it is a 12x8in two-subplot figure at dpi=150 with green/red fills and a legend, roughly 1800x1200, and it looks identical under all eight themes.
- **展示数据**：net_profit as an 80px signed numeral with ▲/▼, win_rate, total_games, wins/losses/pushes, total_wagered / total_won / total_lost, avg_bet / avg_win / avg_loss / biggest_win / biggest_loss, last 30 games as win/loss/push bars plus a cumulative polyline, theme signature
- **主题可见性**：Removes the second of the two matplotlib images. After this change there is no unthemed image left in either plugin. It is also the surface most likely to be posted deliberately ('look at my run'), which is exactly the third-party-eyeballs case the product goal targets.
- **manga 单色降级**：Win/loss/push are position (above / below / on the rule) plus fill (solid / hollow / tick) — two geometric cues, no hue. The polyline is kit.text_color. Fully monochrome-safe.
- **替代的文本响应**：blackjack/__init__.py:240-259 — the 🎴📊💰🎰🏆 text block, create_win_loss_chart's matplotlib PNG, and the '\n📊 图表生成失败' fallback at :256. Makes stats_service.create_win_loss_chart (stats_service.py:140-258) dead code; after both plugins land, matplotlib is only used by plugins/inventory/season_render.py:8.

```
BlackjackStatsCard — AutoPage(min_width=896, padding=56, background=kit.background())
measured output: 898 x 1163 (bangdream) / 898 x 1093 (other seven)
SHARES its body components with MinesStatsCard — only the header, the stat
labels and one extra row differ.

┌────────────────────────────────────────────────────────────────────────┐ 898
│ ┌ kit.title_pill("黑香澄", "战绩 · 137 局", 717, 57) → 786 x 127 ────┐ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                            ↕ gap 32                                    │
│ ┌ kit.panel(width=Fixed(786), height=Fixed(176), padding=32) ────────┐ │
│ │  净收益                                            胜率           │ │  24px muted
│ │  ▼ -1,240 Pt                                       41.6%          │ │  80px / 40px
│ └────────────────────────────────────────────────────────────────────┘ │
│                            ↕ gap 32                                    │
│ ┌ kit.panel(width=Fixed(786), padding=Insets.only(30,28,30,28)) ─────┐ │
│ │  局数           137   │  胜 / 负 / 平    57 / 74 / 6              │ │  Grid(columns=2,
│ │  总投入      27,400   │  平均下注              200                │ │    row_track=Fixed(48),
│ │  总赢得      18,240   │  平均赢得              320                │ │    gap=(30,8))
│ │  总输掉      19,480   │  平均输掉              263                │ │
│ │  最高赢       1,200   │  最高输              1,000                │ │
│ └───────────────────────┴────────────────────────────────────────────┘ │
│   胜/负/平 is a genuine blackjack-only field (BlackjackStats.pushes,    │
│   stats_service.py:39) — MinesStats has no push concept                │
│                            ↕ gap 32                                    │
│ ┌ kit.panel(width=Fixed(786), height=Fixed(300), padding=32) ────────┐ │
│ │  最近 30 局                              累计 -1,240   (22 muted) │ │
│ │   █    █                                                          │ │  SparkStrip —
│ │   █  █ █   █     █      █                ‾‾╲                      │ │  the SAME shared
│ │ ──█──█─█───█─────█──────█───────────────────╲___                  │ │  Component as
│ │   ▽    ▽ ▽▽  ▽▽▽   ▽▽▽    ▽▽ ▽▽▽ ▽▽             ╲__╱‾‾╲___       │ │  MinesStatsCard
│ │      ▽▽    ▽    ▽      ▽▽▽    ▽▽▽                                 │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│   WIN  = SOLID bar ABOVE the rule                                      │
│   LOSS = HOLLOW bar BELOW the rule                                     │
│   PUSH = a 3px tick ON the rule (blackjack only — mines has no push)   │
│                            ↕ gap 18                                    │
│                                    ▏ 主题 · 霓虹街机                   │
└────────────────────────────────────────────────────────────────────────┘

SparkStrip lives in utils/charts.py as a frozen-dataclass Component (§12), not
in either plugin — it is used by both stats cards and takes
(values: Sequence[int], kit: BaseKit) so it can be reused by any future plugin.
```

### BlackjackHelpCard (plugins/blackjack/render/help.py::render_help)  `[P2/S]`
- **插件**：plugins/blackjack
- **触发**：/黑香澄 h | -h | --help | help
- **目的**：Replaces a pre-baked static PNG that can never be themed. This is the first thing a curious onlooker types after seeing someone else's game, so it is the theme's actual first impression — and it can now show the exact same action chips the live table shows, which the static image cannot stay in sync with.
- **展示数据**：objective in one sentence, the two ways to start a round, each action chip, rendered identically to the live table, with what it does, the double-down legality rule stated once, where it belongs, the blackjack payout and push rule, pointer to the stats command, theme signature
- **主题可见性**：Turns a frozen 1-bit-of-branding PNG into a live theme showcase, and it is the surface a curious onlooker reaches first. Because it shows real chips rendered by the real component, an onlooker sees the actual visual language of the theme before playing.
- **manga 单色降级**：Text and chips only; separators come from kit.separator. Nothing colour-dependent. In manga this reads as a printed rules page, which is on-genre.
- **替代的文本响应**：blackjack/__init__.py:42-45 (HELP_MESSAGE, a raw read of plugins/blackjack/recourses/instruction.png) and its send at :133-136.

```
BlackjackHelpCard — AutoPage(min_width=896, padding=56, background=kit.background())
measured output: 898 x 1005 (bangdream) / 898 x 935 (other seven)

┌────────────────────────────────────────────────────────────────────────┐ 898
│ ┌ kit.title_pill("黑香澄", "怎么玩", 717, 57) → 786 x 127 ───────────┐ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                            ↕ gap 32                                    │
│ ┌ kit.panel(width=Fixed(786), padding=Insets.only(30,28,30,28)) ─────┐ │
│ │  目标                                              (24px muted)    │ │
│ │  点数尽量接近 21 但不超过，比 Kasumi 大就赢         (26px)         │ │
│ │  ────────────────────────────────────────────────────────────      │ │  kit.separator
│ │  开局                                                              │ │
│ │  /黑香澄 200      直接下注 200 Pt 开一局                           │ │
│ │  /黑香澄          先问你要下多少                                   │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                            ↕ gap 32                                    │
│ ┌ kit.panel(width=Fixed(786), padding=32) ───────────────────────────┐ │
│ │  牌桌上会给你这几个按钮                            (24px muted)    │ │
│ │  ( 补牌 h )   再要一张                                             │ │  the SAME chip
│ │  ( 停牌 s )   不要了，交给 Kasumi                                  │ │  component the live
│ │  ( 双倍 d )   只有第一轮、且没分牌时能用，注翻倍                   │ │  table renders, so
│ │  ( 投降 q )   认输，只赔一半                                       │ │  it cannot drift
│ │  ( 是/否 )    两张同点数时会问你要不要分牌                         │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                            ↕ gap 32                                    │
│ ┌ kit.panel(width=Fixed(786), height=Fixed(112), padding=28) ────────┐ │
│ │  BlackKasumi（开局 21 点）赔 1.5 倍 · 平局退还本金 (26px)          │ │
│ │  /黑香澄统计 看战绩                                (22px muted)    │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                            ↕ gap 18                                    │
│                                    ▏ 主题 · 霓虹街机                   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 交互改动

### plugins/mines
- **现在**：Every board image is followed by a text block: '安全！Kasumi 捡到了Pt\n已翻开 8/20 | 当前倍率 8.3284x | 可结算 1665 个Pt\n请选择 1-25，或输入「收手」结算' (mines/__init__.py:374-385, using _format_status at :73-78 and Messages.PROMPT/SAFE_REVEAL). The multiplier is the only number that matters and it is the third item on the second line, rendered at chat body size.
- **改为**：The multiplier and payout become the header pill subtitle at 37px — the largest text on the card — and a four-cell ladder strip under it. Messages.PROMPT is replaced by a permanent hint strip below the board, and Messages.SAFE_REVEAL is replaced by a ring on the cell that was just dug (new last_index kwarg). Zero loose text accompanies the board.
- **为什么更好**：Three separate reasons. (a) The house style says the title-bar subtitle is where mutable state goes and the plugin noun is the constant — mines currently wastes it on the literal string 'Arisa的仓库' (field.py:139). (b) The PROMPT text is 100% redundant with an image that already displays the numerals 1-25 at 80px. (c) 'safe' is better expressed as a ring on the specific cell than as a sentence, and it answers a question the sentence doesn't: which cell was that. Measured: the strings fit — '8/20 · x8.33 · 1,665 Pt' is 403px against 747px of available pill width at pill_width=717; the current full status string is 802px and would clip.

### plugins/mines
- **现在**：The player sees only the current multiplier and must decide whether to dig again. The reward for one more dig is invisible; the risk (mines / remaining cells) is computable but never shown.
- **改为**：The ladder strip's fourth cell shows '再挖一格  x11.80 → 2,359 Pt' — the multiplier and payout one dig deeper. When only one safe cell remains the label becomes '全清奖励'.
- **为什么更好**：This is a game-design improvement that only an image affords, not a formatting change. The whole tension of mines is a single decision made repeatedly, and today it is made blind. The value is a pure function of state — comb(total, r+1)/comb(gems, r+1)*(1-house_edge), the same expression as session.py:41-44 — so it costs one extra call and zero DB access. It also teaches the payout curve implicitly, which is currently only stated as a vague sentence in Messages.HELP ('翻开的安全箱子越多，倍率越高').

### plugins/mines
- **现在**：One message per dig. A 20-dig full clear produces 20 board images plus 20 text blocks, each image 190-474 KB (measured: bangdream 474 KB, manga 348 KB, neon 270 KB, minimal 190 KB at the current 898x987). In a group chat that is one player monopolising the scrollback with ~9 MB of uploads.
- **改为**：Accept multiple indices in one message: '7 13 19' digs three cells in order and renders ONE board card. The just-dug ring becomes an ordered badge (1/2/3). If a mine is hit partway, digging stops there, the remaining indices are ignored, and the result card notes '在第 2 格停下'.
- **为什么更好**：The image is what makes this legible — a text log of three sequential outcomes is confusing, an image showing three ordered badges is instantly readable. Measured cost argument: on the mines board, 0.212s of the 0.218s bangdream render is the background alone (a background-only page of the same size renders in 0.212s; adding three flat panels costs nothing). So the cost of a dig is almost entirely the cost of PRODUCING AN IMAGE AT ALL, not of what is on it. Batching three digs into one card is a straight 3x saving on both render time and upload bytes. This is also the counterweight that makes the rest of this proposal safe: without it, adding richer cards makes group-chat spam worse.
- **新增命令**：multi-index input on the existing dig channel (no new command name)

### plugins/mines
- **现在**：'/探险' with no argument replies with the bare text '要下注多少Pt呢？' (mines/__init__.py:109-112) and waits 60s. The player has no idea what mine counts are legal, what they pay, or what their balance is. The payout curve exists only as the sentence 'Arisa 数量越多，倍率越高' buried in an 11-line help block.
- **改为**：'/探险' with no bet replies with MinesOddsCard: the real 7x6 multiplier table, the ★-marked default row, the player's balance, their last result, and the worked example '回复「下注额 雷数」开始，例如 100 5'. The same card is reachable directly as '/探险 赔率'.
- **为什么更好**：A 7x6 numeric grid is inherently spatial — as text it is unreadable, as an image it is scannable in one glance. This is a genuinely new command that only makes sense once output is visual. It also converts a dead prompt into the moment the player learns the mines argument exists (today only discoverable via -h), and it puts a themed image in front of a player before they have spent anything. The grid body is identical for every user, so it is @lru_cache'd per kit and effectively free after the first render.
- **新增命令**：/探险 赔率

### plugins/blackjack
- **现在**：Every table image is followed by a hard-coded prompt listing all four actions (messages.py:17,23), regardless of which are legal. When the player picks an illegal one the bot sends a specific rejection: DOUBLE_AFTER_SPLIT '分牌之后不能双倍下注哦~请重新选择' (handlers.py:286-290), DOUBLE_NOT_FIRST '不能在非第一轮使用双倍下注哦~' (:293-296), DOUBLE_NOT_ENOUGH '你只有 X 个Pt，不够双倍下注哦~' (:300-306). Three of the five message constants in the file exist to punish the player for believing the prompt.
- **改为**：The table card renders a chip row computed from state: 补牌/停牌/投降 always; 双倍 only when play_round == 1 AND split_state == 0 AND balance >= bet. An action that is not legal is not drawn, so it cannot be chosen. One short generic text survives for typos.
- **为什么更好**：This is the clearest case in the cluster of an image changing the shape of the interaction rather than its medium. Seven message constants and four send sites are deleted, not because they moved into an image, but because the state they describe is now impossible to reach. It also removes a real UX lie: today the prompt string is assembled with a conditional double_part at handlers.py:233-236 in ONE of the two branches, so the split branch (ACTION_PROMPT_SPLIT) and the invalid branch disagree about whether 双倍 exists. Computing from state makes that class of drift structurally impossible.
- **移除命令**：the ACTION_PROMPT / ACTION_INVALID / DOUBLE_* text surface (7 constants, messages.py:17-27)

### plugins/blackjack
- **现在**：The end of a round is 3-4 separate messages: play_dealer_turn sends 'Kasumi 的回合啦！' + 'Kasumi 一共补了 2 张牌' + a whole second image of ONLY the dealer's hand (handlers.py:56-77, sent at :591/:665); then the result arrives as a text line (handlers.py:699-702); then a daily-task message (:708-711); then a level-up message (:712-717). The dealer-only image is redundant — those same cards are on the table image the player just received — and the money outcome, the most important information in the game, is plain text.
- **改为**：One BlackjackResultCard. The dealer's draw count becomes a clause on the verdict banner ('Kasumi 补了 2 张'), both full hands are shown, the money is a 64px signed numeral, and the task/level rewards become chips at the bottom. generate_hand (render.py:430-452) leaves the game flow entirely.
- **为什么更好**：A normal round drops from 7 messages to 4, a natural blackjack from 3 to 1, and one of the two images per round disappears — so this is fewer bytes on the wire, not more, despite being richer. It also fixes an ordering oddity: today the player learns they busted (handlers.py:133-142, text only, no image) after already receiving a table image, so the two halves of one event arrive as two notifications. Caveat this requires: check_progress and add_xp must be awaited BEFORE rendering rather than after sending, so both must be wrapped in try/except and the card must render without the chips if either fails.

### plugins/blackjack
- **现在**：The split flow asks 是/否 first and checks affordability afterwards: handlers.py:526-532 sends SPLIT_NOT_ENOUGH '你只有 X 个Pt，不够分牌的额外下注哦~接下来将按照不分牌处理' AFTER the player has already answered. The offer itself is a table image plus two text strings, and the player cannot see what the two hands would look like or what the total stake becomes.
- **改为**：Affordability is checked first. If the player cannot afford it, the offer is never rendered and the game proceeds normally, with a note in the next table card's header subtitle. If they can, BlackjackSplitCard shows both prospective hands with dashed placeholders for the cards still to be dealt, plus 追加下注 / 分牌后总注 / 余额（分牌后）, plus 是/否 chips.
- **为什么更好**：Same principle as the action chips: an offer that cannot be accepted should not be made. That deletes SPLIT_NOT_ENOUGH and removes the sequence where the bot asks a question, accepts the answer, and then retracts it. On the positive side, splitting is the highest-stakes decision in the game (it doubles the stake) and is currently the one made with the least information — showing the two hands side by side is exactly what an image is for.
- **移除命令**：Messages.SPLIT_NOT_ENOUGH (messages.py:46-48)

### plugins/blackjack
- **现在**：generate_table uses AutoPage(min_width=832) around an unbounded HStack of Fixed(320) cards (render.py:554-560, :608-612). A 3-card hand renders 1088px wide, a 5-card hand 1792px. The value numeral is drawn in source space at a fixed font 64 on a 640px card (render.py:470, :497), so its effective size is 64 * card_w/640 — 32px at 320 wide, and it would fall below the 22px readability floor at any smaller size.
- **改为**：Card display size steps down so the strip always fits the 768px inner width: n<=2 → 320x448, n==3 → 213x298, n>=4 → 160x224 in a Grid(columns=min(n,4)). CARD_TEXT_FONT_SIZE becomes round(64 * 320 / card_w) → 64/96/128, holding the effective numeral at exactly 32px in every case. Page width is pinned at 896 for every hand size.
- **为什么更好**：Two bugs at once. Today a long hand produces a very wide image that a chat client downscales hard — the exact failure the brief warns about — and the page width jumps between messages within a single round, which reads as visual noise. 320/213/160 are 640÷2/÷3/÷4, integral reductions per the house sizing rule, so the source art is never resampled at a fractional ratio. And it makes every blackjack image in a game exactly 896 wide, matching mines' 898, so the two games look like one product.

---

## 保留为文本
- **plugins/mines** — Messages.INPUT_INVALID '听不懂喵，请输入 1-25 的数字，或「收手」' — both sites, mines/__init__.py:289-292 (non-digit) and :297-300 (out of range)：Mid-game correction on a surface where a board image already exists one message above. Rendering a second 898x1279 image to say 'try again' costs 0.06-0.22s and 200-600 KB to convey ten characters. The player's eye is already on the board.
- **plugins/mines** — Messages.ALREADY_REVEALED '这个位置已经被翻开过了，换一个吧' (mines/__init__.py:304-307)：Same as above, and the board directly above already shows a stamp on that cell — the image half of this message has already been delivered.
- **plugins/mines** — BET_INVALID, BET_TOO_SMALL, BET_NOT_ENOUGH, MINES_INVALID, MINES_TOO_SMALL, MINES_TOO_LARGE (mines/__init__.py:123-133, :177-192, :200-204)：Refusals. The whole payload is a number or a constraint; an image adds latency and bytes and nothing else. MINES_INVALID is additionally HTML-escaped (messages.py:9-14) because it contains angle brackets — an easy source of a rendering-time surprise.
- **plugins/mines** — Messages.TIMEOUT '太久没动静了，Kasumi 先离开地下室了' (mines/__init__.py:227-230) — but extend the string to name the forfeited payout：The player has been absent for at least 180 seconds; nobody is watching. Rendering a full result card for an audience of zero puts an unrequested image in a group chat. The one legitimate complaint about the current message is that it does not say what was lost — fix that in the string, not with a card.
- **plugins/mines** — '已强制退出扫雷游戏' (mines/__init__.py:163-166 and :238-241) and '没有正在进行的扫雷游戏' (:158-161)：Acknowledgements of an explicit abort. The player asked to stop; giving them an image is the opposite of what they asked for.
- **plugins/mines** — Messages.ERROR + the error code (mines/__init__.py:392-397)：Correctness, not preference. The renderer is one of the things that can raise, and kit_for_user is on the path of every render. The error branch must not depend on either. Keep it as a plain text send with no kit involvement at all.
- **plugins/mines** — Messages.STATS_EMPTY '你还没有玩过地下室探险哦，快来试试吧！' (mines/__init__.py:411-414)：There is no data to render. A stats card with every field zeroed is a worse version of one sentence.
- **plugins/mines** — The residue of Messages.HELP (messages.py:43-61) after MinesOddsCard and the board hint strip absorb the payout rules and the controls — roughly four lines listing 探险 / 探险统计 / 探险 赔率 / 探险 -f：What remains is a command index, which is a list of strings with no spatial content. Its unique value today (the 1-25 numbering, the payout rule) has moved onto two cards that show rather than describe.
- **plugins/blackjack** — Messages.BET_PROMPT '你要下注多少Pt呢？' (handlers.py:367-370) — but append the balance to the string：This is the fastest path into the game and the player types a number immediately. Adding 0.1-0.25s and an image download in front of a one-word answer makes the game feel slower. Unlike mines, blackjack has no odds table worth showing here — the payout is always 1:1 (1.5:1 on a natural), so there is nothing spatial to display. The only real defect is that it omits the balance, which is a string fix.
- **plugins/blackjack** — BET_TIMEOUT, BET_INVALID, BET_TOO_SMALL, BET_NOT_ENOUGH, ALREADY_IN_GAME (handlers.py:373-398, __init__.py:146-153)：Refusals and timeouts, same reasoning as mines. ALREADY_IN_GAME is additionally near-unreachable because the matcher carries rule=not_in_game (__init__.py:68).
- **plugins/blackjack** — Messages.TIMEOUT_LOSE '时间到了哦，游戏自动结束。下注的Pt已没收哦~' (handlers.py:219-222)：180 seconds of silence means the player left. Same argument as the mines timeout: no audience, and an unrequested image in a group chat.
- **plugins/blackjack** — One short generic invalid-action line, replacing ACTION_INVALID / ACTION_INVALID_SPLIT (handlers.py:237-240)：Once the legal actions are chips on the table, this only fires on a typo. It should be one line pointing back at the image ('看牌桌下面那排按钮哦'), not a re-render of the table the player is already looking at.
- **plugins/blackjack** — Messages.SPLIT_TIMEOUT (handlers.py:507-510) and Messages.SPLIT_INVALID (handlers.py:518-521)：Both resolve to 'proceeding without a split'. The consequence is immediately visible on the next table card, which shows the unchanged stake in its header — so the text only needs to explain the interpretation, in one line.
- **plugins/blackjack** — The unexpected-error message with the refund and error code (blackjack/__init__.py:213-219)：Same correctness argument as mines: this branch catches failures that may include the renderer or the theme resolver. It must be reachable with no rendering at all.
- **plugins/blackjack** — '你还没有玩过黑香澄游戏哦，快来试试吧！' (blackjack/__init__.py:233-237) and the stats-error message (:265-269)：No data to render, and the error path must not depend on the renderer.

---

## 风险
- BLOCKER — blackjack cannot be themed at all today. BlackjackRenderer holds the kit as instance state (render.py:92, `self.kit = kit or BanGDreamKit()`) and the single instance is built once at startup (__init__.py:93-110) and stashed on the GameManager. All eight call sites go through `game_manager.renderer` (handlers.py:68,73,160,203,255,316,416,441,493,564). kit MUST become a per-call keyword on generate_table/generate_hand and every private helper must take kit first per house style §1. The expensive state (card art, face cache, cv2 cascade) is kit-independent, so the class survives — only the kit moves.
- Mines is also hardwired to BanGDream today: _render_field_image (mines/__init__.py:40-45) calls `render(field)` with no kit, even though field.py:110 already accepts one. One-line fix, but it means nothing in this cluster is currently theme-aware in practice.
- COST — the mines board is already over budget before any of this lands. Measured on this machine at pixel_ratio=2: bangdream 0.218s, neon 0.203s, sakura 0.201s, fluent 0.186s, midnight 0.176s, sailing 0.073s, manga 0.067s, minimal 0.056s. The house budget is ~0.15s and five of eight kits exceed it. `await page.render_async()` is mandatory on the per-move path, not optional. The good news, measured: a background-only page of the same size costs 0.212s in bangdream — i.e. essentially the whole render is the background, and the 25 cells plus panels are nearly free. So adding the ladder and hint strips is ~free; sending a SECOND image is not.
- BYTES — the current mines board PNG is 474 KB (bangdream) / 348 KB (manga) / 270 KB (neon) / 190 KB (minimal) at 898x987. The taller board card (1279 in bangdream) pushes that toward 600 KB. Cards are RGBA so utils.theming.image_segment sends PNG unconditionally; a 20-dig game is ~12 MB of uploads into one channel. The batch-dig change is the mitigation and should ship in the same pass, not later.
- The blackjack result and table cards must keep `result.convert("RGB")` (render.py:634). image_segment routes RGBA to PNG unconditionally, and a 896x1461 PNG of photographic card art is 3-4x a q92 4:4:4 JPEG. Mines and stats cards should stay RGBA (text-heavy, PNG keeps edges crisp). This is a per-surface decision, not a global one.
- Composing daily-task and level-up rewards into the result cards requires awaiting check_progress (daily_task/service.py:68-101) and monetary.add_xp (level_service.py:43-77) BEFORE rendering instead of after sending. Both hit the DB and both commit. A failure in either would now block the result image, where today it only drops a follow-up message. Both calls must be individually wrapped and the card must render without the chip row on failure.
- Existing legibility bug being fixed, worth calling out because it changes a visual people are used to: the unrevealed mines cell is fill=(223,223,223,255) with color=(255,255,255,255) text at font 80 (field.py:25-36) — white on #DFDFDF is 1.35:1 contrast, far below any floor, on the most-repeated glyph in the game. Moving to kit.panel_fill / kit.text_color fixes it in all eight kits (verified: midnight (226,232,245) on (30,36,56); neon (232,236,255) on (14,12,28); manga (18,18,20) on (255,255,255)). Some players may read the change as 'the tiles look different now'.
- The mines cell radius stays at an explicit 16 rather than letting the kit default show, because bangdream's default 48 clamps to 60 on a 120px cell (primitives.py:110) and turns every tile into a circle. That is a deliberate deviation from house rule §7 ('omit radius so the kit silhouette shows') and should be documented in the helper, otherwise someone will 'fix' it.
- utils.cards.response_card must accept a content width so the header aligns. The BD title pill's measured width is pill_width * 625 // 570, so the pill_width for a target content width W is CEIL(W * 570 / 625): 786 → 717, 832 → 759. Verified by measurement — 717 gives exactly 786x127 and 759 gives exactly 832x127. Floor division gives 716 → 785 and is off by one. If response_card cannot take a width, board cards need a local header helper and the §8b stretch mismatch comes back.
- Title-pill subtitles clip silently — BanGDreamTitlePill.render draws with _draw_left_aligned_text into a fixed pill and never measures the string (components.py:425-433), and measure() returns a constant size regardless of subtitle length (verified: four subtitles of wildly different lengths all measured 548x127). Measured at font 37 with CHINESE_FONT: '8/20 · x8.33 · 1,665 Pt' is 403px, worst realistic case '24/24 · x24.25 · 242,477 Pt' is 537px, available at pill_width=717 is 747px. Safe, but any future subtitle needs measuring, not eyeballing.
- Both result cards are tall — mines 898x1445, blackjack 896x1431 (1:1.6). That is within portrait tolerance but at the limit. If they read as too long in practice, the mines board on the result card can drop to Fixed(600) with 108px cells; do not shrink the blackjack card art below 160 or the value numeral falls under the floor even with the derived font size.
- Removing matplotlib from both stats services leaves plugins/inventory/season_render.py:8 as the only remaining importer, so matplotlib stays a dependency. create_win_loss_chart in both stats_service.py files becomes dead code — delete it rather than leaving two ~120-line unreferenced functions with duplicate font-loading side effects at import time (blackjack/stats_service.py:17-18 loads a FontProperties at module scope).
- The shared SparkStrip Component is used by both plugins and does not belong in either. utils/cards.py is documented as composition-from-BaseKit-atoms only, and SparkStrip is a raw-PIL Component (house §12). It needs its own home — utils/charts.py — and every literal inside it must go through ctx.scale_px(), which is the single easiest thing to get wrong in a custom Component.
- generate_card runs cv2 face detection and multi-layer PIL compositing per card (render.py:328-428). The per-Card memo (`card._get_image`) is per Card OBJECT and Shoe.deal() constructs a fresh Card every time (models.py:53-64), so the memo only helps within one hand. Rendering the same hand a third time on the result card re-composites every card. cut_card is cached by path (render.py:275-276, :322-325) so the expensive half is covered, but measure the result card end-to-end before assuming it fits the budget — it is the one surface here whose cost is not dominated by the background.
