# 插件簇：utility

涉及插件：plugins/help, plugins/info, plugins/nickname, plugins/vits, plugins/bang_avatar

卡片 7 张 · 交互改动 13 项 · 保留文本 10 项

---

## 卡片设计

### HelpBoardCard  →  plugins/help/render/board.py::render_board(entries, *, theme_name, kit=None)  `[P0/L]`
- **插件**：plugins/help
- **触发**：/help (aliases 帮助, 帮助信息) — plugins/help/__init__.py:162
- **目的**：The first thing a new player sees, and the single highest-traffic third-party impression surface in the whole bot. Today it is 14 lines of `名字 -描述` with no command strings on it at all — you cannot type anything from reading it, you have to run a second command. The board prints the actual typeable string for every command, grouped by what you are trying to do, so the drill-down becomes optional instead of mandatory.
- **展示数据**：category name + item count per category (游戏 / 养成 / 社交), primary typeable command string per entry, e.g. /猜卡面, /转账 <昵称> <数量>, aliases and sub-triggers as a muted second line, e.g. cck · 猜猜看 / r · q / 提示 · bzd, total command count in the header subtitle, meta strip: /help 插件名 · /关于 · /id · /主题 and the support QQ group 908979461 (from help/__init__.py:181), theme signature footer (suppressed on starter themes per foundation §5)
- **主题可见性**：This is the single best theme showcase in the bot because it is almost pure chrome: 3 large panels + 20 small tiles = 23 kit-decided corners on one image, plus the kit background. The bangdream 48px corner, neon 10px, and fluent 8px read as three completely different products at a glance. It is also the highest-traffic surface an onlooker sees, and it is the one card that names /主题 in its own body — so the onlooker who thinks 'sick theme' finds the command on the same image.
- **manga 单色降级**：Best-case kit. Everything is ink text, hairline separators, and outlined tiles at radius 16 — no hue carries meaning anywhere. Category grouping is carried by panel boundaries and the 30px header, not color. The muted alias line is (112,112,118) on (255,255,255,242) paper, ~5:1 contrast. The screentone background separates the page from the panels without any color at all.
- **替代的文本响应**：plugins/help/__init__.py:184 (the whole bare-/help dump). Also deletes the reason `escape_text` (help/__init__.py:10-16) and the `bot.adapter.get_name() == "Satori"` escape branch (help/__init__.py:200-201) exist — an image has no markup to escape. Requires replacing the hand-maintained `plugin_data` dict (help/__init__.py:19-159) with a structured registry; the dict is provably stale, missing /gacha (gacha/__init__.py:26), /背包 (inventory/__init__.py:63), /装扮 (:111), /赛季 (:171), /赛季排行 (:248), /赛季趋势 (:288), /赛季历史 (:317), /profile (:368), and /id (info/__init__.py:22).

```
AutoPage(min_width=896, padding=56, background=_background(kit))
root = VStack([...], gap=32, align="start")     # "start", NOT the default "stretch" (layout.py:377)

 896 declared / ~898 actual · content width 784
╔════════════════════════════════════════════════════════════════════════════╗
║ ┌────────────────────────────────┐                                         ║ header via utils.cards.response_card
║ │ 帮助                            │   BD branch: kit.title_pill("帮助",     ║ wrapped in Frame(align_x="start")
║ │ 23 条指令 · /help 猜卡面 看详情  │   "23 条指令 · …", 500, 57) → 548x127   ║ so all 8 kits agree on width (§8b)
║ └────────────────────────────────┘                                         ║
║                                                                            ║ gap 32
║ ┌────────────────────────────────────────────────────────────────────────┐ ║ kit.panel(padding=32, radius OMITTED)
║ │  游戏                                                          6 项    │ ║ HStack[ text(30) Fill , text(22, muted, right) ]
║ │  ────────────────────────────────────────────────────────────────────  │ ║ kit.separator()
║ │  ┌────────────────────┐┌────────────────────┐┌────────────────────┐    │ ║ Grid(columns=3,
║ │  │ /猜卡面             ││ /猜谱面             ││ /一笔画             │    │ ║   column_track=Fixed(224),
║ │  │ cck · 猜猜看        ││ cpm · 提示 · bzd   ││ os · r · q         │    │ ║   row_track=Fixed(80), gap=24)
║ │  └────────────────────┘└────────────────────┘└────────────────────┘    │ ║ 3*224 + 2*24 = 720 = 784 - 2*32 ✓
║ │  ┌────────────────────┐┌────────────────────┐┌────────────────────┐    │ ║ tile = kit.panel(child, radius=16,
║ │  │ /黑香澄             ││ /探险               ││ /娶群友             │    │ ║        padding=Insets.only(16,12,16,12))
║ │  │ -h 看玩法           ││ mines · -h · -f    ││ qqy · ccb          │    │ ║ line1 text(26, wrap=False, max_lines=1)
║ │  └────────────────────┘└────────────────────┘└────────────────────┘    │ ║ line2 text(22, muted, wrap=False, max_lines=1)
║ └────────────────────────────────────────────────────────────────────────┘ ║ panel h = 32+44+2+18+184+32 = 312
║                                                                            ║
║ ┌────────────────────────────────────────────────────────────────────────┐ ║
║ │  养成                                                          9 项    │ ║
║ │  ────────────────────────────────────────────────────────────────────  │ ║
║ │  ┌────────────────────┐┌────────────────────┐┌────────────────────┐    │ ║
║ │  │ /信息               ││ /签到               ││ /排行榜             │    │ ║
║ │  │ 余额 · 个人信息      ││ daily              ││ rank               │    │ ║
║ │  └────────────────────┘└────────────────────┘└────────────────────┘    │ ║
║ │  ┌────────────────────┐┌────────────────────┐┌────────────────────┐    │ ║
║ │  │ /每日任务           ││ /抽卡               ││ /背包               │    │ ║
║ │  │ 任务 · 每日         ││ gacha · 十连        ││ 仓库 · inventory   │    │ ║
║ │  └────────────────────┘└────────────────────┘└────────────────────┘    │ ║
║ │  ┌────────────────────┐┌────────────────────┐┌────────────────────┐    │ ║
║ │  │ /装扮               ││ /主题               ││ /赛季               │    │ ║  ← 主题 lands here; the board
║ │  │ cosmetic           ││ 8 套外观            ││ season · 排行 · 趋势 │    │ ║    is where onlookers learn it
║ │  └────────────────────┘└────────────────────┘└────────────────────┘    │ ║ panel h = 32+44+2+18+288+32 = 416
║ └────────────────────────────────────────────────────────────────────────┘ ║
║                                                                            ║
║ ┌────────────────────────────────────────────────────────────────────────┐ ║
║ │  社交                                                          5 项    │ ║
║ │  ────────────────────────────────────────────────────────────────────  │ ║
║ │  ┌────────────────────┐┌────────────────────┐┌────────────────────┐    │ ║
║ │  │ /转账 <昵称> <数量>  ││ /发红包             ││ /抢红包             │    │ ║
║ │  │ transfer           ││ 红包 <标题><额><份> ││ 领红包 <编号>       │    │ ║
║ │  └────────────────────┘└────────────────────┘└────────────────────┘    │ ║
║ │  ┌────────────────────┐┌────────────────────┐                          │ ║ Grid `rows` OMITTED — _tracks()
║ │  │ /邮箱               ││ /设置昵称 <昵称>    │                          │ ║ derives ceil(5/3)=2 and render()
║ │  │ 邮件 · mail · <编号>││ 叫我 · setnick     │                          │ ║ guards `child_index < len` at
║ │  └────────────────────┘└────────────────────┘                          │ ║ layout.py:562 → ragged rows are safe
║ └────────────────────────────────────────────────────────────────────────┘ ║
║                                                                            ║
║ ┌────────────────────────────────────────────────────────────────────────┐ ║ meta strip: NOT tiles. One row of
║ │  /help 插件名  ·  /关于  ·  /id  ·  /主题        需要帮助? QQ群 908979461│ ║ text(24) + text(22 muted, right).
║ └────────────────────────────────────────────────────────────────────────┘ ║ kit.panel(padding=Insets.only(32,20,32,20))
║                                                                            ║ h ≈ 90
║                                        ┃ 主题 · 霓虹街机                    ║ signature_for(kit) — right-aligned,
╚════════════════════════════════════════════════════════════════════════════╝ omitted entirely on starter themes

Estimated height: 127 + 32 + 312 + 32 + 416 + 32 + 312 + 32 + 90 + 24 + 40 + 112 = ~1561
→ 896 x ~1561 (1 : 1.74). MEASURE before shipping; if >1700 drop the tile sub-line to
  Fixed(56) tracks, which returns ~1370 (1 : 1.53).
```

### HelpDetailCard  →  plugins/help/render/detail.py::render_detail(entry, kit=None)  `[P1/M]`
- **插件**：plugins/help
- **触发**：/help <插件名> — plugins/help/__init__.py:187-205
- **目的**：The usage dict + examples for one plugin. The reason this card must exist and cannot just be folded into the board is 猜卡面: help/__init__.py:64 crams twelve difficulty names into a single line of prose ('难度可选为 easy, normal, hard, expert, hard++, expert++, 黑白木筏, 高闪大图, 五只小猫, 超级猫猫, 寻找记忆, 6块床板'). That is an enumerable value set masquerading as a sentence. As a chip grid it becomes scannable and, more importantly, copy-target-able.
- **展示数据**：plugin display name (header subtitle), usage rows: command string (left, 24px) → meaning (right, 22px muted) from plugin_data[x]['usage'], enumerable parameter chips when the registry entry declares them (难度 x12 for 猜卡面, 游戏难度 x4 + 缩写 for 猜谱面, 难度 x3 for 一笔画), example strings from plugin_data[x]['examples'] as a 3-column grid, theme signature
- **主题可见性**：Three stacked kit panels plus up to 12 capsule chips. The chip capsule is where the kits diverge hardest — a `radius=height//2` pill under bangdream's warm cream sits very differently from the same pill on neon's near-black machine fill. The header is the BD title_pill on bangdream and the neutral two-tier header from utils.cards everywhere else, which is itself a visible fork.
- **manga 单色降级**：Pure ink. The chip grid works entirely on outline + word; there is no color-coded difficulty. The left/right split of the usage rows is positional. Muted-vs-normal text is the only palette use and manga's (112,112,118) vs (18,18,20) is a strong lightness gap. This card is arguably sharpest in manga because the chip outlines survive JPEG artifacting better than pastel fills.
- **替代的文本响应**：plugins/help/__init__.py:203 (the `插件 X 的使用方法：` + usage lines + `示例：` block, lines 188-198).

```
AutoPage(min_width=896, padding=56)  ·  content 784  ·  VStack(gap=32, align="start")

╔════════════════════════════════════════════════════════════════════════════╗
║ ┌────────────────────────────────┐                                         ║ response_card header
║ │ 帮助                            │   BD: kit.title_pill("帮助","猜卡面",   ║ title = fixed noun "帮助"
║ │ 猜卡面                          │        pill_width=420, h=57) → 460x127 ║ subtitle = the plugin (live state)
║ └────────────────────────────────┘                                         ║
║                                                                            ║
║ ┌────────────────────────────────────────────────────────────────────────┐ ║ kit.panel(padding=32, radius omitted)
║ │  用法                                                                   │ ║ text(30)
║ │  ────────────────────────────────────────────────────────────────────   │ ║ kit.separator()
║ │  /猜卡面|cck|猜猜看                          开始猜卡面（随机难度）      │ ║ row = Frame(HStack([
║ │  /猜卡面 <难度>                              指定难度开始              │ ║   Frame(text(24,wrap=False,max_lines=1,
║ │  /猜卡面 -f                                  强制退出                  │ ║        overflow="ellipsis"), width=Fill(),
║ │  /猜卡面 -h                                  查看帮助和可用难度         │ ║        align_x="start", align_y="center"),
║ │  bzd                                        猜不出来的时候就发这个吧    │ ║   Frame(text(22, color=muted, align="right",
║ │                                                                        │ ║        wrap=False, max_lines=1),
║ └────────────────────────────────────────────────────────────────────────┘ ║        width=Fixed(300), align_x="stretch",
║                                                                            ║        align_y="center")], gap=12),
║ ┌────────────────────────────────────────────────────────────────────────┐ ║   height=Fixed(44), align_y="center")
║ │  难度                                                         12 种     │ ║ VStack(rows, gap=8, align="stretch")
║ │  ────────────────────────────────────────────────────────────────────   │ ║
║ │  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐          │ ║ THE PAYOFF PANEL. Only rendered when
║ │  │  easy    ││ normal   ││  hard    ││ expert   ││ hard++   │          │ ║ entry.params is non-empty.
║ │  └──────────┘└──────────┘└──────────┘└──────────┘└──────────┘          │ ║ Grid(columns=5,
║ │  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐          │ ║   column_track=Fixed(132),
║ │  │ expert++ ││ 黑白木筏  ││ 高闪大图  ││ 五只小猫  ││ 超级猫猫  │          │ ║   row_track=Fixed(56), gap=15)
║ │  └──────────┘└──────────┘└──────────┘└──────────┘└──────────┘          │ ║ 5*132 + 4*15 = 720 = 784-64 ✓
║ │  ┌──────────┐┌──────────┐                                              │ ║ chip = kit.panel(Frame(text(24,
║ │  │ 寻找记忆  ││ 6块床板   │                                              │ ║   align="center", wrap=False,
║ │  └──────────┘└──────────┘                                              │ ║   max_lines=1), align_x="center",
║ └────────────────────────────────────────────────────────────────────────┘ ║   align_y="center"), radius=28)
║                                                                            ║ radius = height//2 → capsule (house rule §7)
║ ┌────────────────────────────────────────────────────────────────────────┐ ║
║ │  示例                                                                   │ ║
║ │  ────────────────────────────────────────────────────────────────────   │ ║
║ │   /猜卡面        /猜卡面 easy      /猜卡面 超级猫猫                       │ ║ Grid(columns=3, column_track=Fixed(224),
║ │   /猜卡面 -f     /猜卡面 -h        bzd                                  │ ║   row_track=Fixed(48), gap=24)
║ └────────────────────────────────────────────────────────────────────────┘ ║ text(24, wrap=False, max_lines=1)
║                                                                            ║
║                                        ┃ 主题 · 网点纸                     ║ signature_for(kit)
╚════════════════════════════════════════════════════════════════════════════╝

Height ≈ 127+32+ (32+44+2+18+ 5*44+4*8 +32 =380) +32+ (32+44+2+18+ 3*56+2*15 +32 =326)
         +32+ (32+44+2+18+ 2*48+24 +32 =272) +24+40+112  ≈ 1377   → 896 x ~1377 (1:1.54)
For a plugin with no `params` (e.g. 昵称, tts) the middle panel is omitted → ~1050.
```

### AboutCard  →  plugins/info/render.py::render_about(*, theme_name, theme_owned, theme_total, kit=None)  `[P1/S]`
- **插件**：plugins/info
- **触发**：/关于 · /info (rule=has_no_argument) — plugins/info/__init__.py:9-19
- **目的**：Three lines of static bot identity. It is the lowest-data, highest-chrome response in the bot, which makes it the ideal pure theme demo — there is nothing on it to distract from the kit. Doubling as the /主题 equip confirmation surface (see interaction changes) means the theme plumbing does not need a separate 'sample card' module.
- **展示数据**：「キラキラドキドキ」的小游戏合集机器人 Kasumi! (info/__init__.py:15), 项目地址 Kasumi-Games/kasumi-next (info/__init__.py:16), 联系我们 908979461 (info/__init__.py:17), 指令入口 /help, active theme display name + owned/total count (new — from utils.theming.theme_for_kit + all_themes), CTA capsule: 输入 /主题 切换外观
- **主题可见性**：Maximum. Two panels, one capsule, one background, six text rows and zero domain data — the kit is 90% of the pixels. This is the card to render in all eight kits during review because any kit bug shows up here first. It is also the only surface where the theme is named unconditionally, so a player on a starter theme (who by design gets no signature line anywhere else) still learns the mechanic exists.
- **manga 单色降级**：Fine. The 外观 row is a label/value text pair, not a swatch — it names the theme in words, which is exactly what survives monochrome. The bottom capsule is an outlined pill. The only risk is that manga is the *least* distinguishable kit on a card this sparse; the 外观 row naming '网点纸' is the redundant word cue that fixes that.
- **替代的文本响应**：plugins/info/__init__.py:14-19 (the entire 3-line 关于 message). Does NOT absorb /id at info/__init__.py:22-28 — see stays_text.

```
AutoPage(min_width=896, padding=56)  ·  content 784  ·  VStack(gap=32, align="start")

╔════════════════════════════════════════════════════════════════════════════╗
║ ┌────────────────────────────────┐                                         ║
║ │ Kasumi                          │  BD: kit.title_pill("Kasumi",          ║
║ │ キラキラドキドキ                 │       "キラキラドキドキ", 500, 57)      ║
║ └────────────────────────────────┘                                         ║
║                                                                            ║
║ ┌────────────────────────────────────────────────────────────────────────┐ ║ kit.panel(padding=32, radius omitted)
║ │                                                                        │ ║
║ │   「キラキラドキドキ」的小游戏合集机器人                                  │ ║ text(30, wrap=True) — the one place
║ │                                                                        │ ║ wrap=True is correct: it is prose
║ │   ──────────────────────────────────────────────────────────────────   │ ║ kit.separator()
║ │                                                                        │ ║
║ │   项目            Kasumi-Games/kasumi-next                             │ ║ stat_row(kit, "项目", "...")
║ │   交流群          908979461                                            │ ║ label text(24, muted) Frame(Fixed(160))
║ │   指令            /help                                                │ ║ value text(24)        Frame(Fill())
║ │   外观            霓虹街机 · 已解锁 4/8                                 │ ║ ← ALWAYS rendered, even on starters
║ │                                                                        │ ║   (deliberate exception, see IC)
║ └────────────────────────────────────────────────────────────────────────┘ ║ rows VStack(gap=18, align="stretch")
║                                                                            ║ row = Frame(HStack(...), height=Fixed(40),
║ ┌────────────────────────────────────────────────────────────────────────┐ ║        align_y="center")
║ │   输入 /主题 切换外观 · 8 套可选                                          │ ║ kit.panel(Frame(text(24, align="center")),
║ └────────────────────────────────────────────────────────────────────────┘ ║   height=Fixed(64), radius=32)  ← capsule
╚════════════════════════════════════════════════════════════════════════════╝

Height ≈ 127 + 32 + (32 + 41 + 24 + 2 + 24 + 4*40+3*18 + 32 = 372) + 32 + 64 + 112 ≈ 739
→ 896 x ~739 (1 : 0.82, near-landscape but short — safe in a group chat)
No theme_signature footer here: the 外观 row supersedes it and is unconditional.
```

### NameplateCard  →  plugins/nickname/render.py::render_nameplate(state, kit=None)  where state ∈ {UNSET, CURRENT, JUST_SET, JUST_CHANGED}  `[P2/S]`
- **插件**：plugins/nickname
- **触发**：/我的昵称 · getnick (info/__init__.py:17) AND the success paths of /设置昵称 · 叫我 · setnick (:16)
- **目的**：Collapses five response sites into one card with four states. The set-nickname success path currently fires TWO separate messages (nickname/__init__.py:78 then :82) — 'set!' followed by a policy footnote. And the insufficient-balance refusal at :91 tells you the price but never your balance, so you cannot tell how short you are. One card carries name + price + balance always, so the refusal becomes rare instead of blind.
- **展示数据**：the nickname itself at 64px (or an empty-slot rule when unset), state framing line: 以后 Kasumi 就会叫你 / Kasumi 还不知道该怎么叫你, 下次修改 price: 30 Pt (hard-coded at nickname/__init__.py:90,96), current balance from monetary.get (currently never shown, even in the refusal at :91), 首次设置免费 badge on the JUST_SET state (absorbs the second message at :82), the literal command string /设置昵称 <你想要的称呼> on the UNSET state (absorbs :117)
- **主题可见性**：The 64px hero name renders in the kit's own font treatment — bangdream routes through BanGDreamText with its CHINESE_FONT, everything else through KitText. A player's own name at display size in their own theme is the most personal 'this is mine' moment in the cluster. Frequency is low so the cost is easy to justify.
- **manga 单色降级**：Strong. The hero is a word; the UNSET empty state is a drawn rule plus an emptied value column — two non-color signals, copying the leaderboard.py:22-29 discipline. Price/balance are label-value text pairs. Nothing depends on hue.
- **替代的文本响应**：plugins/nickname/__init__.py:78 + :82 (two messages → one card), :100 (change success), :117 (unset) and :122 (query). Five sites, one module. The six validation/refusal sites at :34, :41, :47, :57, :70, :91 stay text.

```
AutoPage(min_width=896, padding=56)  ·  content 784  ·  VStack(gap=32, align="start")

STATE = JUST_SET / JUST_CHANGED / CURRENT
╔════════════════════════════════════════════════════════════════════════════╗
║ ┌────────────────────────────────┐                                         ║
║ │ 昵称                            │  BD: kit.title_pill("昵称", <state>,   ║ subtitle carries the live state:
║ │ 设置成功                        │       pill_width=420, h=57)            ║ 设置成功 / 修改成功 / 当前称呼
║ └────────────────────────────────┘                                         ║
║                                                                            ║
║ ┌────────────────────────────────────────────────────────────────────────┐ ║ kit.panel(padding=Insets.only(32,36,32,32),
║ │                                                                        │ ║   radius omitted)
║ │   以后 Kasumi 就会叫你                                                  │ ║ text(24, color=muted)
║ │                                                                        │ ║ gap 12
║ │   喵喵                                                                  │ ║ THE HERO. text(64, wrap=False,
║ │                                                                        │ ║   max_lines=1, overflow="ellipsis")
║ │   ──────────────────────────────────────────────────────────────────   │ ║   64 is the display-numeral tier (§5);
║ │                                                                        │ ║   nickname is capped at 20 chars
║ │   下次修改          30 Pt                                              │ ║   (nickname/__init__.py:40) so 20*64
║ │   我的余额          482 Pt                                             │ ║   overflows 720 → ellipsis is required.
║ │                                                                        │ ║ stat_row(kit, ...) x2, gap 18
║ └────────────────────────────────────────────────────────────────────────┘ ║
║                                                                            ║
║                                        ┃ 主题 · 樱色                       ║ signature_for(kit)
╚════════════════════════════════════════════════════════════════════════════╝

JUST_SET adds one extra muted row before 下次修改:  「首次设置免费」

STATE = UNSET  (same page, hero slot degrades — no separate module)
║ ┌────────────────────────────────────────────────────────────────────────┐ ║
║ │   Kasumi 还不知道该怎么叫你                                             │ ║ text(24, muted)
║ │                                                                        │ ║
║ │   ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─                                             │ ║ hero replaced by kit.separator(
║ │                                                                        │ ║   length=Fixed(300), thickness=4,
║ │   ──────────────────────────────────────────────────────────────────   │ ║   color=kit.muted_text_color)
║ │   首次设置          免费                                                │ ║ ← empty slot = a rule, not a color.
║ │   之后修改          30 Pt                                              │ ║   Mirrors the leaderboard's
║ │   我的余额          482 Pt                                             │ ║   filled-vs-empty idiom
║ │                                                                        │ ║   (leaderboard.py:22-29): muted color
║ │   /设置昵称 <你想要的称呼>                                              │ ║   AND an emptied value column.
║ └────────────────────────────────────────────────────────────────────────┘ ║

Height ≈ 127 + 32 + (36+32+12+86+24+2+24+ 2*40+18 +32 ≈ 380) + 24 + 40 + 112 ≈ 715
→ 896 x ~715
```

### VoiceRosterCard  →  plugins/vits/render/roster.py::render_roster(groups, *, available, balance, kit=None)  `[P1/M]`
- **插件**：plugins/vits
- **触发**：the character-list branch of /tts — plugins/vits/__init__.py:109 + :116; ALSO a new explicit trigger /tts -l · /tts 角色 · /tts 列表
- **目的**：vits/__init__.py:116-121 dumps `\n`.join of speaker_dict (vits/utils.py:101-197) — 10 lines, one of which is the 30-name Starlight line. That is 75 names in a wall of text, delivered as a side effect of entering a 60-second waiter (:123). Worse, the alias mechanic the previous message advertises ('香澄可以写成ksm', :110) is invisible: the dump prints names only, never a single alias. A grid prints name AND alias together, which is the only way the alias feature becomes learnable.
- **展示数据**：9 band panels x 5 characters, each with name + one romaji alias, Starlight as a separate 30-name grid (aliases omitted — 雙葉/真晝/克洛迪娜 have no characters.json entry at all, verified), per-character availability against the live `speakers` dict returned by call_speaker_api (vits/__init__.py:48-50), cost formula 10 字 1 Pt (derived from vits/__init__.py:162), the caller's current balance from monetary.get (vits/__init__.py:163), one worked usage example: /tts 香澄 早上好
- **主题可见性**：Ten kit panels on one page — the highest panel count in the cluster after the help board. Because every panel is the same size and shape, the kit's corner radius and fill become a repeating motif rather than a one-off, which is exactly what makes a theme read as a 'system' to a bystander. Also: this is the only card that will be posted *at* another person ('here, look up your character'), so it travels.
- **manga 单色降级**：Good. Band grouping is panel geometry; name-vs-alias is position + the muted/normal lightness pair; unavailability is muted text + an emptied alias column. No hue anywhere. The one manga-specific risk is that ten outlined panels at radius 14 over screentone is visually busy — mitigate by letting the panels use the kit default fill and NOT adding any extra border.
- **替代的文本响应**：plugins/vits/__init__.py:109 (the 'tell me the character' prompt) + :116-121 (the speaker_dict dump). Two consecutive `vits.send` calls become one image. The card also becomes reachable directly (see interaction changes) instead of only as a waiter side effect.

```
AutoPage(min_width=896, padding=56)  ·  content 784  ·  VStack(gap=32, align="start")

╔════════════════════════════════════════════════════════════════════════════╗
║ ┌────────────────────────────────┐                                         ║
║ │ tts                             │  BD: kit.title_pill("tts",             ║ subtitle = live availability count
║ │ 75 位角色 · 10 字 1 Pt           │       "75 位角色 · 10 字 1 Pt", 560,57)║ (cost formula is vits:162,
║ └────────────────────────────────┘                                         ║  ceil(len(text)/10))
║                                                                            ║
║ ┌───────────────────────┐┌───────────────────────┐┌───────────────────────┐║ HStack? No — Grid(columns=3,
║ │ Poppin'Party          ││ Afterglow             ││ Pastel*Palettes       │║   column_track=Fixed(245),
║ │ ─────────────────────  ││ ─────────────────────  ││ ─────────────────────  │║   row_track=Fixed(246), gap=25)
║ │ 香澄        ksm       ││ 巴          tme       ││ 彩          aya       │║ 3*245 + 2*25 = 785 ≈ 784 ✓
║ │ 有咲        ars       ││ ひまり      hmr       ││ 麻弥        yamato    │║ each cell = kit.panel(padding=
║ │ 沙綾        saya      ││ モカ        moca      ││ 千聖        cst       │║   Insets.only(20,18,20,18),
║ │ りみ        rimi      ││ つぐみ      tsg       ││ イヴ        eve       │║   radius omitted)
║ │ たえ        tae       ││ 蘭          ran       ││ 日菜        hina      │║ band title text(26, wrap=False,
║ └───────────────────────┘└───────────────────────┘└───────────────────────┘║   max_lines=1, overflow="ellipsis")
║ ┌───────────────────────┐┌───────────────────────┐┌───────────────────────┐║ separator()
║ │ Roselia               ││ Hello, Happy World!   ││ Morfonica             │║ 5 rows, each:
║ │ ─────────────────────  ││ ─────────────────────  ││ ─────────────────────  │║  HStack([Frame(text(24), Fill(),
║ │ 友希那      ykn       ││ こころ      kkr       ││ ましろ      msr       │║   align_x="start"),
║ │ リサ        lisa      ││ 美咲        msk       ││ つくし      tks       │║   Frame(text(22, muted, align=
║ │ 紗夜        sayo      ││ 花音        kanon     ││ 透子        tk        │║   "right"), width=Fixed(88),
║ │ 燐子        rinko     ││ 薫          kaoru     ││ 七深        nnm       │║   align_x="stretch")], gap=8)
║ │ あこ        ako       ││ はぐみ      hgm       ││ 瑠唯        rui       │║  wrapped Frame(height=Fixed(34),
║ └───────────────────────┘└───────────────────────┘└───────────────────────┘║   align_y="center"), gap=6
║ ┌───────────────────────┐┌───────────────────────┐┌───────────────────────┐║ cell h = 18+35+2+12+5*34+4*6+18
║ │ RAISE A SUILEN        ││ MyGO!!!!!             ││ Ave Mujica            │║        = 269 → row_track Fixed(270)
║ │ ─────────────────────  ││ ─────────────────────  ││ ─────────────────────  │║
║ │ パレオ      pareo     ││ 燈          tomori    ││ 祥子        saki      │║
║ │ レイヤ      rei       ││ そよ        soyo      ││ 睦          mzm       │║
║ │ チュチュ    chu       ││ 立希        taki      ││ 海鈴        umiri     │║  ← 海鈴/初華 have no unique ascii
║ │ ますき      masuki    ││ 愛音        anon      ││ 初華        uika      │║    alias in characters.json;
║ │ ロック      lock      ││ 楽奈        raana     ││ にゃむ      nyamu     │║    ALIAS_OVERRIDES supplies these
║ └───────────────────────┘└───────────────────────┘└───────────────────────┘║
║ ┌────────────────────────────────────────────────────────────────────────┐ ║ Starlight gets ONE full-width panel,
║ │  少女歌剧 Starlight                                            30 位    │ ║ names only, no alias column.
║ │  ────────────────────────────────────────────────────────────────────  │ ║ Grid(columns=6,
║ │   華戀    晶      光     未知留   香子    雙葉                           │ ║   column_track=Fixed(112),
║ │   真晝    艾露    珠緒   艾露露   純那   克洛迪娜                        │ ║   row_track=Fixed(38), gap=(8,10))
║ │   真矢    奈奈    壘     文       一愛   菈樂菲                          │ ║ 6*112 + 5*8 = 712 ≈ 720 ✓
║ │   司      美空    靜羽   悠悠子   八千代  栞                             │ ║ text(24, align="center",
║ │   美帆    安德露  瑪莉亞貝菈 克拉迪亞 桃樂西 瑪麗安                       │ ║   wrap=False, max_lines=1,
║ └────────────────────────────────────────────────────────────────────────┘ ║   overflow="ellipsis")
║                                                                            ║ (瑪莉亞貝菈 = 5 glyphs @24 = 120 >
║ ┌────────────────────────────────────────────────────────────────────────┐ ║  112 → ellipsis. Accept, or drop
║ │  /tts 香澄 早上好                            你有 482 Pt · 本次约 1 Pt  │ ║  that row's font to 22.)
║ └────────────────────────────────────────────────────────────────────────┘ ║ usage capsule + pre-flight cost
║                                        ┃ 主题 · 深夜巡演                   ║ signature_for(kit)
╚════════════════════════════════════════════════════════════════════════════╝

Height ≈ 127+32 + (3*270 + 2*25 = 860) +32+ (18+35+2+12+5*38+4*10+18 = 315) +32+ 84 +24+40+112
       ≈ 1658  → 896 x ~1658 (1 : 1.85). The tallest card in the cluster. It is also the
       rarest (once per player, ever, once they learn `ksm`) so the cost is acceptable;
       render with `await page.render_async()`.

UNAVAILABLE characters (in speaker_dict but NOT in the live `speakers` dict from
call_speaker_api) render with color=kit.muted_text_color AND their alias column emptied —
two signals, per leaderboard.py:22-29.
```

### VoiceSlipCard  →  plugins/vits/render/slip.py::render_slip(*, character, text, cost, balance, kit=None)  `[P2/S]`
- **插件**：plugins/vits
- **触发**：the successful synthesis reply of /tts — plugins/vits/__init__.py:188 (audio) + :196 (receipt)
- **目的**：TTS output is audio, so the theme cannot be felt at all on the one surface where the player spent Pt. Today the receipt is a second, separate message (:196) that arrives after the audio. Attaching a small themed slip to the audio message makes tts a themed interaction and removes a message from the group.
- **展示数据**：the character that spoke (subtitle), the text that was synthesized, up to 3 wrapped lines then ellipsis, cost in Pt (vits/__init__.py:162, required_amount), remaining balance (vits/__init__.py:197, monetary.get after the cost), theme signature
- **主题可见性**：Small but present, and it is the receipt that hangs next to an audio bubble in the scrollback — a bystander who cannot hear the audio still sees the themed slip. It is the only way a theme reaches the tts surface at all.
- **manga 单色降级**：Trivially fine: one panel, prose text, two label/value rows, a separator. Nothing color-bearing. The quoted sentence in 「」 brackets is a typographic cue, not a colored one.
- **替代的文本响应**：plugins/vits/__init__.py:196-200 (the '本次语音合成消耗了 N 个星之碎片，你还有 M' receipt). Rides with the existing audio send at :188-194.

```
AutoPage(min_width=640, padding=32)  ·  content 576  ·  VStack(gap=24, align="start")
DELIBERATELY SMALL — this rides next to an audio bubble and must not dominate it.

╔══════════════════════════════════════════════════════╗
║ ┌──────────────────────────┐                         ║
║ │ tts                       │  BD: kit.title_pill(   ║ subtitle = the character, i.e.
║ │ 香澄                      │      "tts","香澄",     ║ the live state (house rule §8)
║ └──────────────────────────┘      pill_width=360,57)║
║                                                      ║
║ ┌──────────────────────────────────────────────────┐ ║ kit.panel(padding=28, radius omitted)
║ │                                                  │ ║
║ │  「早上好呀，今天也要元气满满地加油哦」            │ ║ text(24, wrap=True, max_lines=3,
║ │                                                  │ ║   overflow="ellipsis")
║ │  ────────────────────────────────────────────    │ ║ wrap=True is correct here — it is
║ │                                                  │ ║ the spoken sentence, not a label
║ │  本次消耗        1 Pt                            │ ║ stat_row x2, gap=18,
║ │  剩余            481 Pt                          │ ║ height=Fixed(36) each
║ │                                                  │ ║
║ └──────────────────────────────────────────────────┘ ║
║                              ┃ 主题 · 云母窗          ║ signature_for(kit)
╚══════════════════════════════════════════════════════╝

Height ≈ 127 + 24 + (28 + 3*32 + 20 + 2 + 20 + 2*36+18 + 28 ≈ 300) + 18 + 34 + 64 ≈ 567
→ 640 x ~567 (near square, small).  Render cost is negligible next to the TTS HTTP call.
Sent as ONE message: image_segment(slip) + MessageSegment.audio(...) + pg.element
```

### WifeCard  →  plugins/bang_avatar/render/card.py::render_card(avatar_card, *, wife_name, band, star, attribute, balance, kit=None)  (and plugins/bang_avatar/render/avatar.py::render(...) -> Image.Image, refactored from the current MessageSegment return)  `[P0/M]`
- **插件**：plugins/bang_avatar
- **触发**：/娶群友 · qqy · ccb (rule=has_no_argument) — plugins/bang_avatar/__init__.py:45-47
- **目的**：This is the most-forwarded image the bot produces and it is the ONLY plugin in the cluster whose response is already an image — an unthemed 640x640 BanG Dream! card frame with zero kit involvement. Today the surrounding facts arrive as two trailing text fragments that are concatenated with no separator (bang_avatar/__init__.py:74-75 produces literally `娶到 喵喵 了哦~你手里还有 3 个碎片`), and both are lost the moment someone screenshots or forwards only the picture. Wrapping the card in a themed page and printing the wife's name ON the image makes the shared artifact self-contained AND makes the single most-shared image in the bot carry the owner's theme. Highest leverage in the cluster for the 'yo where'd you get that' goal.
- **展示数据**：the existing 640x640 BanG Dream! card composite (avatar + frame + band icon + attribute icon + stars), the wife's nickname, printed ON the card as a name tag (currently only in trailing text, bang_avatar/__init__.py:74), band name resolved from models.Band (currently only an icon), attribute name + star count as words/glyphs, redundant with the icons already on the art, cost: WIFE_COST from config (bang_avatar/config.py:9, default 2), remaining balance (bang_avatar/__init__.py:75), owner-form theme signature
- **主题可见性**：Highest impact in the cluster. The 640x640 card art is fixed BanG Dream! branding that every player's output shares — the themed page around it is the ONLY thing that differs between two players posting the same command. That contrast is precisely the mechanic the product goal wants: identical payload, visibly different frame, so a bystander attributes the difference to the person rather than to luck. It is also the image people forward, so the theme travels outside the originating chat.
- **manga 单色降级**：The card art itself is full-color and unthemeable — that is fine and correct (it is licensed BanG Dream! art, i.e. content, not chrome). Manga contributes the screentone page, the ink-outlined panels, and the ink label/value rows, which frames the color art like a printed page. The name tag deliberately keeps its hard-coded blue fill with white text: it is a state token on unpredictable art, and its glyph cue is the name string itself, per §10. Star count is shown as ★★★☆☆ AND as the numeral in the art — two non-color cues.
- **替代的文本响应**：plugins/bang_avatar/__init__.py:67-78 — the `render(...) + f"娶到 X 了哦~" + f"你手里还有 N 个碎片"` chain, including the missing-separator bug at :74-75. Requires refactoring plugins/bang_avatar/render.py:41-80 `_render` to return `Image.Image` instead of `MessageSegment` (it is the legacy module utils.theming.image_segment exists to kill, per house style §0) and deleting the duplicate `image_to_message` at plugins/bang_avatar/utils.py:107-118.

```
AutoPage(min_width=752, padding=56, background=_background(kit))  ·  content 640
VStack(gap=32, align="start")

╔════════════════════════════════════════════════════════════════════╗
║ ┌────────────────────────────────┐                                 ║
║ │ 娶群友                          │  BD: kit.title_pill("娶群友",   ║ title = fixed plugin noun
║ │ 喵喵                            │       wife_name, 420, 57)      ║ subtitle = live state (the wife)
║ └────────────────────────────────┘                                 ║
║                                                                    ║
║ ┌────────────────────────────────────────────────────────────────┐ ║ kit.panel(padding=0, radius omitted)
║ │┌──────────────────────────────────────────────────────────────┐│ ║ Overlay([
║ ││ ╔╗  ★                                                  [PURE]││ ║   kit.image(avatar_card,
║ ││ ╚╝  ★                                                        ││ ║     width=Fixed(640),
║ ││     ★         the 640x640 composite produced by               ││ ║     height=Fixed(640),
║ ││     ★         bang_avatar/render.py::_render —                ││ ║     fit="cover",
║ ││     ★         avatar + card-{stars}.png frame +               ││ ║     radius=kit-default? NO — pass
║ ││               band_{n}.png + {attr}.png + star.png            ││ ║     radius=24 explicitly: the source
║ ││               (all from localstore src_path)                  ││ ║     art already has its own border
║ ││                                                              ││ ║   nametag),
║ ││                                                              ││ ║   align_x="center", align_y="end")
║ ││                                                              ││ ║
║ ││                                                              ││ ║ nametag = Frame(
║ ││                                       ┌────────────────────┐ ││ ║   kit.panel(Frame(kit.text(wife_name,
║ ││                                       │      喵喵          │ ││ ║     font_size=36, align="center",
║ │└───────────────────────────────────────└────────────────────┘─┘│ ║     color=(255,255,255,255),
║ └────────────────────────────────────────────────────────────────┘ ║     wrap=False, max_lines=1,
║                                                                    ║     overflow="ellipsis"),
║ ┌────────────────────────────────────────────────────────────────┐ ║     align_x="center", align_y="center"),
║ │  乐队       Poppin'Party                                       │ ║     width=Fixed(280), height=Fixed(56),
║ │  属性       Pure          ★★★☆☆                                │ ║     fill=NAME_TAG_FILL, radius=28),
║ │  ──────────────────────────────────────────────────────────    │ ║   padding=Insets.only(0,0,24,24))
║ │  花费       2 Pt                                               │ ║
║ │  剩余       481 Pt                                             │ ║ NAME_TAG_FILL is HARD-CODED
║ └────────────────────────────────────────────────────────────────┘ ║ (0x34,0x74,0xD6,255) + white text —
║                                                                    ║ same rule as blackjack's
║                                    ┃ 喵喵 的主题 · 霓虹街机          ║ PLAYER_TAG_COLOR (render.py:475-476):
╚════════════════════════════════════════════════════════════════════╝ it sits on unpredictable avatar art,
                                                                       so it is state, not chrome (§10).
Height ≈ 127 + 32 + 640 + 32 + (32 + 2*40+18 + 2 + 18 + 2*40+18 + 32 ≈ 280) + 24 + 40 + 112
       ≈ 1287  → 752 x ~1287 (1 : 1.71, portrait)

NOTE the signature uses the OWNER form: this is a shared surface naming another player,
so `signature_for(kit, owner_name=<caller nickname>)` → "喵喵 的主题 · 霓虹街机".
```

---

## 交互改动

### plugins/help
- **现在**：`/help` prints 14 plugin NAMES and descriptions with no command strings on it (help/__init__.py:171-182). To learn what to actually type you must run `/help <插件名>` (:187-205). The drill-down is mandatory for every single plugin.
- **改为**：The board prints the typeable command string for every entry, so the drill-down becomes optional. `/help <插件名>` survives only for entries that declare `params` or more than 3 usage forms — 猜卡面, 猜谱面, 一笔画, 黑香澄, 探险, 红包, 赛季. For the other ~16 entries the board is the complete answer.
- **为什么更好**：This is the paginated-list-becomes-a-grid case. The drill-down exists today purely because a text line cannot hold both a command and its meaning at a readable density; a tile grid can. Killing 16 of 23 drill-downs turns a two-step lookup into a one-step one for the majority of commands, and it does it for the audience that most needs it — people who just joined the group.
- **移除命令**：removes the *need* for /help <插件名> on 16 of 23 entries; the command itself stays for the 7 deep ones

### plugins/help
- **现在**：The command list is a hand-written `plugin_data` dict at help/__init__.py:19-159 that has drifted from reality. It documents no /gacha (gacha/__init__.py:26), no /背包 (inventory/__init__.py:63), no /装扮 (:111), no /赛季 (:171), no /赛季排行 (:248), no /赛季趋势 (:288), no /赛季历史 (:317), no /profile (:368), and no /id (info/__init__.py:22). It also says nickname costs '30 个Pt' (help:55) while nickname itself says '30 个星之碎片' (nickname:83, :92).
- **改为**：Replace the dict with `plugins/help/registry.py` holding a frozen `HelpEntry(category, command, aliases, summary, usage, examples, params)` list, plus `tests/test_help_registry.py::test_every_loaded_command_is_documented` which walks `nonebot.get_loaded_plugins()` matchers and asserts every registered command name or alias appears in exactly one entry.
- **为什么更好**：A rendered board makes staleness *more* embarrassing, not less — a pretty image confidently omitting a third of the bot is worse than an ugly text list doing the same. The card work is worthless without this, so it is part of the same change, not a follow-up. The registry is also what supplies the `params` chip lists the detail card needs.
- **新增命令**：no new command; adds plugins/help/registry.py + a CI test

### plugins/help
- **现在**：`/help 香澄` → `未找到该插件！` (help/__init__.py:207-210). A dead end with no next step.
- **改为**：Match the token against every entry's command, aliases, and display name. Exactly one match → render that detail card. Several → a one-line text list of the matches. None → text: `没有叫「香澄」的功能，最接近的是 猜卡面 / 昵称 / tts。发送 /help 看全部。`
- **为什么更好**：Cheap, and it is the single most common failure of a help system — the user guesses a synonym. Note the fix does NOT become an image: the miss case is short, actionable, and latency-sensitive, so only the *hit* case renders.

### plugins/info
- **现在**：The theme foundation (§5) says `/主题 <name>` should reply with 'a full sample card already rendered in the new kit', which implies a dedicated sample-card module whose only job is to look nice.
- **改为**：`/主题 <name>` reuses `plugins/info/render.py::render_about` as its confirmation sample, with the header subtitle swapped to `已切换` and the 外观 row already showing the new theme.
- **为什么更好**：A card built solely to be a sample is dead weight that will drift. AboutCard is already the lowest-data, highest-chrome surface in the bot — precisely what a theme sample should be — and reusing it means the confirmation also teaches the player that `/关于` exists. One module, two callers, zero duplicated 'here is what your theme looks like' code.

### plugins/info
- **现在**：Per foundation §5, the theme signature line renders only when the equipped theme is NOT a starter theme, so players on theme_default / theme_minimal see no theme reference anywhere, ever.
- **改为**：AboutCard carries an `外观  霓虹街机 · 已解锁 4/8` row that renders UNCONDITIONALLY, including for starter themes, and a `/主题 切换外观` capsule under it. This is a deliberate, single-surface exception to the suppression rule.
- **为什么更好**：The suppression rule is right for passive surfaces — scarcity does the advertising. But it leaves a hole: a starter-theme player has no in-bot path to discover the mechanic except by seeing someone else's signature and being curious enough to ask. `/关于` is literally the 'what is this bot' command, so naming the cosmetic system there is on-topic rather than an ad. Confining the exception to exactly one low-frequency command keeps the anti-clutter property intact.

### plugins/nickname
- **现在**：First-time success fires TWO messages back to back: `设置成功！以后 Kasumi 就会叫你X啦~` (nickname/__init__.py:78-81) then `首次设置昵称免费，下次修改需要 30 个星之碎片` (:82-86).
- **改为**：One NameplateCard in the JUST_SET state, with `首次设置 免费` and `下次修改 30 Pt` as rows on the same card.
- **为什么更好**：The three-messages-become-one-card case. The second message is a policy footnote that only makes sense attached to the first; splitting them doubles the notification count for one logical event. On a card the policy is a field, not an announcement.

### plugins/nickname
- **现在**：`余额不足！修改昵称需要 30 个星之碎片` (nickname/__init__.py:91-94) states the price but never your balance, so you cannot tell whether you are 1 Pt short or 29. And the price is only ever discoverable by failing.
- **改为**：NameplateCard always shows `下次修改 30 Pt` and `我的余额 482 Pt` — on `/我的昵称`, on set success, and on change success. The refusal stays text but is rewritten to include the balance: `余额不足：修改昵称需要 30 Pt，你有 12 Pt。`
- **为什么更好**：Turns a blind refusal into a rare one. The card is the place the player learns the price before they need it; the refusal only has to handle the case where they ignored it. This is the same pattern as the vits pre-flight cost line and it costs nothing extra on either card.

### plugins/vits
- **现在**：The 75-character roster (vits/__init__.py:116-121) is reachable ONLY as a side effect of running `/tts` with no recognizable character, which immediately drops you into a 60-second `waiter` (:123). You cannot look up 'what's Rinko's alias' without starting a synthesis session you then have to time out of.
- **改为**：Add `/tts -l` / `/tts 角色` / `/tts 列表` as an explicit trigger that renders VoiceRosterCard and returns immediately, no waiter. The no-character path also renders the same card, but that path is now the fallback rather than the only door.
- **为什么更好**：A reference table should be addressable. Right now the only way to read the roster is to accidentally fail at something else, which is a strange thing to require of the plugin's central lookup. It costs one branch at the top of `handle_vits`.
- **新增命令**：/tts -l · /tts 角色 · /tts 列表

### plugins/vits
- **现在**：The roster dump prints names only (vits/__init__.py:118, `f"{k}: {', '.join(v)}"` over speaker_dict), while the message immediately above it (:110) promises '邦邦的角色支持使用别名哦，比如「香澄」可以写成「ksm」'. The feature is advertised and then not shown — you get exactly one worked example for 75 characters.
- **改为**：Every roster cell prints `name` + one romaji alias in a muted right column: `香澄  ksm`. Alias selection is a curated `ALIAS_DISPLAY` table in a new `plugins/vits/roster.py`, seeded from characters.json but NOT derived at runtime.
- **为什么更好**：Derivation is tempting and wrong — I ran it. 'Shortest unique alias' over characters.json yields `dd` for 香澄, `34` for 紗夜, `螺` for りみ, `利息` for 立希, `后悔` for そよ: meme aliases, not teaching aliases. Restricting to unique ASCII improves it (ksm/ars/saya/sayo/rinko) but still picks `dd` for 香澄 and returns empty for 海鈴, 初華, 雙葉, 真晝, 克洛迪娜, 壘. So: derive as a default, override ~8 entries by hand, and put the override table under test.
- **新增命令**：adds plugins/vits/roster.py (ALIAS_DISPLAY + band ordering)

### plugins/vits
- **现在**：Successful synthesis is two messages: the audio segment (vits/__init__.py:188-194) then a text receipt (:196-200).
- **改为**：One message: `image_segment(slip) + MessageSegment.audio(...) + passive_generator.element`.
- **为什么更好**：The result-in-3-messages-becomes-1 case, and the only way a theme can touch the tts output at all — audio has no chrome. Cost is free relative to the TTS HTTP round trip that already dominates this path.

### plugins/vits
- **现在**：The cost formula (`ceil(len(text)/10)`, vits/__init__.py:162) is invisible until you fail the balance check at :164-169, which is also the last step before payment — after you have already sat through up to two 60-second waiter prompts.
- **改为**：The roster card footer carries `你有 482 Pt · 10 字 1 Pt`, and the header subtitle carries the same rate.
- **为什么更好**：Failing a balance check at the end of a two-round-trip conversational flow is the worst possible place to learn the price. Putting the rate on the card that opens the flow costs one text row.

### plugins/bang_avatar
- **现在**：`plugins/bang_avatar/render.py::_render` (lines 41-80) returns a `MessageSegment` built by `BytesIO` + `MessageSegment.image(raw=..., mime="image/png")`, and `plugins/bang_avatar/utils.py:107-118` holds a fifth copy of the same helper (`image_to_message`). The renderer therefore cannot be composed into any layout, cannot take a `kit`, and cannot be unit-tested without a Satori adapter.
- **改为**：Split into `plugins/bang_avatar/render/avatar.py::render(wife_data, src_path, avatar_url) -> Image.Image` (the existing compositing, unchanged) and `plugins/bang_avatar/render/card.py::render_card(avatar_card, *, kit=None) -> Image.Image` (the themed page), with a re-export-only `render/__init__.py`. Delete `utils.py::image_to_message`; the handler uses `utils.theming.image_segment`.
- **为什么更好**：This is the module the house-style doc explicitly names as the thing `image_segment` exists to kill (§0, §14.1). Until it returns `Image.Image` it is structurally impossible for any theme to reach the most-shared image in the bot. The refactor is a prerequisite for the card, not a cleanup afterthought.

### plugins/bang_avatar
- **现在**：`get_user_nickname(wife.id)` is already resolved (bang_avatar/__init__.py:74) but is printed as trailing text, so it vanishes when the image is screenshotted or forwarded alone — which is the dominant way this output is consumed.
- **改为**：The nickname is drawn onto the card as an `Overlay`-anchored name tag (align_y="end"), with hard-coded fill (0x34,0x74,0xD6,255) and white text, mirroring blackjack's PLAYER_TAG_COLOR treatment at plugins/blackjack/render.py:466-476.
- **为什么更好**：Makes the forwarded artifact self-contained, which is the whole point of an image response in a group chat. It also gives the card a second theme-invariant state token that follows §10's discipline (a hard-coded fill paired with a word).

---

## 保留为文本
- **plugins/info** — `/id` → `你的 ID 是: {event.get_user_id()}` (plugins/info/__init__.py:22-28)：The single strongest stays-text case in the cluster. The entire purpose of the response is to hand the user a string they will paste into a bug report, an admin request, or a whitelist entry. Rendering it as an image makes it untypeable without transcribing 10+ digits by hand. There is no version of this that an image improves.
- **plugins/vits** — `TTS 服务出现故障，待会再来试试吧…\n错误码：{code}` (plugins/vits/__init__.py:68-71) and `请求失败\n错误码：{code}` (:183-186)：Same argument as /id, and stronger. `generate_error_code()` (utils/error_handler.py:41-44) returns codes like `KSM-X9F2K1` that exist specifically so the operator can grep the log file for them (error_handler.py:56-60 documents exactly that workflow). A code the reporter cannot copy is a code that gets mistyped. Errors are also the worst possible place to spend 100 ms and a download.
- **plugins/vits** — `请告诉我你想让角色说的话吧~` (:147-150) and both `时间到了哦，流程已结束` timeouts (:126-129, :155-158)：Mid-waiter conversational turns. The user is being asked to type the next thing; anything that delays the prompt directly extends the 60-second window they are racing. A card here also visually implies 'here is a result' when nothing has happened yet.
- **plugins/vits** — `Kasumi不太能理解怎么把这个转成语音呢...` (:75-77) and `Kasumi不太认识这个角色呢...` (:141-144)：Refusals with no payload. The second one should gain a pointer (`发送 /tts -l 查看全部角色`) but stays text — an image would make a 12-character apology cost more than the thing the user was trying to do.
- **plugins/vits** — `你现在共有 N 个星之碎片，但语音生成需要 M 个…` (:165-169)：Two numbers and a verdict. Once the roster card carries the pre-flight rate this becomes a rare path, and when it fires the whole message IS the number — an image adds chrome around information that needs none.
- **plugins/nickname** — The five validation refusals: format error (:34-38), >20 chars (:41-44), contains newline (:47-50), unchanged name (:57-60), name already taken (:70-73)：All are immediate rejections of something the user just typed, and the correct next action is to retype it. Latency between the user's message and the correction is the entire quality measure. `:35` also currently ships raw HTML entities (`&lt;昵称&gt;`) — that gets fixed as plain text, not by rendering.
- **plugins/nickname** — `余额不足！修改昵称需要 30 个星之碎片` (:91-94)：Stays text, but must be rewritten to include the actual balance (it currently does not). The NameplateCard is where the price and balance are learned in advance; the refusal only has to be fast and specific.
- **plugins/bang_avatar** — `余额不足，你手里只有 N 个碎片哦，先赚些星之碎片吧~` (:80-84) and `群里暂时没有人能被你娶到哦~` (:86-89)：Both are pre-render refusals — nothing has been generated, so there is no artifact to frame. The second one is also a channel-state fact (`channels.get_channel_members` returned only the caller), not a player-state fact, so a themed personal card would be misleading about what went wrong.
- **plugins/help** — The `/help <未知>` miss case (:207-210), upgraded to a nearest-match hint：A miss means the user does not yet know what they want. Handing them three candidate words as text they can immediately retype beats handing them a picture they have to read and then retype from. Only the hit case renders.
- **plugins/help** — `/help` in a DM or a low-bandwidth context — no change proposed, but noted：The board is ~896x1561 and is the response to the most-run command in the bot. If group image upload ever becomes a bottleneck, `/help 文字` returning the current text dump is the escape hatch to keep, not a new feature to build now.

---

## 风险
- Help board height. My arithmetic gives 896 x ~1561 (1 : 1.74) for the 3-column / 80px-tile layout, but that is computed from the spacing ladder, not measured — the BD title_pill alone measures 548x127 from a (500,57) request (bangdream/components.py:379-390), and other kits' header will differ. Measure before shipping. Mitigation if it exceeds ~1700: drop the tile's muted alias sub-line, taking row_track from Fixed(80) to Fixed(56) and the page to ~1370.
- bang_avatar resampling. The composite is 640x640 (initialize.py:140 explicitly downscales bestdori card art to 640). Displaying it at Fixed(640) means AutoPage builds a 1280 box at pixel_ratio=2 (core.py:171) and then LANCZOS-downscales the whole page back (layout.py:175-179) — one upsample plus one downsample, i.e. softer than today's raw segment. Blackjack dodges this by displaying source/2 (CARD_WIDTH = 160*2 = 320 from a 640 source, render.py:472-473), but 320px in a group chat is too small to be the hero. Options, in order: (a) stop downscaling to 640 in initialize.py:140/149 and keep bestdori's native size, then display at 640 for a true 1:1; (b) accept the softening; (c) display at Fixed(320) and lose impact. Decide before implementing.
- bang_avatar passes a live PIL Image, not a Path, to kit.image. KitImage `.convert("RGBA").copy()` on every render for in-memory sources and does not use ctx.image_cache (atoms.py:416-421). Unavoidable here — the avatar is fetched per call over HTTP anyway — but it means the WifeCard is the one card in the cluster that gets no image-cache benefit, and the copy happens at 640x640 twice (measure + render).
- Satori multi-segment ordering with audio is unverified. vits/__init__.py:188-194 only ever composes `MessageSegment.audio(...) + passive_generator.element`. Whether `image_segment(slip) + MessageSegment.audio(...) + pg.element` renders as one bubble, two bubbles, or drops the image is platform-dependent. Verify on the live adapter before merging IC 'audio + slip in one message'; the fallback is to keep two messages but make the second one the card instead of the text.
- Currency label is mid-rename and inconsistent across this exact cluster. nickname/__init__.py:83 and :92 say 星之碎片; vits/__init__.py:166 and :197 say 星之碎片; bang_avatar/__init__.py:74 and :81 say 碎片; help/__init__.py:55 says Pt; the most recent commit is 189fbb2 'feat: star kakera -> pt'. Every card design above writes 'Pt'. Pick one label and apply it in the same PR, or the cards will ship the inconsistency in a much more visible form than the text did.
- help's plugin_data is stale by nine commands (verified against every on_command call site: gacha:26, inventory:63/:111/:171/:248/:288/:317/:368, info:22). Rendering a stale list beautifully is worse than rendering it plainly. The registry + `test_every_loaded_command_is_documented` is not optional scope — treat it as part of the P0.
- vits has a live IndexError. `speaker_id = [k for k, v in speakers.items() if v == character][0]` (vits/__init__.py:172) assumes every character `match_character` resolves is present in the API's speaker list. It is not guaranteed: characters.json has 77 keys, speaker_dict has 75 names, and the API list is fetched at runtime (:48-50). The roster card must render from `speaker_dict` intersected with `speakers.values()` and mute the rest, otherwise it will advertise characters that crash on use. Separately, three Starlight names — 雙葉, 真晝, 克洛迪娜 — have no characters.json entry at all, so they are reachable only by typing the exact API name.
- Render cost concentration. The help board (~1561px) and the voice roster (~1658px) are the two largest pages in the cluster and both sit on blocking matchers (help is priority=1). Neither can use the synchronous `page.render()`; both must go through `await page.render_async()` (layout.py:82-100, 181-199). The bangdream image background is the expensive one at ~0.25 s for an 898x898 page — for pages this tall, use `kit.background()` with no source rather than copying graph.py's per-render `BG_DIR.glob` (graph.py:338-345), which is both uncached and unbudgeted.
- Grid with a ragged final row: I verified this is safe — `_tracks` derives `row_count = ceil(len(children)/col_count)` when `rows is None` (layout.py:591) and `render` guards `if child_index < len(self.children)` (layout.py:562). But this deviates from the house convention of pinning both counts (field.py:149). The 社交 category (5 entries, 3 columns) and 猜卡面's 12 chips over 5 columns both rely on it. Note the deviation in the module docstring so nobody 'fixes' it by pinning rows and clipping a cell.
- Theme signature on the help board is a judgment call worth revisiting. The board is the highest-traffic image in the bot, so it is also where a signature line is most repeated. The foundation's suppression rule (starter themes get none) is what keeps it tolerable — but if adoption climbs and most players hold a paid theme, the board footer becomes the most-seen line in the product. Consider suppressing the signature on `/help` specifically once non-starter adoption exceeds ~50%.
