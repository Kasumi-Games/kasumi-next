# 插件簇：mailbox

涉及插件：plugins/mailbox

卡片 5 张 · 交互改动 8 项 · 保留文本 7 项

---

## 卡片设计

### InboxCard — plugins/mailbox/render/inbox.py::render_inbox(mails, kit=None)  `[P0/M]`
- **插件**：plugins/mailbox
- **触发**：/邮箱 · /邮件 · /mail (no argument)
- **目的**：The single scannable inbox. Replaces the numbered text list AND its "发送 '邮件 <编号>' 查看详情" hint. Auto-densifies from 2-line to 1-line rows past 8 mails so there is never a page 2 and no pagination command is ever needed. Also absorbs the empty-inbox reply so /邮箱 is image-shaped 100% of the time — this is the cluster's highest-frequency surface and therefore the primary place the theme is felt.
- **展示数据**：ordinal index (the argument /邮件 <n> takes), read / unread state (inverted chip vs bare numeral), mail.title (26px, 1 line, ellipsis), attachments joined via display_item_amount(item_id, quantity) — e.g. 赛季积分 x100Pt · 星星贴纸 x50张, 「已领取」 replacing the attachment line once mail.is_read, 「通知」 replacing the attachment line when mail.attachments is empty, days remaining until mail.expire_time (剩 N 天 / 明天到期 / 今天到期), unread-with-rewards count and total count in the header subtitle, footer affordances: /邮件 <编号>, /邮件 领取
- **主题可见性**：Highest-traffic surface in the cluster, so it is where the theme is felt most. Three simultaneous signals: (1) full-bleed kit.background() fills 898x1136 — midnight's star scatter, neon's grid/horizon, sakura's petals, sailing's waves, manga's screentone all read at a glance; (2) one large panel whose corner radius is the kit's own default (radius= omitted deliberately) — 48 bangdream vs 8 fluent vs 10 neon is a ~40px silhouette difference on a 784px-wide box; (3) up to 8 inverted number chips repeat the kit's text_color/panel_fill pair down the left edge, turning the palette into a rhythm rather than a single accent. In a group chat this is the card most likely to be scrolled past by a third party, which is exactly why the footer signature line lives here.
- **manga 单色降级**：Nothing in this card carries meaning by hue. Unread chip = solid (18,18,20) ink block with a (255,255,255,242) numeral — the highest-contrast element on the page in manga, and arguably the clearest of all eight kits. Read rows collapse to muted (112,112,118) with the value column emptied to the literal word 「已领取」 — two signals, the leaderboard.py:22-29 pattern. The single hard-coded colour, the (234,78,116) expiry pill, is a mid-grey block after monochrome downscale, but it is redundantly cued by a filled pill silhouette, a ● glyph, and the literal word 「到期」, so it still reads as an alarm.
- **替代的文本响应**：__init__.py:110-113 ("你的邮箱是空的呢~") and __init__.py:131-137 (the numbered list built at 115-129 plus the escape_text hint at 134). Kills the only use of escape_text() (__init__.py:47-53) on this path and removes the satori-markup injection surface on the unescaped mail.title at line 128.

```
AutoPage(min_width=896, padding=56, background=kit.background())  ->  898 x ~1136 px
root VStack(gap=32, align="stretch")   inner content width = 784

|<------------------------------- 784 -------------------------------->|
╭────────────────────────╮
│  邮箱                   │   3 封未领取 · 共 7 封          <- response_card header
╰────────────────────────╯                                    (BD: title_pill 500x57 -> measures 548x127)
                                                              (others: two-tier, title 34 / subtitle 24,
                                                               wrapped Frame(align_x="start"))
┌──────────────────────────────────────────────────────────────────────┐
│  kit.panel(radius OMITTED, padding=32)          content width = 720  │
│                                                                      │
│  ┏━━━━┓                                                    ┌───────┐ │  ROW A (unread, has items)
│  ┃    ┃  维护补偿                                          │剩 5 天│ │  Frame h=Fixed(76) align_y=center
│  ┃ 1  ┃  赛季积分 x100Pt · 星星贴纸 x50张                   └───────┘ │  HStack(gap=18)
│  ┗━━━━┛                                                              │   [ chip Fixed(64x64) ]
│   ^64px  ^ title 26px, wrap=False, max_lines=1, ellipsis     ^ 24px   │   [ VStack Fill()  gap=4 ]
│          ^ meta  22px, kit.text_color                       Fixed(140)│   [ Frame Fixed(140) align=end ]
│                                                                      │
│                                     gap=18                           │
│                                                                      │
│  ┏━━━━┓                                                  ┏━━━━━━━━━┓ │  ROW B (unread, expiring <48h)
│  ┃ 2  ┃  扬帆赛季开启                                     ┃●明天到期┃ │  expiry pill: fill (234,78,116,255)
│  ┗━━━━┛  扬帆主题 · 赛季积分 x500Pt                        ┗━━━━━━━━━┛ │  text (255,255,255,255) 22px
│                                                                      │  + literal word 「到期」 + ● dot
│                                                                      │
│    3     七日签到奖励                                        剩 2 天  │  ROW C (already claimed)
│          已领取                                                      │  NO chip box at all.
│    ^ bare numeral 30px in kit.muted_text_color               ^ muted │  all three strings muted.
│                                                                      │  (leaderboard.py:22-29 idiom:
│                                                                      │   muted colour + emptied value)
│    4     赛季公告                                            剩 6 天  │  ROW D (announcement, no items)
│          通知                                                        │  meta literal = 「通知」
│                                                                      │
│  ...up to 8 two-line rows...                                         │
└──────────────────────────────────────────────────────────────────────┘
         │ 主题 · 霓虹街机                                              <- signature_for(kit), right-aligned,
                                                                          suppressed on starter themes

footer="/邮件 <编号> 查看 · /邮件 领取 一键领取"   22px muted

─────────────────── DENSE VARIANT: len(mails) > 8 ───────────────────
row becomes Frame(h=Fixed(52)), single line, chip shrinks to Fixed(44):

│  ┏━━┓ 维护补偿                       赛季积分 x100Pt +1     剩 5 天  │
│  ┃1 ┃ ^24px                         ^22px muted, Fixed(240) ^Fixed(120)
│  ┗━━┛
│   2   七日签到奖励                   已领取                 剩 2 天  │

24 rows max; row 24 becomes  "还有 6 封 · 已按到期时间排序"

─────────────────── EMPTY VARIANT: mails == [] ───────────────────
│  kit.panel(padding=56)                                              │
│                                                                     │
│              ┌───────────────────────────────────┐                  │
│              │   邮箱是空的                       │  34px centred    │
│              │   有新邮件时这里会出现提醒          │  24px muted      │
│              └───────────────────────────────────┘                  │
│                        panel height Fixed(240)                      │
subtitle becomes "0 封", footer omitted. ~8 components total, ~40 ms.

CHIP SPEC (theme-invariant, zero hue):
  unread : kit.panel(Frame(kit.text(str(i), font_size=30, color=kit.panel_fill,
                                     align="center", max_lines=1),
                            align_x="center", align_y="center"),
                     width=Fixed(64), height=Fixed(64),
                     fill=kit.text_color, radius=16)
  read   : Frame(kit.text(str(i), font_size=30, color=kit.muted_text_color,
                          align="center", max_lines=1),
                 width=Fixed(64), height=Fixed(64), align_x="center", align_y="center")
  -> inverted-fill vs bare-numeral is a SHAPE difference, legible in every kit.
```

### MailDetailCard — plugins/mailbox/render/mail.py::render_mail(mail, results, kit=None)  `[P0/M]`
- **插件**：plugins/mailbox
- **触发**：/邮件 <编号>
- **目的**：One card for what is currently one string assembled from three logically separate blocks: the metadata header (lines 195-198), the body (line 199), and the grant results appended last (lines 178-190). Today the reward — the emotional payload — is the last thing in a text wall. Here it is a dedicated panel of big numerals below the letter, so the payoff leads visually while the announcement is still fully readable.
- **展示数据**：mail.title (34px, up to 2 lines), mail.sender_id, mail.created_at, mail.expire_time in one 22px muted meta line, mail.content, wrapped at 26px, capped at 24 lines, per-attachment GrantResult.granted as a 48px numeral, item name + currency unit_name from display_item_amount, 「本次领取」 vs 「已领取」 band state, 「已有」 tiles for GrantResult.skipped, stable mail code #M<id> in the header subtitle, days remaining
- **主题可见性**：This is the card where the kit's *typography* surface is largest — a real paragraph of body text at 26px on a themed panel means text_color and panel_fill do the work rather than chrome. The reward tiles are the strongest silhouette moment: 1-3 panels repeating the kit corner radius side by side inside a parent panel, where a 48px bangdream corner and an 8px fluent corner sit directly next to each other for comparison. A third party sees a letter, not a chat message, which is the whole point.
- **manga 单色降级**：Zero hard-coded colour in this card. The tile inset is mix_color(panel_fill -> text_color, 0.08), which in manga is white-toward-ink = a light grey card on a white panel, exactly the flat-tone look the kit is going for; in midnight/neon it lightens the dark panel instead. Reward vs skipped is signalled by tile fill AND by muted text AND by the numeral being replaced by the word 「已有」 — three signals, all monochrome-safe. The separator uses MangaKit's own primary (18,18,20) so it is a solid ink rule.
- **替代的文本响应**：__init__.py:203 (await mailbox_cmd.finish(content, ...)), which absorbs the reward_message built at 178-190 and the metadata/content string built at 194-201.

```
AutoPage(min_width=896, padding=56, background=kit.background())  ->  898 x ~1010 px
root VStack(gap=32, align="stretch")

╭────────────────────────╮
│  邮件                   │   第 2 封 · #M42 · 剩 5 天
╰────────────────────────╯

┌──────────────────────────────────────────────────────────────────────┐  LETTER PANEL
│  kit.panel(radius OMITTED, padding=32)          content width = 720  │
│                                                                      │
│  维护补偿                                                            │  34px, wrap=True, max_lines=2
│                                                                      │
│  ──────────────────────────────────────────────────────────────────  │  kit.separator(thickness=2,
│                                                                      │    length=None -> fills 720)
│  系统 · 2026-07-24 18:00 送达 · 2026-07-31 18:00 过期                │  22px kit.muted_text_color
│                                                                      │  wrap=False, max_lines=1
│                                                gap 24                │
│  感谢大家的耐心等待，本次维护已经全部完成。作为补偿，我们为所有       │  26px, line_height 36,
│  玩家准备了以下奖励，请注意在 5 天内领取，过期后将无法补发。          │  wrap=True, max_lines=24,
│                                                                      │  overflow="ellipsis"
│  祝各位游戏愉快。                                                    │  color=kit.text_color
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                                gap 32
┌──────────────────────────────────────────────────────────────────────┐  REWARD PANEL
│  kit.panel(radius OMITTED, padding=32)                               │  omitted entirely when
│                                                                      │  mail.attachments == []
│  本次领取                                                     2 项   │  24px text_color | 22px muted
│                                        gap 24                        │  ^ band text is one of:
│                                                                      │    「本次领取」 any r.granted>0
│  ┌──────────────────┐  ┌──────────────────┐                          │    「已领取」  all r.skipped
│  │                  │  │                  │   Grid(columns=3,        │
│  │      100         │  │       50         │        column_track=     │  TILE 228x140,
│  │                  │  │                  │        Fixed(228),       │  kit.panel(fill=_tile_fill(kit),
│  │   赛季积分  Pt    │  │   星星贴纸  张    │        row_track=        │        radius OMITTED)
│  └──────────────────┘  └──────────────────┘        Fixed(140),       │  _tile_fill = mix_color(
│      ^ 48px numeral, align="center"                gap=18)           │    normalize_color(kit.panel_fill),
│      ^ 24px name + unit, muted, wrap=False         wrapped in        │    normalize_color(kit.text_color),
│                                                    Frame(align_x=    │    0.08)  -> visible inset in all 8,
│                                                          "center")   │       incl. minimal (245->232) and
│                                                                      │       midnight (dark->lighter)
│  NON-STACKABLE VARIANT (a theme / frame / title — display_item_amount│
│  returns just the name when quantity==1 and not stackable):          │
│  ┌──────────────────┐                                                │
│  │      获得         │  <- 24px muted where the numeral would be     │
│  │    扬帆主题       │  <- 30px name, wrap=True, max_lines=2         │
│  └──────────────────┘                                                │
│                                                                      │
│  SKIPPED VARIANT (GrantResult.skipped, service.py:185-190):          │
│  tile drawn with fill=kit.panel_fill (no mix) and every string in    │
│  kit.muted_text_color, numeral replaced by the word 「已有」          │
└──────────────────────────────────────────────────────────────────────┘
         │ 主题 · 网点纸

footer="/邮箱 返回列表"
```

### ClaimAllCard — plugins/mailbox/render/claim.py::render_claim_all(claimed, totals, remaining_notices, kit=None)  `[P0/M]`
- **插件**：plugins/mailbox
- **触发**：/邮件 领取 (NEW subcommand)
- **目的**：The flagship. Today claiming 4 mails costs 4 commands and produces 4 text walls, and every one of those commands re-runs get_user_mails() which lazily inserts broadcast recipient rows (service.py:196-217) and re-sorts by created_at desc (service.py:241) — so a broadcast arriving mid-sequence shifts every index and you claim the wrong mail. One command, one card, one aggregated haul: fewer messages, no index race, and a single screenshot-worthy reward image instead of four forgettable ones.
- **展示数据**：number of mails claimed, aggregated granted quantity per item_id, as 48px numerals, item names + unit_name, per-mail breakdown: stable code, title, its own attachment list, count of remaining unread announcement-only mails, 「之前已发放」 state when all results are skipped
- **主题可见性**：The hero grid is 3-4 kit panels in a row inside a parent kit panel — the single densest concentration of kit silhouette anywhere in the bot. This is the card a player screenshots. It is also short (~880px), portrait, and dominated by large numerals, so it survives client downscale better than any other card in the cluster and is the most likely to make a bystander ask about the theme.
- **manga 单色降级**：No hue anywhere. Tiles use the mix_color inset, numerals use kit.text_color, labels use kit.muted_text_color. In manga the hero reads as 3-4 light-grey blocks with heavy ink numerals on a screentone page — the strongest composition of the eight. Skipped/already-claimed tiles differ by fill AND by the numeral being replaced with a word, so nothing is lost.
- **替代的文本响应**：Nothing directly — this is a new command. It removes ~90% of the traffic to __init__.py:203 (per-mail detail) and to the __init__.py:145-148 / 208-211 index errors, because the common case no longer requires typing an index at all.

```
AutoPage(min_width=896, padding=56, background=kit.background())  ->  898 x ~880 px
root VStack(gap=32, align="stretch")

╭────────────────────────╮
│  邮箱                   │   一键领取 · 4 封
╰────────────────────────╯

┌──────────────────────────────────────────────────────────────────────┐  HERO PANEL
│  kit.panel(radius OMITTED, padding=32)          content width = 720  │
│                                                                      │
│  合计获得                                                     4 项   │  24px | 22px muted
│                                        gap 24                        │
│  ┌──────────────────┐┌──────────────────┐┌──────────────────┐        │  Grid(columns=3,
│  │                  ││                  ││                  │        │       column_track=Fixed(228),
│  │      720         ││      170         ││      获得        │        │       row_track=Fixed(140),
│  │                  ││                  ││                  │        │       gap=18)
│  │   赛季积分  Pt    ││   星星贴纸  张    ││    扬帆主题      │        │  wrapped in Frame(align_x="center")
│  └──────────────────┘└──────────────────┘└──────────────────┘        │  -> 1 or 2 tiles centre;
│  ┌──────────────────┐                                                │     4+ tiles wrap to row 2
│  │      获得         │      SAME _reward_tile() helper as             │
│  │  扬帆冠军头像框    │      MailDetailCard — one implementation      │  totals[item_id] = sum of
│  └──────────────────┘                                                │  GrantResult.granted across mails
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                                gap 32
┌──────────────────────────────────────────────────────────────────────┐  DETAIL PANEL
│  kit.panel(radius OMITTED, padding=32)                               │
│                                                                      │
│  明细                                                                │  24px
│                                        gap 18                        │
│  M42   维护补偿              赛季积分 x100Pt · 星星贴纸 x50张         │  row Frame h=Fixed(44)
│  M41   扬帆赛季开启           扬帆主题 · 赛季积分 x500Pt              │  HStack(gap=18):
│  M39   七日签到奖励           星星贴纸 x120张                         │   Frame(code,  Fixed(72))  22px muted
│  M38   活动金奖              赛季积分 x120Pt · 扬帆冠军头像框          │   Frame(title, Fixed(232)) 24px text
│  ^72   ^232                  ^ Fill(), 22px muted, 1 line, ellipsis  │   Frame(items, Fill())     22px muted
│                                                                      │
│  ──────────────────────────────────────────────────────────────────  │  kit.separator, only present
│                                                                      │  when notices remain
│  还有 2 封通知未读 · /邮箱 查看                                       │  22px muted
│                                                                      │  claim-all deliberately does NOT
└──────────────────────────────────────────────────────────────────────┘  touch attachment-less mails
         │ 主题 · 霓虹街机                                                 so is_read keeps meaning
                                                                          "the player read the notice"
footer="/邮箱 查看邮箱"

───────────── NOTHING-TO-CLAIM VARIANT ─────────────
No hero panel. Single panel, height Fixed(240):
│              没有可领取的邮件            │  34px centred
│              7 封邮件都已领取过了        │  24px muted centred
(still a card, not text — it is the same command surface as a successful claim)

───────────── ALREADY-CLAIMED / RETRY VARIANT ─────────────
If every GrantResult comes back skipped=True (grant_many succeeded but
read_mail failed on a previous attempt — see __init__.py:162-192 ordering),
the hero band reads 「之前已发放」 and every tile is the muted skipped form.
The card must never render an empty hero panel.
```

### ScheduleBoardCard — plugins/mailbox/render/schedule.py::render_schedule_board(mails, kit=None)  `[P1/M]`
- **插件**：plugins/mailbox
- **触发**：/schedulemail list · /定时邮件 list
- **目的**：The admin timeline. Replaces the flat text list AND its "使用 '/schedulemail info <名称>' 查看详情" hint by carrying enough per row (recipients, payload, countdown, auto-generated name) that info is only needed for full body text. A send queue is inherently temporal-spatial data — this is the one place in the cluster where a picture is strictly more information-dense than the text it replaces.
- **展示数据**：ScheduledMail.scheduled_time as date line + time line + human countdown, 待发送 / 逾期 status (逾期 = scheduled_time <= now and not is_sent), ScheduledMail.title, recipient summary (全体用户 or N 位用户) derived from ScheduledMail.recipients, first attachment via display_item_amount + "+N 项", ScheduledMail.expire_days, ScheduledMail.name (the auto-generated mail_<ts>_<suffix> identifier), pending vs overdue counts in the subtitle
- **主题可见性**：This card is built almost entirely from kit.separator — the one BaseKit atom that no existing renderer uses, and whose default colour differs sharply per kit (manga uses primary ink (18,18,20); neon uses primary magenta at alpha 190; sailing/fluent use their own defaults). A rail of vertical + horizontal rules is therefore an unusually pure expression of the kit. Admin-only, so its onlooker value is low — it earns its image on density, not on desirability.
- **manga 单色降级**：The separator rail is MangaKit.primary ink, so the timeline structure is at its clearest in monochrome. The one hard-coded token, the 逾期 pill, is redundantly cued by a filled pill silhouette, a ● glyph, and the word 逾期 itself, plus a third signal: the countdown column reads 「逾期 4分」 instead of 「N 小时后」. Everything else is text_color/muted_text_color only.
- **替代的文本响应**：__init__.py:668-671 ("📭 当前没有待发送的定时邮件。") and __init__.py:700-702 (the list built at 673-698, including the trailing info hint at line 698).

```
AutoPage(min_width=896, padding=56, background=kit.background())  ->  898 x ~980 px
root VStack(gap=32, align="stretch")

╭────────────────────────╮
│  定时邮件               │   待发送 5 · 逾期 1
╰────────────────────────╯

┌──────────────────────────────────────────────────────────────────────┐
│  kit.panel(radius OMITTED, padding=32)          content width = 720  │
│                                                                      │
│   07-26  │  ┏━━━━━┓ 新年祝福                                         │  ROW: Frame h=Fixed(112)
│   21:30  │  ┃●逾期┃ ^26px title, wrap=False, max_lines=1              │  HStack(gap=24):
│  逾期 4分 │  ┗━━━━━┛                                                  │   [Frame Fixed(132) align_x=end]
│          │  全体用户 · 赛季积分 x2024Pt · 30 天过期                    │   [kit.separator(orientation=
│          │  新年祝福                                                  │      "vertical", length=None,
│    ^132  ^2px vertical rail       ^22px muted                        │      thickness=2) — fills the
│    ^ 24px date / 24px time / 22px countdown, align="right"           │      Fixed(112) row height]
│                                                                      │   [Frame Fill()]
│  ────────┼───────────────────────────────────────────────────────────│
│                                                                      │  kit.separator(horizontal) between
│   07-28  │  待发送  维护补偿                                          │  rows, gap 18 above and below
│   18:00  │  ^22px muted, no pill
│  3 小时后 │  全体用户 · 赛季积分 x100Pt +1 项 · 7 天过期               │  STATUS TOKENS:
│          │  mail_1753628400_ab12x9                                   │   待发送 -> plain 22px muted word,
│                                                                      │             no pill
│  ────────┼───────────────────────────────────────────────────────────│   逾期   -> filled pill,
│                                                                      │             fill (234,78,116,255),
│   07-30  │  待发送  活动金奖                                          │             text (255,255,255,255),
│   09:00  │                                                           │             ● glyph + literal word
│  4 天后  │  3 位用户 · 赛季积分 x500Pt · 3 天过期                     │   (mail.scheduled_time <= now and
│          │  金奖用户                                                  │    not is_sent means the 5-second
│                                                                      │    scheduler at __init__.py:83 is
│  ────────┼───────────────────────────────────────────────────────────│    stuck — this IS an alarm)
│                                                                      │
│   ...    │                                                           │
│                                                                      │  RECIPIENTS never printed raw:
└──────────────────────────────────────────────────────────────────────┘  "all" -> 全体用户
         │ 主题 · 云母窗                                                   otherwise -> f"{n} 位用户"
                                                                          (a raw comma list of 40 uids
footer="/schedulemail info <名称> 看全文 · edit 改 · delete 删"            would blow the row width)

ATTACHMENT SUMMARY: first attachment via display_item_amount, then "+N 项"

───────────── EMPTY VARIANT ─────────────
Single panel, Fixed(240):
│         没有待发送的定时邮件          │  34px centred
│         /schedulemail add 创建        │  24px muted centred
```

### MailPreviewCard — plugins/mailbox/render/schedule.py::render_mail_preview(mail, *, status, changes=None, kit=None)  `[P1/L]`
- **插件**：plugins/mailbox
- **触发**：/schedulemail send · add · info · edit (four success paths, one card)
- **目的**：A WYSIWYG proof-read surface, serving four sites with one module. Today an admin broadcasts to every user and gets back a single line ("✅ 邮件已发送给全体用户，最后邮件ID: 42"), with zero chance to see what players will actually receive; info returns a 14-line key:value blob; edit returns a flat list of new values with content truncated to 20 chars (line 779). This card renders the mail body exactly as the player-facing MailDetailCard letter panel renders it, then puts delivery metadata underneath — so create/inspect/verify all become the same look-before-it-ships moment.
- **展示数据**：ScheduledMail.title / .content rendered exactly as the player will see them, attachments as reward tiles (same helper as the player card), ScheduledMail.name, recipient summary, scheduled_time absolute + relative countdown, expire_days, created_at + created_by, sent_at when is_sent (mirrors __init__.py:740-742), changed-field diff (old -> new) on the edit path
- **主题可见性**：The admin sees their own theme, and specifically sees it wrapped around content they authored — the strongest possible 'this is my bot' moment for the operator. Because the preview panel is composed from the same helper as the player-facing MailDetailCard, the admin is also implicitly previewing what the theme does to a letter. Worth stating plainly in the module docstring: the preview is rendered in the ADMIN's kit, and each recipient will see the same mail in their own.
- **manga 单色降级**：No hue anywhere. The 改 chip is the inverted-fill shape signal (ink block, panel-fill glyph) and is redundantly cued by the old→new pair being present at all, so a monochrome reader loses nothing. The preview/metadata split is carried by captions outside panels rather than by nesting or tint, which is precisely the construction that survives MinimalKit's opaque panel_fill and MangaKit's flat white.
- **替代的文本响应**：__init__.py:558-562 (send success), __init__.py:640-644 (add success), __init__.py:744-746 (the 14-line info blob built at 717-742), and __init__.py:848-851 (the edit success list built at 767-840).

```
AutoPage(min_width=896, padding=56, background=kit.background())  ->  898 x ~1060 px
root VStack(gap=24, align="stretch")
NO PANEL NESTING ANYWHERE — captions sit OUTSIDE panels, because in
MinimalKit panel_fill (245,245,245,255) is opaque and a panel-in-panel
would be completely invisible.

╭────────────────────────╮
│  定时邮件               │   待发送 · 07-28 18:00
╰────────────────────────╯                            subtitle by status:
                                                        send  -> 已发送 · 全体用户
  玩家将看到                                            add   -> 待发送 · 07-28 18:00
  ^ 24px kit.muted_text_color caption, OUTSIDE the panel  info  -> 已发送 · 07-26 21:30
                                                        edit  -> 已修改 · 3 项
┌──────────────────────────────────────────────────────────────────────┐  PREVIEW PANEL
│  kit.panel(radius OMITTED, padding=32)          content width = 720  │  byte-identical composition
│                                                                      │  to MailDetailCard's letter
│  维护补偿                                                            │  panel + reward panel, via a
│                                                                      │  shared _letter_body(kit, ...)
│  ──────────────────────────────────────────────────────────────────  │  helper
│                                                                      │
│  感谢大家的耐心等待，维护已完成！本次补偿将在 7 天内有效。            │  26px, max_lines=24
│                                                                      │
│  ┌──────────────────┐┌──────────────────┐                            │  _reward_tile() again —
│  │      100         ││       50         │                            │  third reuse of the same
│  │   赛季积分  Pt    ││   星星贴纸  张    │                            │  228x140 helper
│  └──────────────────┘└──────────────────┘                            │
└──────────────────────────────────────────────────────────────────────┘
                                gap 24
  投递信息
┌──────────────────────────────────────────────────────────────────────┐  METADATA PANEL
│  kit.panel(radius OMITTED, padding=32)                               │  rows via utils.cards.stat_row
│                                                                      │
│   名称        mail_1753628400_ab12x9                                 │  label Frame Fixed(140) 22px muted
│   接收者      全体用户                                                │  value Fill()  24px text_color
│   预定时间    2026-07-28 18:00:00              3 小时后               │  wrap=False, max_lines=1
│   过期        7 天                                                    │  row Frame h=Fixed(48)
│   创建        2026-07-26 15:02 · 由 2854196310                        │  gap 12
│   实际发送    2026-07-28 18:00:04                                     │  (only when is_sent and sent_at)
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
         │ 主题 · 网点纸

footer="改 /schedulemail edit mail_1753628400_ab12x9 · 删 delete <名称>"

───────────── EDIT VARIANT (changes dict supplied) ─────────────
Changed rows get a leading chip and an old -> new value:

│  ┏━┓ 预定时间   2026-07-28 18:00  →  2026-07-28 21:30                 │
│  ┃改┃            ^22px muted, old      ^24px text_color, new          │
│  ┗━┛                                                                  │
│  ┏━┓ 内容       维护时间延长，补偿增加！                              │  content shown in FULL in the
│  ┃改┃                                                                 │  preview panel above, not
│  ┗━┛                                                                  │  truncated to 20 chars as at
│      过期        7 天                                                 │  __init__.py:779
│      接收者      全体用户                                             │

chip: kit.panel(kit.text("改", font_size=20, color=kit.panel_fill,
                         align="center"), width=Fixed(36), height=Fixed(36),
                fill=kit.text_color, radius=10)
Same inverted-fill trick as the inbox chip — no hue, works in all 8.

───────────── SHIPPING NOTE ─────────────
For `add` and `send` the reply is image_segment(card) + a ONE-LINE plain
text carrying the raw name, because mail_1753628400_ab12x9 cannot be
copy-pasted out of a PNG and is the argument every subsequent edit/delete
needs:
    await cmd.finish(
        image_segment(card) + Message(f"\n{name}") + pg.element,
        referrer=pg.event.referrer,
    )
```

---

## 交互改动

### plugins/mailbox
- **现在**：Claiming N mails costs N commands and produces N messages. `/邮件 1`, `/邮件 2`, `/邮件 3` — each one re-runs `mail_service.get_user_mails(user_id)` (__init__.py:142), each one emits a separate text wall (__init__.py:203), each one buries its reward at the bottom of that wall (reward_message appended at 178-190).
- **改为**：`/邮件 领取` claims every unread mail that has attachments, in one call, and returns one ClaimAllCard: a hero grid of the aggregated haul (720 赛季积分, 170 星星贴纸, 扬帆主题, ...) plus a per-mail breakdown plus a note of any announcement-only mails left unread.
- **为什么更好**：Three wins, only one of which is cosmetic. (1) N messages become 1 — the group-chat spam of claiming a backlog disappears. (2) It fixes a real correctness bug: `get_user_mails` lazily inserts MailRecipient rows for broadcast mails on every call (service.py:196-217) and re-sorts by `created_at desc` (service.py:241), so a broadcast landing between `/邮箱` and `/邮件 2` shifts every index and the player claims a different mail than the one they read. Claim-all removes the index from the loop entirely. (3) The aggregate total is a number that has never existed before — the sum of a session's haul — and it is the single most screenshot-worthy image in the cluster, which is exactly what the theme-desirability goal needs.
- **新增命令**：/邮件 领取 (aliases 领取 / claim)

### plugins/mailbox
- **现在**：The inbox is a numbered text list capped only by how many mails exist, ending with the hint `发送 '邮件 <编号>' 查看详情` (__init__.py:134). A long backlog produces an unreadable wall of lines and would eventually need pagination.
- **改为**：One InboxCard that auto-densifies: ≤8 mails render as two-line rows (title + attachments + expiry), 9-24 render as one-line rows with attachments collapsed to `赛季积分 x100Pt +1`, and row 24 becomes a single `还有 N 封` line. The card grows via AutoPage; there is no page 2 and no pagination command is ever added.
- **为什么更好**：A paginated list is a state machine the player has to drive; a densifying card is a single glance. Mails self-expire in ≤30 days (Mail.expire_days is clamped 1-30 at __init__.py:513) and the 3am cleanup job deletes them (service.py:305-343), so the list is naturally bounded and 24 rows is a real ceiling, not a guess. It also removes the only call to `escape_text()` on this path (__init__.py:47-53) and, more importantly, removes the unescaped `mail.title` interpolation at line 128 — admin-authored titles currently go into a satori message body with no escaping at all.
- **移除命令**：the implicit paginate-by-scrolling behaviour and the trailing hint line at __init__.py:134

### plugins/mailbox
- **现在**：`/schedulemail add -r all -t 维护补偿 -c "..."` creates a broadcast to every user in the bot and replies with one line: `✅ 定时邮件创建成功 (ID: mail_1753628400_ab12x9)！预定发送时间: 2026-07-28 18:00:00` (__init__.py:640-644). The admin has no way to see what players will receive until it has already been sent to all of them.
- **改为**：`add` and `send` return the MailPreviewCard: the mail rendered exactly as the player-facing letter panel will render it (title, body, reward tiles), plus the delivery metadata, plus a footer carrying `edit` and `delete` for that name — and a one-line plain-text tail with the raw auto-generated name so it stays copy-pasteable.
- **为什么更好**：This turns a fire-and-forget broadcast into a proof-read step at zero extra commands. A typo in a mail going to every player is currently only discoverable after the fact; `add` schedules for the future, so the preview arrives while there is still time to `edit` or `delete`. It also makes `/schedulemail info` unnecessary immediately after creation, which is the single most common reason to run it.

### plugins/mailbox
- **现在**：`/schedulemail edit <name> -c "新内容" -w "+5m" -k 50` replies with a flat list of what was set, with content truncated to 20 characters plus an ellipsis (__init__.py:779) and no indication of what the values were before.
- **改为**：The same MailPreviewCard, with `status="已修改"`, the FULL post-edit body rendered in the preview panel, and every changed metadata row carrying a `改` chip and an `旧 → 新` pair.
- **为什么更好**：The current reply is unverifiable — it echoes back the arguments the admin just typed rather than the resulting state, and for the one field most likely to contain a mistake (content) it echoes back only the first 20 characters. A diff plus a full re-render is the only form of this response that actually confirms the edit landed, and it costs no new commands because it reuses the add/info card.

### plugins/mailbox
- **现在**：`/schedulemail list` prints one line per pending mail and ends with `使用 '/schedulemail info <名称>' 查看详情` (__init__.py:698), so inspecting the queue is a two-command loop: list, then info, then list again.
- **改为**：ScheduleBoardCard is a timeline with a time rail — each row carries the absolute date/time, a human countdown (`3 小时后` / `逾期 4 分`), the recipient summary, the reward summary, the expire window and the auto-generated name. `info` becomes needed only when the admin wants full body text.
- **为什么更好**：A send queue is temporal data; a rail with countdowns lets an admin answer 'what is about to fire and does it look right' in one glance instead of one info call per entry. It also surfaces a failure state the text list only hints at: `已到期` (__init__.py:677-679) means `scheduled_time <= now` while `is_sent` is still false, and since the processor runs every 5 seconds (__init__.py:83) that condition is a stuck-scheduler alarm, not a normal state — the card renders it as `逾期` with a filled pill and an elapsed-since counter.

### plugins/mailbox
- **现在**：Mails are addressed only by their position in a live-sorted query result (`mails[mail_index]`, __init__.py:141-150). Nothing in the system has a stable player-visible handle.
- **改为**：Every card shows a stable code `#M<mail.id>` (inbox rows in the dense variant, the detail header subtitle, the claim-all breakdown), and `/邮件 M42` is accepted alongside the legacy `/邮件 2`. The `M` prefix makes the two forms unambiguous — a code can never be mistaken for an index.
- **为什么更好**：Codes are the only correct way to reference a mail across messages: the claim-all receipt lists four mails, and without a stable handle none of them can be re-opened reliably. Honest drawback: a code cannot be copied out of a PNG, so it is strictly worse to type than `2` — which is why the ordinal stays primary and the code is belt-and-braces. Low effort; do it after claim-all, which is the real fix.
- **新增命令**：/邮件 M<id> as an accepted form of /邮件 <编号>

### plugins/mailbox
- **现在**：Reading any mail marks it read and grants its attachments (__init__.py:161-192). For an attachment-less announcement, `is_read` is the only record that a player actually saw it.
- **改为**：`/邮件 领取` claims only mails whose `attachments` list is non-empty. Announcement-only mails stay unread, and the ClaimAllCard footer names them: `还有 2 封通知未读 · /邮箱 查看`.
- **为什么更好**：This is an interaction rule, not a rendering choice, and it is the thing that makes bulk claim safe to ship. If claim-all marked everything read, a maintenance notice would be silently consumed by a player farming rewards and `is_read` would stop meaning anything. Excluding them costs one filter and preserves the only read-receipt signal the system has, while the footer guarantees nothing disappears without being named.

### plugins/mailbox
- **现在**：`/邮箱` on an empty inbox replies `你的邮箱是空的呢~` as plain text (__init__.py:110-113) — the state a brand-new player hits first.
- **改为**：The same InboxCard, empty variant: one panel, a 34px `邮箱是空的`, a 24px muted line, subtitle `0 封`, footer omitted. ~8 components, roughly 40 ms.
- **为什么更好**：This is the one place I am knowingly spending latency purely for theme feel, so it needs a justification and here it is: the inbox is the SUBJECT of `/邮箱`, not an acknowledgement of some other action, and mixing text and image replies on the same command means a player who just bought a theme runs `/邮箱`, sees plain text, and concludes the theme did not apply. Consistency of surface is worth 40 ms on the cheapest card in the cluster. The same argument covers the empty schedule board (__init__.py:668-671) for admins.

---

## 保留为文本
- **plugins/mailbox** — Non-superuser access to /schedulemail — the bare `await schedule_mail_cmd.finish(referrer=event.referrer)` at __init__.py:306, 354, 416, 424, 441, 485.：These send nothing at all. Six sites, all unchanged. Rendering anything here would leak the existence of admin commands to non-admins.
- **plugins/mailbox** — Index errors on /邮件 <n>: 「邮件编号无效！」 (__init__.py:145-148) and 「请输入有效的邮件编号！」 (__init__.py:208-211).：A mistyped argument must not cost a 100 ms render and an image upload. These are the most frequent failures on the busiest player command. Improve the strings instead — 「邮件编号无效，当前有 7 封邮件（1-7）」 — which costs nothing and is more useful than any card would be. Re-rendering the whole InboxCard on a typo is tempting and wrong: it doubles the cost of a mistake.
- **plugins/mailbox** — 「这封邮件已经过期了！」 (__init__.py:154-157).：Text, and worth flagging as near-dead code: `get_user_mails` already filters to `created_at + expire_days*86400 > current_time` (service.py:226-228), so the `time.time() > mail.expire_time.timestamp()` check at line 153 is only reachable in a sub-second race. Never worth a card.
- **plugins/mailbox** — All admin argument-validation refusals: 「参数不完整！...」 (321-326, 382-386), 「请提供邮件名称！」 (430-433, 448-451, 492-495), 「请至少提供一个要修改的字段！」 (473-476), 「过期天数必须在1-30之间！」 (514-517, 606-609, 828-831), 「奖励数量不能为负数！」 (520-523), 「接收者不能为空！」 (540-543), 「时间格式错误！...」 (598-602, 783-786), 「Pt数量不能为负数！」 (612-615, 795-798), 「星星贴纸数量不能为负数！」 (806-809), 「参数错误: ...」 / 「参数格式错误: ...」 (567-570, 649-652, 856-859).：Twenty sites of the same shape. Every one is a short, actionable correction that the admin will act on within seconds, usually while iterating on a long command line. An image here adds latency, an upload, and — worse — makes the corrected syntax uncopyable. The usage strings at 322-323 and 383 exist precisely to be copy-pasted.
- **plugins/mailbox** — All error-code replies: 「发送邮件失败\n错误码：{code}」 (344-347), 「创建定时邮件失败\n错误码：{code}」 (406-409), 「发送失败\n错误码：{code}」 (573-576), 「创建失败\n错误码：{code}」 (655-658), 「编辑失败\n错误码：{code}」 (862-865), and 「❌ 更新字段 '{field}' 失败。」 (843-846).：The error code from utils.error_handler is a correlation key the admin pastes into a log search. Putting it in a PNG makes it unretrievable. These also fire when something is already broken — rendering is exactly the wrong thing to attempt on an error path, since the render itself may be what failed.
- **plugins/mailbox** — 「❌ 找不到名为 '{name}' 的定时邮件。」 (712-715, 755-758, 880-883) and 「❌ 邮件 '{name}' 已发送，无法修改。」 (761-764).：Refusals. Short, latency-sensitive, and the name they echo is a 24-character auto-generated identifier the admin needs to re-read and correct — it must stay selectable text.
- **plugins/mailbox** — 「✅ 已删除定时邮件 '{name}'。」 (875-878).：A destructive-action acknowledgement whose entire payload is one name. There is nothing spatial to show — the thing it describes no longer exists. Following up with `/schedulemail list` (which IS a card) is the natural next step and shows the new state.

---

## 风险
- Bulk claim must reuse the EXACT existing idempotency key or it will double-grant. __init__.py:176 passes `idempotency_key=f"mail:{mail.id}"` into `grant_many`, and `grant_item` folds user_id/item_id/scope into it via `_tx_key` (service.py, grant_item). If `/邮件 领取` invents a new key (e.g. `claim_all:<batch>`), a mail already claimed individually will be granted a second time. The claim-all service function must loop mails and call `grant_many` with the identical per-mail key.
- The existing read path grants BEFORE marking read (__init__.py:162-192): `grant_many` runs, then `mail_service.read_mail`. If read_mail throws, the grant is already committed and the mail stays unread, so the next `/邮件 <n>` returns every GrantResult with `skipped=True`. Both MailDetailCard and ClaimAllCard must render that state as an explicit 「之前已发放」 / 「已有」 strip and must never emit an empty hero panel. Test it.
- Mail content is admin-authored and unbounded (Mail.content is a Text column). A 3000-character announcement at 26px/36px line-height over 720px is ~40 lines ≈ 1450 px of body alone, and AutoPage grows without limit. Cap body at max_lines=24 with overflow="ellipsis" and accept that very long announcements are truncated — or the mailbox becomes the one plugin that can emit a 4000 px image. The README already advises admins to keep content short (README.md:163).
- Cost. InboxCard at 8 two-line rows is ~10 kit panels plus ~30 text components — meaningfully heavier than the 898x987 two-panel page the house doc measured at 0.03-0.13 s. Expect bangdream/sakura/neon to sit at or above the 0.15 s budget. Two mandatory mitigations: use `await page.render_async()` on every mailbox handler, and use plain `kit.background()` with NO BanGDream image-source override — `kit.background(source=BG_DIR/...)` costs 0.25 s vs 0.08 s for the tiled pattern (house doc §13), and a blurred photo behind 26px body text is bad for legibility anyway. This is a deliberate divergence from mines/one_stroke.
- Group-chat privacy. The inbox card is more eye-catching than the text it replaces and exposes the player's reward balances plus the body of any admin-sent personal mail to everyone in the channel. There is no regression (the text does this today) but the change makes it noticeable. If a per-mail `is_private` flag is ever wanted, the InboxCard row is where it goes; do not build it now.
- Nothing in the image can be copy-pasted, and this cluster has two identifiers that must be: the auto-generated `mail_<ts>_<suffix>` scheduled-mail name (scheduled_service.py:57-65) and the error codes. The `add`/`send` receipt therefore ships `image_segment(card) + Message(f"\n{name}")`, and every error path stays text. Verify the plain-text tail actually renders after the image in satori before relying on it.
- There are NO item icon assets anywhere in the repo — items.json carries no icon field and there is no resources/ directory at the project root. Every attachment must be rendered from `display_item_amount(item_id, quantity)` text alone. Reward tiles are therefore numeral + name, and the design must not assume art will appear later; if it does, the 228x140 tile has room for a 96x96 raster above the numeral.
- Cross-cluster dependency: plugins/daily/__init__.py:118-121 appends 「你有 N 封邮件，记得查看哦～」 to the check-in text by calling `mail_service.get_user_mails`. When the daily cluster becomes a card, that unread count should become a badge on it rather than a stray line — coordinate, or the mailbox nudge silently disappears when daily is converted.
- `/邮件 领取` must decide what happens when the aggregated haul has more than 6 distinct item_ids. The 3-column grid wraps to a second row (228x140 tiles, 720 wide) which is fine to 6, but a broadcast with 8 attachment types would push the hero panel to 3 rows / 460 px. Cap the hero at 6 tiles ordered by quantity descending and roll the remainder into the 明细 panel.
