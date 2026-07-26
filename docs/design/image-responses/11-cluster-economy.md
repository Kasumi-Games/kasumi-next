# 插件簇：economy

涉及插件：plugins/daily, plugins/red_envelope, plugins/monetary, plugins/daily_task

卡片 8 张 · 交互改动 11 项 · 保留文本 9 项

---

## 卡片设计

### PlayerCard (plugins/daily/render/player.py :: render_player)  `[P0/L]`
- **插件**：plugins/daily
- **触发**：/info · /balance · /余额 · /信息 · /个人信息 · /我的信息
- **目的**：The identity surface. Today it is three lines of text (daily/__init__.py:59-66). It should be the single place a player's whole loadout — theme, avatar frame, title, standing description — is visible at once, and the card an onlooker screenshots. This is the primary 'yo where'd you get that' vector: it is the only response whose *subject* is the player's cosmetics.
- **展示数据**：nickname (nickname.get(user_id)), avatar image + equipped avatar_frame cosmetic (get_equipped(user_id)['avatar_frame']), equipped title cosmetic (get_equipped(user_id)['title']), profile description (get_profile_description(user_id)), user.level (monetary.get_user), XP progress: progress_xp / level_xp_range / xp_needed — exactly the four values computed at daily/__init__.py:51-54, season Pt (monetary.get) with 赛季/休赛期临时 label from is_using_offseason_points(), star stickers (get_star_stickers), bonsai (inventory.get_quantity(user_id, 'bonsai')) — NEW, not in today's text, user.consecutive_checkins — NEW here, only visible on 签到 today, rank (get_user_rank(user_id).rank) — NEW here, only visible via /排行榜 today, today's daily task completion state (daily_task.get_today_task) — NEW here, offseason warning (conditional row)
- **主题可见性**：Maximum. The whole card is chrome: kit background, kit panel silhouette (48px BD corner vs 8px fluent vs 14px manga), kit title pill vs neutral header. The XP bar fill is getattr(kit,'primary',kit.text_color), so the one saturated element on the card is literally the theme's signature colour — magenta on neon, sakura pink on sakura, ink on manga, and it degrades to text_color on minimal which has no primary. The theme_signature footer fires here (non-starter themes only) and names the theme so a viewer can type its name into /主题.
- **manga 单色降级**：Clean. The six stat cells are boxes with a numeral and a word — no hue involved. The XP bar in manga is a solid ink fill (MangaKit.primary = rgba(18,18,20)) on a near-white panel_fill (255,255,255,242): maximum contrast, and the numeric label '1180 / 1520 · 还需 340' is always printed so the bar is never the only signal (§10 redundancy rule). The Lv badge and title pill are filled shapes, not colours. The avatar frame cosmetic is an image asset and degrades as-is.
- **替代的文本响应**：plugins/daily/__init__.py:59-66 (the entire `matcher.send` in `info`). Also absorbs the rank sentence built at daily/__init__.py:210-216 and the task line at daily/__init__.py:115-116 as at-a-glance cells (the full versions stay on /排行榜 and /每日任务).

```
AutoPage(min_width=896, padding=56, background=_background(kit),
         child=VStack([...], gap=32, align="start"))   ->  898 x ~1010
inner content width = 896 - 2*56 = 784

┌────────────────────────────────────────────────────────────────┐
│ ╭───────────────╮                                              │  header
│ │   个人信息     │   BD:  kit.title_pill("个人信息", "香澄 Lv.24",│  460x127
│ ╰──╴ 香澄 Lv.24 ╶╯          pill_width=460, pill_height=57)     │  measured
│                     else: utils.cards.response_card 2-tier      │
│                           header, Frame(hdr, align_x="start")   │
│                                                                 │
│                              ── gap 32 ──                       │
│ kit.panel(padding=32, radius=OMITTED)     Fixed(784) x Fixed(268)│
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ ┌───────────┐                                    ╭─────────╮│ │
│ │ │           │  香澄                   34px       │  Lv.24  ││ │
│ │ │  avatar   │  ╭───────────────────╮             ╰─────────╯│ │
│ │ │  Fixed160 │  │  太鼓の達人         │ title cos. Fixed(140) │ │
│ │ │ +frame192 │  ╰───────────────────╯  24px       x Fixed(56)│ │
│ │ │ Overlay() │  今天也要元气满满地打太鼓！  22px muted        │ │
│ │ └───────────┘  Fill()  wrap=False max_lines=1                │ │
│ │  gap 24        gap 24                                        │ │
│ │ ────────────────────────────────────────────────────────────│ │
│ │  XP                             1180 / 1520 · 还需 340  22px│ │
│ │  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░                    │ │
│ │  Overlay(align_x="start", align_y="center") of two panels:   │ │
│ │    track: Fixed(720) x Fixed(28) radius=14 fill=panel_fill   │ │
│ │    fill : Fixed(round(720*0.776)=559) x Fixed(28) radius=14  │ │
│ │           fill=getattr(kit,"primary",kit.text_color)         │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                              ── gap 32 ──                       │
│ Grid(columns=3, rows=2, column_track=Fixed(240),                │
│      row_track=Fixed(132), gap=(32,24))     784 x 288           │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │
│ │    1,203     │ │     480      │ │      12      │  40px value  │
│ │  赛季 Pt      │ │  星星贴纸     │ │   盆栽        │  22px muted │
│ └──────────────┘ └──────────────┘ └──────────────┘              │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │
│ │    24 天      │ │     #7       │ │    未完成     │              │
│ │  连续签到      │ │  等级排名     │ │  今日任务      │             │
│ └──────────────┘ └──────────────┘ └──────────────┘              │
│   each cell = kit.panel(VStack([value,label], gap=8, "center"), │
│               width=Fixed(240), height=Fixed(132), padding=24)  │
│                                                                 │
│ ── gap 32 ── (row present ONLY when is_using_offseason_points())│
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 休赛期临时 Pt 不会计入下一赛季     22px muted   Fixed(784)x56 │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│                              Frame(align_x="end"):  │ 主题 · 霓虹街机│
└────────────────────────────────────────────────────────────────┘
```

### CheckinCard (plugins/daily/render/checkin.py :: render_checkin)  `[P0/L]`
- **插件**：plugins/daily
- **触发**：/daily · /签到
- **目的**：Collapse the check-in fan-out — today it is up to three separate sends (daily/__init__.py:123-131: the main block, then an optional level-up message, then an empty finish) — into one card, and make the streak visible. The 7-day sticker bonus at daily/__init__.py:108-112 currently fires as a surprise; a 7-dot strip turns it into a countdown, which is the actual retention mechanic and only an image can show it.
- **展示数据**：reward amount (the gauss draw at daily/__init__.py:95), resulting season Pt balance, offseason flag -> replaces the 赛季 Pt label with 休赛期临时 Pt and adds the warning row (daily/__init__.py:103-104), user.consecutive_checkins + the 7-cell window ((n-1)//7*7+1 .. +7), the day-7 bonus state (daily/__init__.py:108-112), level-up: old_level, new_level, stickers — currently a SEPARATE message (daily/__init__.py:126-130, string built at monetary/level_service.py:74), today's task name/description/reward (daily/__init__.py:114-116), unread mail count (daily/__init__.py:118-121), state: claimed | already
- **主题可见性**：High and repeated — this is the one card almost every player sees every single day, so it is the theme's main daily impression. The 7 streak dots are the strongest per-theme signal on any card in the cluster: seven large primary-filled capsules, so neon's magenta / sakura's pink / midnight's indigo / manga's ink read instantly at thumbnail size even before any text is legible.
- **manga 单色降级**：The streak strip is the design's load-bearing manga case and it is built for it: done = filled ink capsule with a white numeral, today = filled capsule with a concentric ink ring (a SHAPE difference, not a colour one), future = white capsule with a muted numeral, bonus day = same but radius 20 instead of 45 (a corner difference). Four states, zero hue. The reward strip rows are ink left-rules plus words. No emoji anywhere — the 🎉 currently in daily/__init__.py:111 and monetary/level_service.py:74 MUST be stripped, old.ttf has no emoji glyphs and would render tofu.
- **替代的文本响应**：plugins/daily/__init__.py:83-86 (今天已经签到过了 -> the card in state="already"), :102-125 (the entire assembled msg), :126-130 (the separate level-up send). Absorbs plugins/monetary/level_service.py:74 and the mail-count line at :118-121.

```
AutoPage(min_width=896, padding=56, gap=32)     898 x ~960 (state=claimed)
inner width 784

┌────────────────────────────────────────────────────────────────┐
│ ╭──────────╮                                                   │
│ │   签到    │   kit.title_pill("签到", "第 24 天 · 香澄",        │
│ ╰─╴第24天╶─╯     pill_width=500, pill_height=57) -> 548x127     │
│                                                                 │
│ HERO  kit.panel(padding=32)          Fixed(784) x Fixed(176)   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │                                                             │ │
│ │   ＋7        Pt                          赛季 Pt   1,203     │ │
│ │   80px      34px                         22px muted / 34px  │ │
│ │   HStack(gap=12, align="end")            Frame(align_x=end) │ │
│ │                                                             │ │
│ │   state="already":  今天已经签到过了     40px, no numeral    │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ STREAK  kit.panel(padding=Insets.only(32,28,32,28))  784 x 210 │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 连续签到 24 天 · 本周            24px       inner = 720      │ │
│ │                                                             │ │
│ │  ╭────╮╭────╮╭────╮╭────╮╭────╮╭────╮┌────┐                │ │
│ │  │ 22 ││ 23 ││ 24 ││ 25 ││ 26 ││ 27 ││ 28 │                │ │
│ │  ╰────╯╰────╯╰══╯ ╰────╯╰────╯╰────╯└────┘                │ │
│ │   done  done TODAY  future future future  BONUS             │ │
│ │  Grid(columns=7, rows=1, column_track=Fixed(90),            │ │
│ │       row_track=Fixed(90), gap=15)  -> 7*90+6*15 = 720 exact│ │
│ │   done  : panel(Fixed90,radius=45, fill=primary), num white │ │
│ │   TODAY : Overlay([panel(90,r45,fill=text_color),           │ │
│ │                    panel(78,r39,fill=primary)])  = ink ring │ │
│ │   future: panel(Fixed90,radius=45, fill=panel_fill),        │ │
│ │           num in muted_text_color                           │ │
│ │   BONUS : same as future but radius=20 (square-ish corner)  │ │
│ │                                                             │ │
│ │  第 28 天 +120 星星贴纸      22px muted (text_color if hit)  │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ REWARD STRIP  (conditional rows, see RewardStrip design)        │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ ▌ 升级  Lv.23 → Lv.24                    ＋120 星星贴纸      │ │
│ │ ▌ 连续签到 28 天奖励                       ＋120 星星贴纸     │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ TASK  kit.panel(padding=32)          Fixed(784) x Fixed(140)   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 今日任务                                     未完成  22px    │ │
│ │ 【概率学博士】在黑香澄中赢得一局   24px  wrap=False ellipsis  │ │
│ │ 奖励 80 张星星贴纸                            22px muted     │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 未读邮件 3 封                    784 x 56  (conditional)     │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│                                              │ 主题 · 霓虹街机  │
└────────────────────────────────────────────────────────────────┘
```

### EnvelopeCard (plugins/red_envelope/render/envelope.py :: render_envelope)  `[P0/L]`
- **插件**：plugins/red_envelope
- **触发**：/发红包 <标题> <金额> <份数>  ·  /抢红包 [id]  ·  /红包 <id>
- **目的**：One renderer, four states (sealed | open | done | expired), replacing three different text messages. Today: creation is a one-line announcement (red_envelope/__init__.py:141-150), each claim is a private-feeling '恭喜你抢到 N Pt' (:218-222), and completion is a SECOND message (:229-238). In a group of ten claimers that is eleven near-identical texts and nobody can see the race. The card makes the envelope a shared object with a visible ledger — the single most social surface in the bot.
- **展示数据**：envelope.channel_index, envelope.title, envelope.total_amount, envelope.total_count, envelope.remaining_amount, envelope.remaining_count, creator nickname (nickname.get(envelope.creator_id)), the full claim ledger: ClaimRecord.user_id -> nickname, ClaimRecord.amount, sorted by amount desc, capped at 8 rows, the just-now claimer, marked with an ink left-rule + the word 刚刚, lucky king (EnvelopeCompletionInfo.lucky_king_id / lucky_king_amount, service.py:236), duration (_format_duration on EnvelopeCompletionInfo.duration_seconds, red_envelope/__init__.py:64-79), time to expiry (envelope.expires_at - now), state: sealed | open | done | expired
- **主题可见性**：The highest-leverage surface in the whole bot, because it is the only card a whole group is guaranteed to look at. Rendering it in the CREATOR's kit means 发红包 is literally a way to broadcast your theme — you hand people currency inside your own visual identity, and the footer reads '香澄 的主题 · 霓虹街机' (the owner_name form of theme_signature, which the foundation already provisions for shared surfaces). The segmented progress bar is a row of primary-filled chips, so the theme colour is the thing that visibly grows as the race runs.
- **manga 单色降级**：The claim bar is filled-vs-empty chips: identical semantics with zero hue. Ranking is carried by row order and printed numerals. 手气王 and 刚刚 are WORDS in filled pills, not colours (§10: every state token gets a glyph/shape/word). The just-claimed row is marked by a 6px ink rule in the left gutter — a position+shape cue. In midnight/neon the panel_fill is dark and primary is a bright accent, so filled chips read brighter than empty ones; in manga it inverts to ink-on-white and still reads. Nothing in this card depends on red meaning 'envelope'.
- **替代的文本响应**：plugins/red_envelope/__init__.py:141-150 (CREATE_SUCCESS), :217-222 (CLAIM_SUCCESS, conditionally — see interaction change 5), :225-238 (the separate CLAIM_COMPLETE send). Absorbs Messages.CREATE_SUCCESS / CLAIM_SUCCESS / CLAIM_COMPLETE (messages.py:15, :29, :30) and per-envelope Messages.LIST_ITEM (messages.py:18-21).

```
AutoPage(min_width=896, padding=56, gap=32)   898 x ~880 (open, 6 rows)
inner width 784
kit = kit_for_user(envelope.creator_id)   <-- CREATOR's theme, not viewer's

┌────────────────────────────────────────────────────────────────┐
│ ╭──────────╮                                                   │
│ │   红包    │  kit.title_pill("红包", "#3 · 香澄",              │
│ ╰─╴#3 香澄╶╯     pill_width=460, pill_height=57)                │
│                                                                 │
│ HERO  kit.panel(padding=32)          Fixed(784) x Fixed(248)   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 新年快乐                       34px wrap=False ellipsis      │ │
│ │                                                             │ │
│ │   100  Pt      ×10 份             有效期 24 小时             │ │
│ │   80px 34px    34px               22px muted, Frame(end)    │ │
│ │                                                             │ │
│ │ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ▓▓▓▓ ░░░░ ░░░░ ░░░░ ░░░░ ░░░░ ░░░░           │ │
│ │  Grid(columns=n, rows=1, row_track=Fixed(24),               │ │
│ │       column_track=Fixed(seg), gap=6)                        │ │
│ │       seg = (720 - (n-1)*6)//n     [n<=20 only]              │ │
│ │  n>20 -> the two-panel continuous bar from PlayerCard's XP   │ │
│ │  claimed segs fill=primary · unclaimed fill=panel_fill,r=6   │ │
│ │                                                             │ │
│ │ 已领 4/10 份 · 剩余 63 Pt                    24px           │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ LEDGER  kit.panel(padding=Insets.only(30,28,30,24))            │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │  1.  有咲                          38 Pt      手气王         │ │
│ │  2.  彩                            24 Pt                    │ │
│ │  3.  沙绫                          16 Pt                    │ │
│ │▌ 4.  香澄                          12 Pt      刚刚          │ │
│ │     (rows VStack gap=14, each Frame height=Fixed(52),        │ │
│ │      align_y="center", max 8 rows)                          │ │
│ │      HStack(gap=12):                                        │ │
│ │        panel(Fixed(6),Fill(),r=3,fill=primary)  or Spacer(6)│ │
│ │        Frame(rank+name, Fill(), align_x=start, 23px)         │ │
│ │        Frame(amount,  Fixed(120), align="right", 22px)      │ │
│ │        Frame(tag,     Fixed(110), align="right", 22px)      │ │
│ │  ……还有 3 人未领                    22px muted (overflow)    │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ COMPLETION BAND   (state="done" only)   784 x 96               │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 2 分 14 秒被抢完        手气王 有咲 · 38 Pt      24px       │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ state="sealed" (just created): LEDGER panel replaced by         │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │        发送 /抢红包 领取           40px, centered  784x140  │ │
│ └─────────────────────────────────────────────────────────────┘ │
│ state="expired": hero bar all muted, band reads                 │
│ │ 已过期 · 未领取的 37 Pt 已退还给 香澄 │                       │
│                                                                 │
│                                        │ 香澄 的主题 · 霓虹街机 │
└────────────────────────────────────────────────────────────────┘
```

### EnvelopeListCard (plugins/red_envelope/render/board.py :: render_board)  `[P1/M]`
- **插件**：plugins/red_envelope
- **触发**：/红包  (no args — new behaviour; replaces /红包列表 · /查看红包)
- **目的**：Today `红包列表` prints one text line per envelope (red_envelope/__init__.py:265-284) with 'Pt 63/100 | 份数 6/10' — you cannot see at a glance which one is worth racing for. A card with a progress bar per row makes the choice instant, and it lets `红包 <id>` become the drill-down, which is what kills the separate list command.
- **展示数据**：count of active envelopes (get_active_envelopes(channel_id), service.py:100-113), per envelope: channel_index, title, remaining_amount/total_amount, remaining_count/total_count, time to expiry derived from envelope.expires_at, a hint line naming the two follow-up commands
- **主题可见性**：Medium. It is a query surface so it renders in the VIEWER's kit — which is the correct contrast to EnvelopeCard: the same group sees the envelope in the creator's theme and the list in their own, which is exactly the moment the mechanic becomes legible ('wait, why does his look different?'). Three primary-filled progress bars carry the hue.
- **manga 单色降级**：Fine — bars are fill-vs-track and every bar is redundantly labelled with '63/100 Pt'. Row identity is the #id numeral and the title string. Nothing hue-dependent.
- **替代的文本响应**：plugins/red_envelope/__init__.py:265-284 (LIST_HEADER + LIST_ITEM assembly) and messages.py:17-21. The `list_cmd` matcher at red_envelope/__init__.py:53-55 is deleted entirely.

```
AutoPage(min_width=896, padding=56, gap=32)   898 x ~620 (3 rows)
inner width 784 · kit = kit_for_user(viewer)   <-- viewer's theme, it's a query

┌────────────────────────────────────────────────────────────────┐
│ ╭──────────╮                                                   │
│ │   红包    │  kit.title_pill("红包", "本群 3 个进行中",         │
│ ╰╴3个进行中╶╯    pill_width=460, pill_height=57)                │
│                                                                 │
│ kit.panel(padding=Insets.only(32,28,32,28))    784 x ~340      │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ #5  年终奖                       180/300 Pt   3/8 份  剩23时│ │
│ │     ▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░           │ │
│ │                                                             │ │
│ │ #3  新年快乐                      63/100 Pt   6/10份  剩21时│ │
│ │     ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░               │ │
│ │                                                             │ │
│ │ #1  随便发发                        8/50 Pt   9/10份  剩 4时│ │
│ │     ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░              │ │
│ │                                                             │ │
│ │  row = Frame(VStack([hdr, bar], gap=10), height=Fixed(76))  │ │
│ │  rows VStack gap=18, max 6, then '……还有 N 个' 22px muted    │ │
│ │  hdr = HStack(gap=12):                                       │ │
│ │    Frame(#id,   Fixed(56), align_x=start, 23px)             │ │
│ │    Frame(title, Fill(),    align_x=start, 23px, ellipsis)   │ │
│ │    Frame(pt,    Fixed(150),align="right", 22px)             │ │
│ │    Frame(count, Fixed(100),align="right", 22px)             │ │
│ │    Frame(ttl,   Fixed(96), align="right", 22px, muted)      │ │
│ │  bar = Overlay(track Fixed(720)x16 r8 panel_fill,           │ │
│ │                fill  Fixed(720*claimed_pct)x16 r8 primary)  │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  发送 /抢红包 领取最新的一个 · /红包 3 查看战况   22px muted     │
│                                            │ 主题 · 网点纸      │
└────────────────────────────────────────────────────────────────┘
```

### RankCard (plugins/daily/render/rank.py :: render_rank)  `[P0/M]`
- **插件**：plugins/daily
- **触发**：/levelrank · /rank · /排行 · /排行榜 · /等级排行 · /等级排行榜
- **目的**：Today this is ten unformatted lines plus a trailing sentence about your own rank (daily/__init__.py:218-228) — the columns do not align in a proportional chat font, and your own row is prose, not a row. A card gives real columns and pins you as an actual row under a separator, so 'how far am I from #26' becomes a bar you can see.
- **展示数据**：get_top_users(10) -> user_id, level, xp (monetary/ranking_service.py:12-29), nickname.get(user.user_id) or 'Unknown' — same fallback as daily/__init__.py:221, viewer's own rank + xp_gap (get_user_rank, ranking_service.py:32-68), viewer's own level and xp, the gap-to-next bar (visual form of the 'xp_gap' sentence at daily/__init__.py:213-216), explicit ladder name in the subtitle (等级榜)
- **主题可见性**：Medium-high. Ten rows means the panel is large and the kit's corner radius and background dominate the frame. Top-3 badges are the only filled shapes, so the theme's primary reads as 'the podium colour'. Deliberately NO avatars: ten remote fetches would blow the latency budget and add a failure mode the card does not need.
- **manga 单色降级**：Top-3 vs rest is filled-badge vs bare-numeral — a shape/presence difference, not a colour one, so it survives monochrome exactly the way one_stroke's populated-vs-placeholder rows do (leaderboard.py:22-29 uses the same two-signal discipline). The self row is separated by an actual kit.separator rule and prefixed with the word 你, so it is findable without hue. The gap bar carries its own '距上一名 340 XP' label.
- **替代的文本响应**：plugins/daily/__init__.py:218-228 in full — both the joined top-10 line list (:219-224) and the appended rank_message built at :210-216.

```
AutoPage(min_width=896, padding=56, gap=32)   898 x ~1200
inner width 784 · panel padding 32 -> inner 720
Row idiom copied verbatim from one_stroke/render/leaderboard.py:30-67

┌────────────────────────────────────────────────────────────────┐
│ ╭──────────╮                                                   │
│ │  排行榜   │  kit.title_pill("排行榜", "等级榜 · Top 10",       │
│ ╰╴等级榜╶──╯     pill_width=460, pill_height=57)                │
│   (subtitle names the ladder — today's text never says whether  │
│    it ranks level or season Pt; there are two ladders in-repo)  │
│                                                                 │
│ kit.panel(padding=32)                     784 x ~888           │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ ╭──╮                                                        │ │
│ │ │ 1│  香澄                        Lv.42        18,204 XP    │ │
│ │ ╰──╯                                                        │ │
│ │ ╭──╮                                                        │ │
│ │ │ 2│  有咲                        Lv.40        16,880 XP    │ │
│ │ ╰──╯                                                        │ │
│ │ ╭──╮                                                        │ │
│ │ │ 3│  沙绫                        Lv.39        15,102 XP    │ │
│ │ ╰──╯                                                        │ │
│ │   4   彩                          Lv.35        11,940 XP    │ │
│ │   5   莉莎                        Lv.33        10,220 XP    │ │
│ │   6   友希那                      Lv.31         9,015 XP    │ │
│ │   7   蘭                          Lv.30         8,470 XP    │ │
│ │   8   巴                          Lv.28         7,133 XP    │ │
│ │   9   兰                          Lv.27         6,802 XP    │ │
│ │  10   摩卡                        Lv.26         6,240 XP    │ │
│ │                                                             │ │
│ │ ──────── kit.separator(length=Fixed(720)) ────────────      │ │
│ │                                                             │ │
│ │ ╭──╮                                                        │ │
│ │ │27│  你 · 千圣                   Lv.24         1,180 XP    │ │
│ │ ╰──╯                                                        │ │
│ │      距上一名 340 XP  ▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░           │ │
│ │      Overlay(track Fixed(560)x14 r7, fill by 1-gap/ratio)   │ │
│ │                                                             │ │
│ │  row = Frame(HStack([...], gap=12), height=Fixed(52),       │ │
│ │              align_y="center");  rows VStack gap=18          │ │
│ │  [badge] rank 1-3: kit.panel(Frame(txt 30px, center),       │ │
│ │            width=Fixed(56), height=Fixed(52), radius=14,    │ │
│ │            fill=primary), text (255,255,255,255)            │ │
│ │          rank 4+ : Frame(txt 30px muted, width=Fixed(56))   │ │
│ │            — NO panel.  fill-vs-nofill = the only cue diff  │ │
│ │  [name]  Frame(Fill(), align_x=start, 23px, ellipsis)       │ │
│ │  [lv]    Frame(Fixed(96),  align="right", 22px)             │ │
│ │  [xp]    Frame(Fixed(150), align="right", 22px)             │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                            │ 主题 · 云母窗      │
└────────────────────────────────────────────────────────────────┘
```

### TaskCard (plugins/daily_task/render/task.py :: render_task)  `[P1/M]`
- **插件**：plugins/daily_task
- **触发**：/每日任务 · /每日 · /任务
- **目的**：Today the command shows only the one task you were assigned (daily_task/__init__.py:53-65) so nobody learns that a five-task pool exists (tasks.json holds exactly 5: blackjack_win, cck_first_try, guess_chart_easy, mines_cashout_2x, one_stroke_normal_60s). Showing the whole pool with today's highlighted teaches the five games the bot has and gives a reason to come back tomorrow. This is a content-discovery change an image makes free.
- **展示数据**：today's task id/name/description/reward (daily_task_service.task_configs[task.task_id]), task.is_completed and task.completed_at formatted as '%H 时 %M 分' (same as daily_task/__init__.py:50-52), the full 5-entry pool from tasks.json via daily_task_service.get_task_config_list(), which pool row is today's (ink left-rule + 今/完 mark + non-muted description)
- **主题可见性**：Medium. Two panels means the kit silhouette appears twice, and the left rule on today's row plus the 已完成 pill are primary-filled. It is a lower-traffic command than 签到 so it is not carrying the theme story alone — its job is content discovery.
- **manga 单色降级**：Today's row uses THREE redundant cues — a 6px ink rule in the gutter, a CJK mark character (今/完), and un-muted description text — so it is unambiguous with hue fully removed. The 已完成 / 未完成 pill is a word, not a colour. Explicitly no emoji or ✓/★ glyphs: CHINESE_FONT is old.ttf and glyph coverage outside CJK+ASCII is not verified.
- **替代的文本响应**：plugins/daily_task/__init__.py:53-58 (the completed branch) and :60-65 (the incomplete branch), in full.

```
AutoPage(min_width=896, padding=56, gap=32)   898 x ~830
inner width 784

┌────────────────────────────────────────────────────────────────┐
│ ╭──────────╮                                                   │
│ │ 每日任务  │  kit.title_pill("每日任务", "今日 · 概率学博士",    │
│ ╰╴概率学博士╶╯   pill_width=500, pill_height=57)                │
│                                                                 │
│ TODAY  kit.panel(padding=32)         Fixed(784) x Fixed(206)   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 今日任务                              ╭──────────╮          │ │
│ │ 22px muted                            │  已完成   │  24px   │ │
│ │                                       ╰──────────╯          │ │
│ │ 概率学博士                       40px    Fixed(150)x Fixed(52)│ │
│ │ 在黑香澄中赢得一局                24px  wrap=False ellipsis   │ │
│ │                                                             │ │
│ │ 奖励 80 张星星贴纸        完成于 21 时 47 分   22px muted    │ │
│ │  (完成于 … only when task.completed_at, same value as the    │ │
│ │   strftime at daily_task/__init__.py:50-52)                  │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ POOL  kit.panel(padding=Insets.only(30,28,30,24))  784 x ~372  │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 任务池 · 每日随机 1 个              22px muted               │ │
│ │                                                             │ │
│ │▌完  概率学博士   在黑香澄中赢得一局                    80    │ │
│ │     一眼看穿     在猜卡面中第一次猜测就猜中             80    │ │
│ │     太谱达人     在简单/普通难度中猜中一次谱面          80    │ │
│ │     见好就收     在探险中带着≥2倍Pt撤退                80    │ │
│ │     笔走飞星     在普通难度的一笔画中于60秒内通关       80    │ │
│ │                                                             │ │
│ │  row = Frame(HStack([...], gap=12), height=Fixed(56),       │ │
│ │              align_y="center");  rows VStack gap=14          │ │
│ │  [rule] panel(Fixed(6), Fill(), r=3, fill=primary)          │ │
│ │         for TODAY'S row only, else Spacer(width=Fixed(6))   │ │
│ │  [mark] Frame(Fixed(48)): '完' if done, '今' if today &      │ │
│ │         not done, '' otherwise.  24px.  CJK only, no emoji.  │ │
│ │  [name] Frame(Fixed(180), align_x=start, 23px)              │ │
│ │  [desc] Frame(Fill(),     align_x=start, 22px, ellipsis,     │ │
│ │               muted unless it is today's row)                │ │
│ │  [rwd]  Frame(Fixed(90),  align="right", 22px)              │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                            │ 主题 · 深夜巡演    │
└────────────────────────────────────────────────────────────────┘
```

### TransferReceiptCard (plugins/daily/render/transfer.py :: render_receipt)  `[P1/S]`
- **插件**：plugins/daily
- **触发**：/transfer · /转账 <昵称> <金额>
- **目的**：A transfer is the only two-party economic act in the cluster and it happens in public. Today it is one line (daily/__init__.py:191-195). A receipt card makes the handoff legible and — the actual reason to build it — it attaches YOUR theme to a gift you just handed someone. That is the cleanest 'where did you get that' trigger available, because the recipient has a reason to look closely at the image.
- **展示数据**：sender nickname (nickname.get(user_id)), recipient nickname — the exact `to_user_nick` token the sender typed (daily/__init__.py:150-152), amount, sender's balance before and after (monetary.get before the transfer call at :183, and after :189)
- **主题可见性**：High per-impression, low frequency. The card is short so the kit background occupies a large fraction of it, and the 80px amount numeral sits directly on the themed panel. This is the only card in the cluster whose signature line is aimed at a specific second person rather than the room, which is why it uses the owner_name form.
- **manga 单色降级**：Perfect — it is two names, a numeral, a rule and two words. Direction is positional. The only colour is the panel and background chrome. Renders identically well in manga, midnight and neon.
- **替代的文本响应**：plugins/daily/__init__.py:191-195 only (the success finish). All five preceding validation branches (:145-188) stay text — see stays_text.

```
AutoPage(min_width=896, padding=56, gap=32)   898 x ~470  (short card)
inner width 784 · kit = kit_for_user(sender)

┌────────────────────────────────────────────────────────────────┐
│ ╭──────────╮                                                   │
│ │   转账    │  kit.title_pill("转账", "已完成",                  │
│ ╰──╴已完成╶╯     pill_width=420, pill_height=57) -> 460x127     │
│                                                                 │
│ kit.panel(padding=32)                 Fixed(784) x Fixed(212)  │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │                                                             │ │
│ │   香澄                  40 Pt                  有咲         │ │
│ │   34px                  80px                   34px         │ │
│ │   付出                  ────────────           收到          │ │
│ │   22px muted            kit.separator(         22px muted   │ │
│ │                          length=Fixed(220))                 │ │
│ │                                                             │ │
│ │   HStack(gap=24, align="center"):                           │ │
│ │     Frame(VStack([name,'付出'],gap=8,'center'),Fill(),start)│ │
│ │     Frame(VStack([amount,rule],gap=12,'center'),Fixed(280)) │ │
│ │     Frame(VStack([name,'收到'],gap=8,'center'),Fill(),  end)│ │
│ │   direction is carried by POSITION + the words 付出/收到,   │ │
│ │   never by an arrow glyph (no ▶ / → : font risk)            │ │
│ │                                                             │ │
│ │ ──────────────────────────────────────────────────────────  │ │
│ │  你的余额  1,203  ->  1,163                    24px         │ │
│ │  (recipient's balance is NEVER shown — it is not public)    │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                        │ 香澄 的主题 · 樱色     │
└────────────────────────────────────────────────────────────────┘
```

### RewardStrip (plugins/daily_task/render/strip.py :: reward_strip)  `[P1/S]`
- **插件**：plugins/daily_task
- **触发**：(no command — shared Component consumed by other cards)
- **目的**：Kill the standalone reward message. `add_xp` returns a level-up string (monetary/level_service.py:74) and `check_progress` returns a task-completion string (daily_task/service.py:101); between them they are sent as SEPARATE messages at eight call sites. This is a Component, not a page: any result card VStacks it in and the extra message disappears. Without it, every card in this cluster and the game cluster still trails a naked text message and the '1 result = 1 image' goal is not actually met.
- **展示数据**：level-up: old_level, new_level, stickers granted (all three already computed in monetary/level_service.py:67-75, currently only formatted into a string), daily-task completion: task name and reward (daily_task/service.py:99-101), the 7-day check-in bonus row (daily/__init__.py:108-112) reuses the same row shape
- **主题可见性**：Low on its own — that is the point. It is a guest component whose only themed elements are the panel corner and the primary-coloured left rules, so it inherits whatever card hosts it and never fights the host's hierarchy.
- **manga 单色降级**：Rows are an ink rule plus words plus a signed numeral. Nothing to lose in monochrome.
- **替代的文本响应**：The separate sends at plugins/daily/__init__.py:126-130, plugins/mines/__init__.py:271-274 and :280-283, plugins/one_stroke/__init__.py:259-262 and :266-270, plugins/blackjack/handlers.py:453/626/706, plugins/cck/__init__.py:281, plugins/guess_chart/__init__.py:356. The string producers at plugins/monetary/level_service.py:74 and plugins/daily_task/service.py:101 should return structured data instead of a formatted string; keep the string for callers that have no card yet.

```
Not a page. Returns a Component | None (None when both inputs are empty),
intended as a VStack child at inner content width (Fill on the cross axis).

reward_strip(kit, *, levelup=(23, 24, 120), task=("概率学博士", 80))

 kit.panel(padding=Insets.only(28,20,28,20))     Fill() x Fit
┌─────────────────────────────────────────────────────────────┐
│▌ 升级  Lv.23 → Lv.24                      ＋120 星星贴纸     │
│▌ 每日任务【概率学博士】完成                 ＋80 星星贴纸      │
└─────────────────────────────────────────────────────────────┘

 row = Frame(HStack([...], gap=12), height=Fixed(56), align_y="center")
 rows = VStack(row_list, gap=12, align="stretch")
   [rule]  kit.panel(width=Fixed(6), height=Fill(), radius=3,
                     fill=getattr(kit,"primary",kit.text_color))
   [label] Frame(kit.text(txt, font_size=24, wrap=False, max_lines=1,
                          overflow="ellipsis"),
                 width=Fill(), align_x="start", align_y="center")
   [value] Frame(kit.text(val, font_size=24, align="right",
                          wrap=False, max_lines=1),
                 width=Fixed(230), align_x="stretch", align_y="center")

 Text is CJK + ASCII only.  '＋' is fullwidth plus (U+FF0B), which IS in
 old.ttf's CJK block — the current strings' 🎉 (daily/__init__.py:111,
 level_service.py:74) is NOT and must be dropped.
```

---

## 交互改动

### plugins/daily
- **现在**：Check-in emits up to three messages: `matcher.send(msg)` with reward + streak + bonus + task + mail count, then `matcher.send(level_msg)` if the user levelled, then an empty `matcher.finish(referrer=...)` (daily/__init__.py:123-131).
- **改为**：One `CheckinCard` image + the PassiveGenerator element, one send. Level-up and the 7-day bonus become `RewardStrip` rows inside it; the mail count becomes a conditional row; the offseason warning becomes a row instead of a string concatenation.
- **为什么更好**：Three notifications for one action is the single worst pattern in the cluster and it happens to every player every day. Collapsing it also fixes an ordering artefact: today the level-up arrives AFTER the check-in text, so the XP number in the first message is already stale. In the card the XP bar and the level are rendered from the post-add state, so they agree.

### plugins/daily
- **现在**：Running 签到 twice finishes with the bare string `今天已经签到过了` (daily/__init__.py:83-86) — a dead end that shows nothing.
- **改为**：Renders the same `CheckinCard` in `state="already"`: no reward numeral, but the streak strip, today's task state, and balances are all there.
- **为什么更好**：Re-running 签到 is the natural gesture for 'show me my streak', and check-in is structurally once-per-day-per-user so this is not a spammable surface (unlike 抢红包). It converts a refusal into the cluster's second-best status card at zero new command cost. This is the one place I am deliberately overriding the 'errors stay text' rule, and the justification is frequency: the duplicate path fires at most a handful of times per user per day.

### plugins/red_envelope
- **现在**：`红包` is an alias of the CREATE command (red_envelope/__init__.py:51), so `/红包` with no args returns `CREATE_USAGE`, and `/红包 3` also returns `CREATE_USAGE` because `len(parts) < 2` (:92-97). Listing is a third command, `红包列表`/`查看红包` (:53-55).
- **改为**：`/红包` (no args) -> `EnvelopeListCard`. `/红包 <int>` -> `EnvelopeCard` for that envelope. `/发红包 <标题> <金额> <份数>` remains the only create form. `红包列表` and `查看红包` are deleted.
- **为什么更好**：Both repurposed forms are TODAY pure error paths (verified: zero args and one arg both fall through to CREATE_USAGE), so this breaks nothing that currently works, and it removes a genuinely bad affordance where the most obvious noun in the plugin returns a usage error. Once the envelope is a card, 'look at the envelope' is the dominant verb and it deserves the short name; create is the rarer act and keeps the explicit 发 prefix.
- **移除命令**：/红包列表 · /查看红包 (red_envelope/__init__.py:53-55, handler :251-284)
- **新增命令**：/红包 (no args) and /红包 <id> as query forms

### plugins/red_envelope
- **现在**：Every claim sends `恭喜你抢到 {amount} 个Pt！` (red_envelope/__init__.py:217-222) — private-feeling, and identical ten times in a row. The completion summary is a SECOND message right after (:225-238).
- **改为**：A claim replies with `EnvelopeCard` in `state="open"` — the whole ledger, the claimer's own row marked 刚刚 — or `state="done"` on the final claim, with the 手气王 and duration in the completion band. Two messages become one; ten identical texts become ten images that each show the race advancing.
- **为什么更好**：The claim race is the only genuinely multiplayer moment the bot has and today it is invisible: you learn your number and nothing else. The ledger makes it a spectacle, which is exactly the 'shared surface' the theme signature was designed for. It also fixes a real information gap — today nobody except the last claimer ever learns the 手气王.

### plugins/red_envelope
- **现在**：n/a — the claim reply is unconditionally one text message.
- **改为**：The card reply is throttled: render `EnvelopeCard` on a claim only when `envelope.total_count <= 12` OR the claim is the final one (`remaining_count == 0`). Above 12, reply with a compact text `抢到 12 Pt · 第 37/200 份 · /红包 3 查看战况` and render only the completion card.
- **为什么更好**：`MAX_ENVELOPE_COUNT = 10_000` (service.py:26) and `count > 10000` is the only guard (red_envelope/__init__.py:119). A 200-part envelope would mean 200 renders at 25-101 ms each plus 200 uploads. This rule keeps the spectacle exactly where it is a spectacle (small envelopes, and the finale) and stays text where the race is a grind. It is also why the `/红包 <id>` query form must exist — it is the escape hatch for big envelopes.

### plugins/red_envelope
- **现在**：`你已经领过这个红包了` (red_envelope/__init__.py:207-211, messages.py:25) — a dead end containing no information.
- **改为**：Stays TEXT, but enriched with the data the handler already has: `你已经领过 3 号红包（12 Pt，当前第 2 名）· 发送 /红包 3 查看战况`.
- **为什么更好**：This is the most-spammed path in the plugin — people mash 抢红包 during a race — so it must NOT render. But a refusal that answers the question behind the mash ('did I get a good one?') and points at the card is strictly better than a wall. Deliberately the counter-example to the 签到-already change above: same shape of decision, opposite answer, and the deciding factor is burst frequency.

### plugins/red_envelope
- **现在**：n/a — envelopes have no visual identity at all.
- **改为**：`EnvelopeCard` renders in `kit_for_user(envelope.creator_id)`, not the viewer's kit. `EnvelopeListCard` renders in the viewer's kit.
- **为什么更好**：It makes 发红包 a broadcast of your theme to an entire group — you attach your identity to currency you are handing out, which is the strongest possible version of 'other players can be like where did u get that'. The list/query surface staying in the viewer's kit is what makes the difference readable: the same person sees two red-envelope cards in one scroll that look nothing alike, which is how they learn themes exist. Requires the footer to use the `owner_name` form of `theme_signature` (`香澄 的主题 · 霓虹街机`) so nobody mistakes it for their own.

### plugins/daily_task
- **现在**：`/每日任务` shows only the one randomly-assigned task (daily_task/__init__.py:53-65). The other four entries in tasks.json are invisible.
- **改为**：`TaskCard` shows today's task in a hero panel plus the full 5-entry pool below, with today's row marked and the rest muted.
- **为什么更好**：The pool is fixed at five and hand-authored (tasks.json), so this is a complete, non-paginating list forever — the same argument the theme gallery uses. It doubles as a games directory: each pool row names a game (黑香澄 / 猜卡面 / 猜谱面 / 探险 / 一笔画), so a player who only knows one game discovers four. Zero new data, zero new command.

### plugins/daily
- **现在**：Player state is scattered across three commands: `/info` gives level+XP+Pt+stickers (daily/__init__.py:59-66), `/排行榜` gives rank as a trailing sentence (:210-216), `/每日任务` gives the task (daily_task/__init__.py:53-65). Bonsai is not shown anywhere.
- **改为**：`PlayerCard` is one surface carrying identity (avatar + equipped frame + equipped title + description), all three currencies including 盆栽, XP bar, streak, rank and today's task state. The dedicated commands survive as the drill-downs.
- **为什么更好**：This is the card that has to answer 'where did you get that'. It only works if the cosmetics are all on it at once — a theme is not desirable next to a bare number, it is desirable next to a frame and a title in a coherent layout. Surfacing 盆栽 also fixes a live dead-end noted in the theme foundation: duplicates pay out a currency the player currently never sees.

### plugins/daily_task
- **现在**：`check_progress` returns a formatted string (daily_task/service.py:101) and `add_xp` returns another (monetary/level_service.py:74); eight call sites send each as its own message right after the game's own result message (mines/__init__.py:271-274 and :280-283, one_stroke/__init__.py:259-262 and :266-270, blackjack/handlers.py:453/626/706, cck/__init__.py:281, guess_chart/__init__.py:356).
- **改为**：Both return structured data; `RewardStrip` renders them as rows that a result card VStacks in. Standalone text remains only for call sites that have no result card yet.
- **为什么更好**：Otherwise every beautiful themed result card in the repo is still followed by two naked grey text messages, and the '1 action = 1 image' promise is broken by the two plugins that are supposed to reward you. This is the change that makes the economy cluster's work visible in the GAME cluster's output. Cross-cluster: the economy side owns the component and the data shape; each game cluster owns the embed. Flag it explicitly so the two designs do not both build a level-up banner.

### plugins/daily
- **现在**：`/排行榜` prints ten `{i}. {name}: Lv.{level} (XP: {xp})` lines with no column alignment, then appends `你当前的排名是第 N 名，离上一名还差 M XP` as prose (daily/__init__.py:218-228). It never states which ladder it is.
- **改为**：`RankCard` with real columns, top-3 as filled badges, and the viewer pinned as an actual row below a `kit.separator`, with the XP gap drawn as a bar. Subtitle reads `等级榜 · Top 10`.
- **为什么更好**：Alignment is the whole value of a leaderboard and proportional chat fonts destroy it. Pinning the self row below a rule makes 'how close am I' a spatial question instead of a sentence to parse. Naming the ladder matters because the repo has two — this one ranks by level/xp (ranking_service.py:23-28) while inventory's `get_active_ranking` ranks by season Pt; the current text lets a player conflate them.

---

## 保留为文本
- **plugins/daily** — All five transfer validation failures: format error (daily/__init__.py:145-148), non-numeric amount (:158-161), unknown nickname `Kasumi 不认识{nick}呢...` (:166-169), self-transfer (:172-175), amount <= 0 (:177-181), insufficient balance `余额不足！` (:183-187).：Every one is a typo the user must retype in the next second. Spending 25-101 ms plus an image upload to say '余额不足' is strictly worse than a line of text — and the insufficient-balance message should be enriched with the actual numbers instead (it currently omits them, unlike the envelope version at messages.py:13).
- **plugins/daily** — `/balanceset` / `/设置余额`: the success line (daily/__init__.py:248-251), the parse-failure line (:253-257), and the silent finish for non-superusers (:238).：SUPERUSER-only administrative tooling with an audience of one. There is no onlooker to impress and no state worth composing; an image would just slow down debugging.
- **plugins/red_envelope** — `NOT_IN_CHANNEL` (messages.py:2, sent at __init__.py:87, :169, :255).：A capability refusal in a DM. There is no envelope, no group and no audience — there is literally nothing to draw.
- **plugins/red_envelope** — All six create-time validations: `CREATE_USAGE` (__init__.py:94-97 and :104-107), `INVALID_AMOUNT` (:110-113), `INVALID_COUNT` (:114-118), `MAX_COUNT_EXCEEDED` (:119-123), `AMOUNT_TOO_SMALL` (:124-128), `INSUFFICIENT_BALANCE` (:130-136).：Same as the transfer errors: pre-transaction input rejection, retyped immediately. `INSUFFICIENT_BALANCE` already interpolates the balance (messages.py:13), which is the whole payload.
- **plugins/red_envelope** — `CREATE_FAILED` with an error code (__init__.py:156-161) and `CLAIM_FAILED` with an error code (:212-216, :243-248).：These fire when the renderer's own dependencies may be the thing that is broken. An error path that needs a working render pipeline to report a failure is a second failure waiting to happen. Text also keeps the error code copy-pasteable, which is the entire point of `generate_error_code`.
- **plugins/red_envelope** — `CLAIM_USAGE` (__init__.py:177-180), `CLAIM_NO_ACTIVE` (:188-191), `CLAIM_NOT_FOUND` (:192-196), `CLAIM_EXPIRED` (:197-201), `CLAIM_EMPTY` (:202-206), `CLAIM_ALREADY` (:207-211), `LIST_EMPTY` (:260-263).：All are latency-sensitive negatives fired during a claim race, when many people are mashing the command at once — precisely the burst where rendering is most expensive and least wanted. `CLAIM_ALREADY` and `CLAIM_EXPIRED` should be ENRICHED as text (amount + current rank, refund amount + recipient) and point at `/红包 <id>`, which is where the card lives.
- **plugins/red_envelope** — The claim acknowledgement itself when `envelope.total_count > 12` and the envelope is not yet complete — a compact `抢到 12 Pt · 第 37/200 份 · /红包 3 查看战况`.：`MAX_ENVELOPE_COUNT` is 10,000 (service.py:26). Rendering a board per claim on a large envelope is a self-inflicted DoS. The finale still gets a card, so the spectacle is preserved where it matters.
- **plugins/daily_task** — `任务系统暂时不可用` (daily_task/__init__.py:33-36) and `任务配置异常` (:40-43).：Both mean the task subsystem failed to load config or assign a row. Composing a card that reports the config is broken, using a pipeline that reads config, is the wrong dependency direction.
- **plugins/monetary** — Everything — plugins/monetary registers no matchers at all (monetary/__init__.py has only the `init()` startup hook and re-exports).：It is a service library, not a response surface. Listed here so the cluster's plugin count is not misread: monetary supplies the DATA for PlayerCard, CheckinCard and RankCard (get_user, get_balance, get_star_stickers, get_top_users, get_user_rank, xp_to_next_level, total_xp_for_level, is_using_offseason_points) and needs no renderer of its own. The only change it should absorb is returning structured level-up data instead of a pre-formatted string (level_service.py:74).

---

## 风险
- EMOJI WILL RENDER AS TOFU. The current strings contain 🎉 at plugins/daily/__init__.py:111 and plugins/monetary/level_service.py:74, and 📬-style decoration is tempting for the mail row. `CHINESE_FONT` is `old.ttf` (plugins/render/kits/fonts.py) and `load_font` silently falls back to PIL's default on OSError (primitives.py:31-49) — a missing glyph does NOT raise, it draws a box. Every string that moves into a card must be audited to CJK + ASCII, and I avoided ✓ ★ ▶ → in all eight designs for the same reason. Verify the actual glyph coverage of old.ttf before shipping anything with a non-CJK symbol.
- RED ENVELOPE CLAIM STORM. `MAX_ENVELOPE_COUNT = 10_000` (red_envelope/service.py:26) and the handler only rejects `count > 10000` (__init__.py:119). Without the `total_count <= 12` throttle, a 200-part envelope becomes 200 renders and 200 uploads on a hot path. Even with the throttle, a 12-part envelope in a fast group is 12 renders inside a minute — all of them must go through `await page.render_async()` (layout.py:82-100), and the bangdream image background at 0.25 s (vs 0.08 s for the tiled one) must NOT be used on this card.
- CLAIM_ENVELOPE DOES NOT RETURN ENOUGH DATA. `claim_envelope` returns `(status, amount, completion_info)` (service.py:157-249) and never returns the envelope or the claim ledger. EnvelopeCard needs `RedEnvelope` plus its `ClaimRecord` rows (the `claims` relationship exists at models.py:31-33 but no service function exposes it). This is a required service change, and it must not be done by touching `envelope.claims` lazily on a detached instance — add an explicit `get_envelope_view(channel_id, index) -> EnvelopeView` that loads both in one place.
- AVATAR FETCHING IS A NETWORK CALL. PlayerCard and any avatar on TransferReceiptCard depend on `get_group_member_head` (plugins/bang_avatar/utils.py), which is an aiohttp request. It must be awaited on the event loop before the render, must have a timeout, and must degrade to a placeholder panel — a render that blocks on a dead CDN turns /info into a hang. RankCard deliberately has no avatars for exactly this reason.
- SESSION THREAD SAFETY. `plugins/monetary/database.py:21-52` exposes one module-global `Session` shared process-wide, same as inventory's. `render_async` offloads to a thread pool. Every ORM read (get_user, get_top_users, get_user_rank, get_active_envelopes, get_today_task, kit_for_user) must complete on the event-loop thread and be passed into the renderer as plain values or a frozen dataclass. No renderer in this cluster may accept a live ORM object it might lazily refresh.
- LATENT BUG THE CHECKIN CARD DEPENDS ON. `handle_daily` mutates `user.last_daily_time` (daily/__init__.py:92) and `user.consecutive_checkins` (:100) and never calls `session.commit()`. It only persists because `add_xp` commits the same global session (level_service.py:65). If the card's refactor reorders those calls — e.g. rendering before add_xp, or making add_xp conditional — the streak silently stops persisting. Add an explicit commit as part of this work.
- TWO LADDERS, ONE WORD. `/排行榜` ranks by level/xp (ranking_service.py:12-29) while `inventory.get_active_ranking` ranks by season Pt (season_service.py:196). Once RankCard is a polished image it will read as THE ranking. The subtitle must name the ladder, and the season ladder needs its own card before this one ships or players will mis-attribute season rewards.
- CREATOR-KIT RENDERING IS CONFUSING IF THE SIGNATURE IS SUPPRESSED. EnvelopeCard renders in the creator's theme, but `signature_for` returns None for starter themes (theme_default / theme_minimal). A creator on bangdream produces a card that looks exactly like the viewer's own bangdream card with no attribution — harmless. But a creator on a paid theme with the signature present is the case that must always show `香澄 的主题 · …`; if that suppression rule ever changes to hide non-starter signatures on shared surfaces, the card becomes actively misleading. Wire the owner_name form explicitly rather than relying on the default.
- COMMAND ALIAS SURGERY. Repurposing `红包` from a create alias (red_envelope/__init__.py:51) to a query verb is safe today because both `红包` and `红包 <int>` currently fall through to CREATE_USAGE — but the two matchers must be split carefully, since `on_command("发红包", aliases={"红包"})` and a new `on_command("红包")` at the same priority 10 will race. Give the query matcher a distinct priority and a rule that rejects the 2+-argument form.
- CARD HEIGHT. RankCard measures roughly 898 x 1200 and PlayerCard 898 x ~1010. Nothing in-tree is that tall — the tallest existing surface is the 898x987 mines board. Chat clients downscale by WIDTH, so a tall portrait card keeps its 22-24px body text legible, but it also eats a lot of scrollback. If it reads as too heavy in practice, drop RankCard's top-10 to top-8 (2 rows x 70px saved) before shrinking any font — 22px is the hard floor.
- SEGMENTED PROGRESS BAR ARITHMETIC. `seg = (720 - (n-1)*6)//n` leaves up to n-1 px of slack (n=10 gives 714 of 720). Grid pins Fixed tracks and will not stretch, so the bar sits 6px short inside a stretch-aligned parent. Wrap it in `Frame(..., width=Fixed(720), align_x="start")` so the shortfall lands on one side deterministically instead of drifting per envelope size.
- SHARED-COMPONENT OWNERSHIP. `RewardStrip` is designed here but consumed by blackjack, mines, one_stroke, cck and guess_chart. If the game cluster's design also invents a level-up banner, there will be two. It must live in `plugins/daily_task/render/strip.py` (or `utils/cards.py`) and be named in both cluster designs, and `level_service.add_xp` / `daily_task.check_progress` must keep returning their current strings until every caller is migrated.
