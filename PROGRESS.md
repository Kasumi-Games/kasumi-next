# 主题系统 + 图片化响应 —— 进度与计划

> 最后更新：2026-07-26。
> 本文档记录「渲染主题 + 图片化响应」这条工作线的全部进度、已定决策与后续计划。
> 赛季制/抽卡/装扮的总体重构计划见 `UPDATE.md`；本文是它的渲染与呈现分支。

---

## 目录

1. [产品目标](#1-产品目标)
2. [已定决策（含理由）](#2-已定决策含理由)
3. [已完成的工作](#3-已完成的工作)
4. [后续计划](#4-后续计划)
5. [已知欠账与待办](#5-已知欠账与待办)
6. [技术备忘（后续开发必读）](#6-技术备忘后续开发必读)

---

## 1. 产品目标

两句话：

1. **玩家自己**在每次交互中都能感到「我在用这个主题」；
2. **群里的旁观者**能看出别人在用一个好看的主题，并产生「yo dude 你这主题哪来的」的反应。

因此评价一切呈现工作的标准是：主题是否**可见**、**可辨认**、**可获得**。
纯粹把文本换成图片不是目标；目标是用图片扩展和改进交互本身。

---

## 2. 已定决策（含理由）

### 2.1 角色主题优先，现有主题经济暂缓

- 第一期角色主题围绕 **Kasumi（户山香澄）**，与 gacha 一同发布。
- 现有 8 个 kit（见 3.1）**保留但不发行**：不做盆栽商店、不加主题道具、不做 `/主题` gallery。
  这些设计已完整留档（`docs/design/image-responses/01-theme-plumbing.md` §2/§5），等角色主题定稿后再取用。
- 例外：`theme_s1_sailing`（唯一已存在的主题道具）已接通 sailing kit —— 它本来就是照着这个道具做的，接通不算发行新主题。

### 2.2 Tier A / Tier B 分层（「不将就」的落地方式）

用户要求游戏面板等高价值表面**每个主题单独手写适配**（不将就）。无差别套用会导致
「50 张卡片 × N 个主题」的不可行工作量，因此分两层：

| 层 | 做法 | 范围 |
| --- | --- | --- |
| **Tier A** 专属适配 | 每个主题手写一版，放进各 kit 自己的 `components.py` | 仅 3 个表面：**游戏面板身份区**、**玩家名片**（`BaseKit.player_card`）、**抽卡结果** |
| **Tier B** 通用组合 | 用 `BaseKit` 原子组合，写一次八主题通用（`utils/cards.py`） | 其余全部：邮箱、帮助、列表、回执、统计、排行 |

判定规则（一句话）：**这张图会不会被不认识你的人在群里刷到、且看到时会产生情绪？会 → Tier A；只是自己查东西 → Tier B。**

选这 3 个 Tier A 表面的依据（来自设计评审的实测）：mines 一局向群里发 5–15 张面板图、
one_stroke 每步一张 —— 游戏面板的主题曝光量是个人资料卡的 10–50 倍。

### 2.3 「卡片」术语约定

本工作线所有「卡片 / Card」均指 **UI 版式**（圆角面板式的图片响应），
不是 BanG Dream 意义上的游戏卡牌。为避免混淆，中文语境用「**图片版式**」。
游戏卡牌内容属于 gacha 工作线，本文不涉及。

### 2.4 对比度规则（实测得出，测试固化）

以下两条写死在 `utils/cards.py`，并有**每次运行时重新测量**的测试守护（`tests/test_cards.py`）：

1. **填充强调块 = `kit.text_color` 填充 + `kit.panel_fill` 前景。**
   否决的方案「`kit.primary` 填充 + 白字」在 8 个主题中 4 个低于 AA
   （sakura 2.16:1、midnight 2.59:1、neon 3.43:1、bangdream 3.60:1）；
   新规则在全部 8 个主题 ≥ 6.58:1。`primary` 只用于非填充装饰（进度条填充、细线）。
2. **`muted_text_color` 只做标签/脚手架，不承载必读信息。**
   sakura 上仅 2.72:1。空状态提示语按此规则用正文色（它是空卡片的全部内容，属必读）。

### 2.5 统一几何

内容列 **784px**、面板内边距 **32**、内部宽 **720**、页边距 **40**；
字号阶梯 40/26/24/22，**必读文本下限 22px**（`pixel_ratio=2` 超采样 + 客户端二次压缩下的可读底线）。
所有卡片同宽（测试断言八主题渲染宽度只允许一个值），跨插件网格、将来的并排对比才能成立。

---

## 3. 已完成的工作

### 3.1 渲染主题（8 个 kit）✅

`plugins/render/kits/`，全部注册于 `KITS` 字典，显示名在 `KIT_DISPLAY_NAMES`：

| kit | 显示名 | 风格 |
| --- | --- | --- |
| bangdream | BanG Dream! | 默认主题（原有） |
| minimal | 极简 | 白底灰面板（原有；本期修复中文豆腐块） |
| midnight | 午夜 | 夜空渐变 + 星尘，靛蓝辉光面板 |
| sailing | 扬帆 | S1 海洋：天空渐变 + 波浪带，奶油面板深蓝饰条 |
| sakura | 樱色 | 粉奶油渐变 + 飘落花瓣，暖粉投影圆角卡 |
| neon | 霓虹街机 | 近黑底 + 透视网格/扫描线，霓虹管描边 |
| manga | 漫画分镜 | 单色：网点纸 + 速度线，重墨描边 |
| fluent | Fluent | Windows 11：Mica 材质、8px 圆角、控件描边 + 顶部高光 |

支撑设施：

- `plugins/render/kits/atoms.py` —— 无视觉身份的共享机械原子（KitText/KitImage/KitPanel/KitSeparator、渐变、软阴影），kit 只写视觉签名，不重复排版数学
- `plugins/render/kits/fonts.py` —— 共享字体路径（CJK 字体 + 展示字体）
- `BaseKit` 增加调色板契约：`text_color` / `muted_text_color` / `panel_fill`（浅色默认值，深色 kit 覆盖）
- 游戏渲染器（mines / one_stroke / blackjack）的硬编码浅色回退已改为读 kit 调色板
- 预览：`uv run python scripts/preview_renderers.py all --kit all`（`--kit` 支持全部 8 个名字）

### 3.2 设计产出（留档）✅

10-agent 设计 workflow 的完整产出存于 **`docs/design/image-responses/`**（11 个文件，约 550KB）：

| 文件 | 内容 |
| --- | --- |
| `00-house-style.md` | 现有渲染器的房屋风格：页面几何、字号、命名约定（实测数字） |
| `01-theme-plumbing.md` | 主题解析设计：kit_for_user、失败降级链、署名机制、items.json 方案 |
| `10`–`15` | 六个插件簇共 **50 张图片版式**设计（含 ASCII 稿）、62 项交互改动、保留文本清单 |
| `90-consistency-review.md` | 一致性评审：21 项跨簇冲突与对比度实测 |
| `91-ambition-review.md` | 野心评审：结构性盲点（见下）与出货顺序建议 |

野心评审的两个核心发现（已纳入决策）：
- 主题经济当时不存在（唯一主题道具、盆栽零去处）→ 促成「角色主题优先」决策
- 游戏面板是曝光量最大的表面却完全匿名 → 促成 Tier A 三表面的选定

### 3.3 阶段 0：基础设施 ✅

| 模块 | 内容 |
| --- | --- |
| `utils/theming.py` | `kit_for_user(user_id)` 主题解析：TTL 缓存（120s / 故障 5s）、降级链 `用户主题 → bangdream → minimal`、坏 kit 每进程只试一次；`theme_by_token()`（中文名/别名/id 均可）；`validate_theme_catalog()`（CI 硬失败，启动只记 ERROR）；`all_themes()` / `unclaimed_kits()` |
| `utils/images.py` | `image_segment()` / `image_bytes()`：PNG 编码（JPEG 色度抽样会毁掉 neon 管边和 sakura 粉字）。原 4 处重复实现（bang_avatar×2、one_stroke、cck）已收敛为委托 |
| 失效钩子 | `equip_cosmetic` / `unequip_cosmetic` → `invalidate_user`；`sync_catalog` → `invalidate_catalog` |
| 目录接通 | `theme_s1_sailing` 补上 `metadata.kit: "sailing"` + 别名；`/装扮 扬帆` 现在真实改变渲染 |

三条硬性不变量（均有测试）：**永不抛异常、永不写库、只在事件循环线程调用**（原因见 §6.1）。

### 3.4 Tier B 工具箱 ✅

`utils/cards.py`：`emphasis` / `badge` / `stat_row` / `meter` / `ladder_rows` /
`empty_state` / `panel_section` / `theme_signature` / `signature_for` /
`card_page`（**全项目唯一的标题构造器** —— `kit.title_pill` 只有 BanGDreamKit 有，
无保护调用会崩掉其余 7 个主题）/ `response_card`。

### 3.5 阶段 1：mailbox + help 图片化 ✅（已对抗式验收）

| 插件 | 版式 | 交互变化 |
| --- | --- | --- |
| mailbox | InboxCard / MailDetailCard / ClaimAllCard（`plugins/mailbox/render/`） | 列表一图取代分页；**新增 `/邮件 领取`** 一键领取（幂等键 `mail:<id>`，有防重复发放测试）；`/邮件 M42` 稳定编号 |
| help | HelpBoardCard / HelpDetailCard（`plugins/help/render/`） | 23 条命令按 游戏/养成/社交/工具 分组一张命令板；`/help 功能名` 详情卡 |

验收核实项：96/96 卡片×主题渲染通过；`kit_for_user` 仅在 handler 调用；无未保护 kit 专属方法；必读 ≥22px 且不用 muted；错误/拒绝保持纯文本；每条回复路径带 passive element。
管理员定时邮件命令按设计保持纯文本。

### 3.6 顺手修掉的存量 bug

- **MinimalKit 中文豆腐块**：`MinimalText` 不传字体路径 → PIL 默认字体无 CJK。已改用 `KitText` + 共享 CJK 字体；minimal「构造零文件依赖」的兜底性质不变（`load_font` 缺文件时回退不抛）
- **`/schedulemail edit` 回复缺 passive element**（HEAD 上即坏，验收 agent 修复）
- 三处 `_title_bar` 回退在浅色面板上画白字（不可见）；一致性评审多处对比度问题在工具箱层面根治

### 3.7 测试基线

**205 passed + 179 subtests**（会话开始时 110）。新增：
`test_render_kits.py`（kit 契约/确定性/调色板）、`test_theming.py`（缓存/降级/目录）、
`test_cards.py`（对比度实测/几何/确定性）、`test_mailbox_render.py`、`test_help_render.py`、`test_help_handler.py`。

---

## 4. 后续计划

### 阶段 2：Tier A 契约 + bangdream 样板 ✅（2026-07-26 完成，已对抗式验收）

已交付（测试基线 205 → **243**，识别条 `identity=None` 时面板输出**字节级不变**）：

1. **契约**：`BaseKit.game_identity / player_card / pull_reveal`（`plugins/render/kit.py`），
   数据类 `PlayerIdentity` / `PullRevealItem` 从 `plugins.render` 导出。
   调用方唯一入口是 `utils/cards.py` 的三个同名调度函数 ——
   `type(kit).X is not BaseKit.X` 判定走专属还是通用回退：**没做专属的主题不崩，做了的主题全权控制**。
2. **通用回退**：三个表面的原子组合版（八主题通用），`utils/identity.py::identity_for` 组装昵称/等级
   （与 theming 同规矩：不抛、不写、事件循环线程；头像留 `avatar=` 参数等缓存就绪）。
3. **bangdream 样板**：三个表面的专属实现（环形头像胶囊条、名片、★6 主色描边+撒星揭示瓷贴），
   与回退版视觉可区分（验收逐图核对）。**角色主题填空指南：`docs/design/tier-a-authoring.md`** ——
   KasumiKit 按此文档作业。
4. **落地**：mines / one_stroke / blackjack 全部 18 处渲染调用点接入身份条（handler 解析一次传入）；
   `/资料` 渲染名片页（简介设置保持文本）；`/抽卡` 单抽/十连渲染揭示页（保底页脚为真实数据，
   info/history/错误保持文本）。
5. 验收顺手修的两处：one_stroke 残留 F401、mines 手写编码块改用 `image_segment`。

已知边界（验收如实记录）：捆绑发放（★6 附带头像框/主题）时 `is_new` 徽章保守省略而非造假
（需 gacha service 提供逐物品结果，属阶段 4 的 service 改动）；付费抽卡后渲染失败走「抽卡失败」
文本路径（发放已持久化，与邮箱领取先例一致）。

### 阶段 3：KasumiKit ✅ kit 本体完成（2026-07-27，双视角对抗验收通过）

视觉方向已定并实现（测试基线 262）：

- **背景**：深紫夜空渐变（非纯黑）+ 低透明星云色漂 + **四芒光斑**（✦，白/香槟金/淡粉/淡青，
  大颗带柔光晕）—— 按用户要求「不用真的黄色五角星，艺术化加工」。种子固定，跨进程逐字节可复现。
- **配色**：主色 = 提亮的香澄珊瑚红 `#FF7662`（只做环/描边，不做浅字底）；第二声部香槟金
  `#FFD180`（Lv 徽章金底深紫字，实测 13.8:1）；正文星光白 14.8:1、muted 6.9:1，全部远超 AA。
- **立绘**：Bestdori 卡面 425「仰望星空」trim 图（特训前后两张）已入
  `plugins/render/kits/kasumi/resources/standing/`，名片右列渲染 576×516（只缩不放，无模糊）。
- **三个 Tier A 表面**全部专属：胶囊身份条（窄宽降级：先丢徽章再丢 detail，名字永不消失，有回归测试）、
  立绘名片（称号槽已预留 —— 0/1/2 个称号图尺寸完全一致不回流）、十连揭示（★6 = 金链章 + 珊瑚描边 + 
  专属闪光，crc32 种子）。
- **头像框**：规格文档 `docs/design/avatar-frame-spec.md`（512×512、中央 Ø416 透明圆、笔触下限、
  主题配色参考）；占位框为代码绘制，**用户手绘稿放进
  `plugins/render/kits/kasumi/resources/frames/avatar_frame.png` 即生效，零代码改动**（已用假资产实测替换路径）。
- **目录**：`theme_kasumi_starbeat` 已进 items.json（别名 香澄/kasumi/星之鼓动/starbeat），
  署名读 kit 显示名（「香澄 的主题 · 星之鼓动」，修掉了「…主题·…主题」冗余）。

**阶段 3 余量（等用户）**：手绘头像框素材；主题的发放途径（归阶段 4 gacha）。

### 阶段 4：Kasumi gacha ✅（2026-07-27 完成，三 agent 实现+双验收）

测试基线 262 → **291**。已交付：

- **赛季重构（用户决定）**：「Kasumi，扬帆起航」整季**作废**（从未上线）；
  **星之鼓动 = 第一赛季**，`2026-s01`，**2026-08-01 → 08-29**（UTC+8，纯 JSON 可调）。
  扬帆季专属道具（称号×5/排名框×4/立绘×2）已从 items.json 移除；`theme_s1_sailing` 保留
  （sailing kit 的映射，暂无发放途径，留待复用）；星之鼓动奖励道具改用 `*_starbeat` 家族命名。
  `sync_seasons_config` 新增废案清理：配置中消失、仍为 planned、无任何玩家数据的赛季行自动删除
  （有历史数据的孤儿赛季永不自动删，各有测试）。
- **S2 星之鼓动内容**：单 featured 户山香澄（立绘 = 卡面 425，`metadata.art` 指向 kit 资源）；
  首个 ★6 捆绑发放 立绘+六星头像框+**星之鼓动主题**；排名 1–3 也发主题（设计文档允许的双通道）；
  参与/排名奖励镜像 S1（鼓动系称号×5 + 排名头像框×3）；费用/保底/概率与 S1 一致；填充池复用占位道具。
- **逐道具发放明细**（阶段 2 遗留的 `is_new` 精确化）：`GachaResult.grants: tuple[GrantDetail, ...]`；
  NEW 徽章按被抽道具自身的发放判定（捆绑重复不再抹掉 NEW）；`grant_message` 与 DB 行完全不变。
- **揭示页升华**：★6 瓷贴渲染真立绘（kasumi/bangdream 专属 + 通用回退三处，批次驱动的统一瓷贴高度）；
  新增「**同时获得：…**」页脚（handler 侧解析道具名/立绘路径，渲染层保持无 DB）。
- 验收修正：通用瓷贴「NEW · PICK UP」窄格时保 NEW 弃 PICK UP（实现者称无法测宽的理由被证伪 ——
  九个 kit 正文都用共享 CJK 字体）；瓷贴行高上限修掉两行名字顶破边框的存量溢出。
- 独立复核过的硬事实：十连恰好扣费一次、幂等键全唯一、二次抽同 featured 不会重复发主题
  （数量恒为 1）、跨进程渲染逐字节一致。

**留待用户**：手绘头像框素材（`frame_kasumi_starbeat` 暂无 `metadata.art`）。
赛季顺序已定：星之鼓动打头阵，8 月 1 日开季。

### 阶段 1 余量（Tier B，可穿插进行，无依赖）

按「文本密度 × 情绪价值」排序的剩余高价值版式（设计稿都在 `docs/design/image-responses/`）：
签到卡（CheckinCard）、红包卡（EnvelopeCard，设计文档指明**只在创建和完成时渲染**，
单次抢红包保持文本）、排行卡（RankCard，用 `ladder_rows`）、
游戏结果合并卡（GameResultCard —— 现在每局结束是 3–4 条连发消息）、统计卡（blackjack/mines）。

---

## 5. 已知欠账与待办

| 项 | 说明 | 归属 |
| --- | --- | --- |
| `plugin_data` 内容过时 | help 命令板忠实渲染现状：缺 `/gacha` `/背包` `/装扮` `/赛季` 系列等 9 条命令；补数据后命令板自动更新 | 内容 |
| matplotlib 图表破坏主题 | `inventory/season_render.py`、`blackjack/stats_service.py`、`mines/stats_service.py` 三处 matplotlib 图不走 kit 体系 | 阶段 1 余量 |
| emoji 无字形 | `old.ttf` 无 emoji 覆盖：`daily/__init__.py:111` 的 🎉、blackjack/mines 统计文本的 🎴📊 等，进图片会变空框 | 图片化时顺手清理 |
| 货币用语漂移 | 「Pt / 碎片 / 星之碎片」在各插件文案中不一致（一致性评审 §9） | 内容 |
| 渲染性能 | 重卡片冷渲染最坏 0.67s（midnight 30 封邮件溢出）；已有缓解（render_async、行数上限），未做进程级缓存 | 观察 |
| 署名抑制规则 | 「入门主题不显示署名」的设计基于旧主题经济，角色主题时代稀缺性分布不同，**需重新设计**再启用 | 阶段 3 |
| 你的 WIP 的 lint | `plugins/gacha`、部分测试文件有 13 个 isort 错误（`uvx ruff check --fix` 可清），属会话开始前的未提交工作，未代改 | 用户 |

**明确推迟**（设计已留档，勿重复设计）：盆栽商店、8 主题道具化、`/主题` gallery、
通用版 GameIdentityStrip（被 Tier A 专属版取代）、成就系统、低稀有度装扮。

---

## 6. 技术备忘（后续开发必读）

### 6.1 线程规则（最重要的一条）

`kit_for_user` **必须在事件循环线程（即 handler 内）调用，把 kit 实例传进渲染函数**：

```python
kit = kit_for_user(event.get_user_id())          # handler 内
image = await page_for(data, kit).render_async()  # 渲染可以下线程
```

原因：`plugins/inventory/database.get_session()` 是进程级全局 SQLAlchemy Session
（非线程安全，冷调用还会触发完整 `init_database()`），而 `render_async` 会把渲染
offload 到线程池。渲染函数签名一律 `render_x(data, kit: BaseKit | None = None)`，
`kit = kit or BanGDreamKit()` 写在函数体内（不能做默认参数 —— 会在 import 时构造）。

### 6.2 新增一个主题的完整步骤

1. `plugins/render/kits/<name>/`：`kit.py`（继承 `BaseKit`，覆盖调色板）+ `components.py`（签名视觉）+ `__init__.py`
2. 注册进 `plugins/render/kits/__init__.py` 的 `KITS` 和 `KIT_DISPLAY_NAMES`
3. `items.json` 加主题道具，`metadata: {"kit": "<name>", "aliases": [...]}`（经 `catalog.py` 现有同步管道，零迁移）
4. 跑 `tests/test_render_kits.py` 与 `tests/test_theming.py` —— kit 契约、目录校验、显示名齐全性都会自动覆盖新主题

### 6.3 写新卡片（Tier B）的规则

- 只用 `utils/cards.py` + `BaseKit` 原子；标题必须走 `card_page`
- 填充强调用 `emphasis(kit)`；必读文本 ≥22px 且不用 `muted_text_color`
- 错误/拒绝/简短确认**保持文本**（图片有渲染 + 上传成本）
- 每条回复：`image_segment(img) + passive_generator.element`，`referrer=passive_generator.event.referrer`
- 渲染模块放 `plugins/<p>/render/<subject>.py`，包 `__init__.py` 纯 re-export
- import 风格：ruff isort，单行单符号、按行长排序（`uvx ruff check --fix` 即可）

### 6.4 定位速查

| 东西 | 位置 |
| --- | --- |
| 主题解析 / 目录校验 | `utils/theming.py` |
| 图片编码 | `utils/images.py` |
| Tier B 工具箱 | `utils/cards.py` |
| kit 注册表 / 显示名 | `plugins/render/kits/__init__.py` |
| 共享原子 / 字体 | `plugins/render/kits/atoms.py` / `fonts.py` |
| 设计文档（50 版式 + 评审） | `docs/design/image-responses/` |
| 预览脚本 | `scripts/preview_renderers.py`（`--kit all`） |
| 预览输出 | `.cache/render-previews/` |
