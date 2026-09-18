# Roselia Render Kit 设计说明

状态：已实现（v1）

日期：2026-09-18

目标注册名：`roselia`

建议玩家名称：`Roselia · 蔷薇穹庭`

## 1. 结论

Roselia 应当作为独立的 `RoseliaKit` 落地，而不是给现有
`BanGDreamKit` 换一套紫色。当前 `bangdream` kit 的核心语言是白色圆角面板、
粉色药丸和现代几何字；Roselia 的稳定识别元素则是：

- 仪式感强的轴线与对称构图；
- 玫瑰、尖拱、彩窗、花冠和植物线框；
- 深蓝紫空间配合象牙白或冷灰蓝信息表面；
- 古典衬线标题与克制的德文/英文副标题；
- 在庆祝状态中使用双层金边、花瓣、玻璃碎光，而不是大面积高饱和填色。

推荐把以下三个官方时期组合成一套适合聊天卡片的系统：

1. `Wahl`：负责深蓝紫空间、冷色玻璃与几何光线；
2. `礎の花冠`：负责浅色信息表面、新艺术花框和长文本可读性；
3. `Für immer`：负责黑金礼仪感、尖拱建筑与资料卡的庄重气质。

`Anfang`、`ROZEN HORIZON` 和 `Rosenchor` 作为高稀有度、结果页与背景变化的补充，
不作为普通正文面板的默认密度。

## 2. 仓库契约

本设计遵守以下现有文档和接口：

- [`BaseKit`](../../plugins/render/kit.py)：基础原子与三个 Tier A 表面契约；
- [`Tier A 表面创作指南`](tier-a-authoring.md)：可读性、确定性、降级与性能约束；
- [`HOUSE RENDER STYLE`](image-responses/00-house-style.md)：页面宽度、字号、间距和主题专属 helper 规则；
- [`utils.cards`](../../utils/cards.py)：共享页面组合与 Tier A 分发器；
- [`KasumiKit`](../../plugins/render/kits/kasumi/kit.py)：仓库中最接近“角色/乐队子主题”的参考实现。

一个完整 Roselia kit 必须提供五个基础原子：

- `background()`
- `text()`
- `image()`
- `panel()`
- `separator()`

并手工实现三个高曝光表面：

- `game_identity()`
- `player_card()`
- `pull_reveal()`

实现只返回 `Component`；页面、页头、保底信息和业务数据继续由调用方负责。

## 3. 素材研究

### 3.1 官方参考索引

下表只作为视觉研究索引。官方图片、角色立绘和 Roselia Logo 不直接复制到 kit 中。

| 参考 | 来源 | 可提取语言 | 在 kit 中的用途 |
| --- | --- | --- | --- |
| `Anfang` | [Bushiroad Music](https://bushiroad-music.com/musics/brmm-10121/) | 放射式巴洛克穹顶、中央玫瑰花环、暖金与暗酒红 | ★6 徽章、单抽英雄构图、特殊完成态 |
| `Wahl` | [Bushiroad Music](https://bushiroad-music.com/musics/brmm-10266/) | 深靛蓝、紫青玫瑰、玻璃质感、细几何光线 | 默认背景、玻璃碎光、现代侧的主色关系 |
| `ROZEN HORIZON` | [Bushiroad Music](https://bushiroad-music.com/musics/brmm-10537/) | 中央消失点、炽热地平线、强烈明暗爆发 | 胜利、升级与特殊结果，不进入普通正文 |
| `Für immer` | [Bushiroad Music](https://bushiroad-music.com/musics/brmm-10788/) | 尖拱窗、象牙白建筑、黑金礼服、宴会式水平秩序 | 资料卡、人物身份、标题与统计区域 |
| `礎の花冠` | [Bushiroad Music](https://bushiroad-music.com/musics/brmm-10854/) | 蓝色新艺术线框、植物拱门、浅色纸面、大量留白 | 默认 panel、边框、分隔线、空状态 |
| `VIOLET LINE` | [Bushiroad Music](https://bushiroad-music.com/musics/brmm-10730/) | 紫色作为“连接”的线性符号 | 状态线、进度、选中态和主题命名 |
| `Rosenchor` | [BanG Dream!](https://bang-dream.com/rosenchor/) | 星空、发光阶梯、冷蓝花瓣、纵深和上升感 | 抽卡高稀有度、排行榜与大型结果页 |
| `Stille Nacht, Rosen Nacht` | [BanG Dream!](https://bang-dream.com/events/roselia2024winter/) | 暗夜、余烬、黑紫礼服、冬季舞台 | 深色变体和节庆页面参考 |
| `Episode of Roselia` | [电影官网](https://roselia-movie.bang-dream.com/) | 白底群像、玫瑰线稿、稀疏编辑排版 | 轻量空状态、帮助页和说明页参考 |
| Roselia 官方定位 | [BanG Dream! Artist](https://bang-dream.com/artist/roselia/) | “本格派”、高技术、暗黑冷峻、追求更高处 | 设计判断的语义基准 |

### 3.2 色彩采样记录

以下数值来自公开封面预览图的缩略图 median-cut 采样，只用于建立工作色板，
不是官方品牌色值。

| 参考 | 主要采样色 | 观察 |
| --- | --- | --- |
| `Anfang` | `#190A0C` `#38201D` `#7B402E` `#C19A77` | 暗酒红承载暖金，密度高、适合徽章而非正文 |
| `Wahl` | `#181B56` `#10246A` `#574498` `#AEE8DD` | 最适合构成默认深色空间和冷光 |
| `ROZEN HORIZON` | `#370503` `#9D1908` `#DC7624` `#EFB857` | 情绪极强，应只用于结果态 |
| `Für immer` | `#554132` `#D5BDA4` `#F2E1C9` `#FEFCF5` | 提供稳定的象牙白、古金与深褐关系 |
| `礎の花冠` | `#F6F4EF` `#96A9CE` `#A5C4DE` `#BEF1F5` | 最适合信息面板、描边与空状态 |
| `Rosenchor` | `#101156` `#1B2D88` `#305CC8` `#9DD5F7` | 提供舞台空间、发光阶梯与高稀有度蓝光 |

### 3.3 字体素材

建议使用两级字体，而不是模仿官方 Logo：

| 角色 | 建议字体 | 来源/许可 | 用法 |
| --- | --- | --- | --- |
| 中日韩正文与中文标题 | Source Han Serif SC SemiBold | [Adobe Source Han Serif](https://github.com/adobe-fonts/source-han-serif)，SIL OFL 1.1 | 正文、昵称、中文标题、数字 |
| 拉丁展示字与德文副标题 | Cormorant SC SemiBold | [Cormorant](https://github.com/CatharsisFonts/Cormorant)，SIL OFL 1.1 | `ROSELIA`、章节号、短英文/德文 |

仓库内已经有一份 Source Han Serif SC SemiBold，位于
`plugins/render/kits/manosaba/resources/SourceHanSerifSC.otf`，并带有 OFL 文本。
实现时不要直接依赖 `manosaba.components`；应在资产层明确选择以下一种方案：

1. 将字体提升为共享 kit 字体资源；或
2. 在 `roselia/resources/fonts/` 中保留独立副本、来源说明和 OFL。

第一版推荐方案 2，避免为了一个新 kit 重排既有资产路径。

## 4. 设计命题

一句话定义：

> 夜色穹顶下的蔷薇礼仪——庄重、克制、向上，而不是普通的“黑紫哥特”。

### 4.1 设计原则

1. **信息表面保持明亮。** 深色负责空间和仪式感，正文面板使用象牙白或冷灰紫，
   使现有业务棋盘、缩略图和彩色状态不会像贴在黑卡上。
2. **对称用在骨架，变化用在光。** 面板、标题和徽章尽量对称；花瓣、玻璃碎光和
   光束可以不对称，但必须播种并保持确定性。
3. **装饰服务层级。** 普通 panel 只有双线和极轻角花；Tier A 才使用完整花冠、尖拱或徽章。
4. **玫瑰不是重复水印。** 一个表面只保留一个强玫瑰焦点，其余使用茎、叶、花瓣或弧线暗示。
5. **避免官方 Logo 临摹。** 主题标记使用原创五瓣蔷薇徽章，不复刻官方 `Roselia` 字标和花体结构。
6. **高稀有度靠结构升级。** 双层边框、冠形徽章、实心星槽和花瓣数量共同表达稀有度，
   颜色只作为辅助信号。

### 4.2 非目标

- 不内置官方角色立绘；
- 不复制官方 Logo、CD 封面、舞台海报或原游戏 UI 切片；
- 不让所有页面都变成全黑或紫色霓虹；
- 不为 Roselia 修改业务数据模型；
- 第一版不在各业务 renderer 中增加 `isinstance(RoseliaKit)` 分支；
- 不把主题上架商店、塞入赛季奖励或主动授予玩家，除非另有产品决定。

## 5. 设计令牌

### 5.1 核心色板

```python
background_top = rgba(12, 9, 22, 255)       # #0C0916
background_bottom = rgba(42, 23, 68, 255)   # #2A1744
text_color = rgba(33, 24, 47, 255)          # #21182F
muted_text_color = rgba(114, 101, 127, 255) # #72657F
panel_fill = rgba(247, 242, 250, 246)       # #F7F2FA @ 96%
paper_fill = rgba(246, 244, 239, 255)        # #F6F4EF
primary = rgba(116, 80, 168, 255)            # #7450A8
rose = rgba(139, 45, 88, 255)                # #8B2D58
accent = rgba(184, 154, 98, 255)             # #B89A62
glass = rgba(157, 213, 247, 255)              # #9DD5F7
rule = rgba(150, 169, 206, 255)               # #96A9CE
```

已检查的 WCAG 对比度：

| 前景 / 背景 | 对比度 | 用途 |
| --- | ---: | --- |
| `text_color` / `#F7F2FA` | 15.40:1 | 正文与重要数据 |
| `muted_text_color` / `#F7F2FA` | 4.90:1 | 标签和注释 |
| `primary` / `#F7F2FA` | 5.51:1 | 图标、短标签、线条 |
| `rose` / `#F7F2FA` | 7.28:1 | 重要状态和玫瑰强调 |
| `#EEE6F2` / `background_top` | 16.16:1 | 深底标题与铭牌文字 |

尽管 `primary` 对浅底达到 AA，填色强调仍统一使用 `cards.emphasis(kit)`，
避免共享组件在主题之间产生不同的可读性规则。

### 5.2 比例

- 70%：象牙白、冷灰紫信息表面；
- 20%：深蓝紫背景和标题铭牌；
- 10%：玫瑰、古金、玻璃蓝强调。

普通业务卡不要同时使用 `rose`、`accent`、`glass` 三种强调；每个表面最多选两种。

### 5.3 几何与间距

- 默认 panel 圆角：`20px`；
- 小 tile 圆角：`12px`；
- 胶囊/身份条：高度的一半；
- 双线边框：外线 `2px`，内线 `1px`，间距 `5px`；
- 主要内边距：`24px` 或 `32px`；
- 微间距：`8 / 12 / 18px`；
- 页面级间距：`24 / 32 / 40px`；
- 尖拱只出现在标题、资料卡或单抽，不用于每个小 panel。

### 5.4 字级

- 正文：`24px`；
- 标签：`22px`；
- Tier A 名称：`26–32px`；
- 页面标题：`40–54px`；
- 拉丁展示标题：`48–64px`；
- 所有固定高度标签必须 `wrap=False, max_lines=1`；
- 拉丁小标题可使用 `2–4px` letter spacing，中文正文不额外拉开。

## 6. 原创视觉资产计划

第一版尽量程序化绘制，只绑定开放字体。建议组件如下：

### `RoseliaBackground`

- 深蓝紫纵向渐变；
- 左上和右下各一组低透明度尖拱彩窗线；
- 少量三角玻璃碎片与花瓣；
- 所有随机位置由 `random_seed` 控制；
- 不绘制可识别的官方 Logo。

### `RoseliaPanel`

- 浅色半透明表面；
- `20px` 默认圆角；
- 外紫线、内冷蓝线；
- 只有边长大于 `180px` 时才画角花；
- 角花必须在局部 layer 内裁切，不能越过组件边界。

### `RoseliaTitle`

- Cormorant SC 拉丁标题或 Source Han Serif 中文标题；
- 标题上下各一条短规则线；
- 中央原创五瓣蔷薇徽章；
- 可选小号德文/英文副标题；
- 长标题逐级缩小到 `24px`，不截断主要标题。

### `RoseCrest`

- 五瓣几何花心、两片叶和一条短茎；
- 使用简单多边形、圆弧和曲线构成；
- 轮廓必须与官方 Roselia Logo 中的玫瑰不同；
- 作为 Pillow 内存图缓存，按 `(size, color)` 使用 `lru_cache`。

### `PetalScatter`

- 3 种原创花瓣轮廓；
- 普通页面透明度 `20–45`，★6 卡 `55–105`；
- 密度以逻辑像素面积计算；
- seed 使用稳定值，例如 `zlib.crc32(name.encode())`，禁止 `hash()`。

### `RoseliaAvatarDisc` 与 `frame_overlay()`

- 默认头像圆盘为冷灰紫；
- 无头像时显示昵称首字；
- unequipped frame 使用双圆环、两片叶和一个小花蕾；
- 装备头像框时，物品资产完全替代主题装饰；
- 遵循仓库 `512px` 画布、中央头像直径 `416px` 的约定。

### 建议资源目录

```text
plugins/render/kits/roselia/
├── __init__.py
├── kit.py
├── components.py
└── resources/
    ├── fonts/
    │   ├── CormorantSC-SemiBold.ttf
    │   ├── SourceHanSerifSC-SemiBold.otf
    │   ├── OFL-Cormorant.txt
    │   ├── OFL-SourceHanSerif.txt
    │   └── SOURCES.md
    └── manifest.json
```

`manifest.json` 记录文件名、上游 URL、版本或 commit、SHA-256、许可和用途。

## 7. 基础原子设计

### `background()`

```python
def background(
    self,
    *,
    fill: ColorLike | None = None,
    bottom: ColorLike | None = None,
    petal_density: float = 0.000025,
    shard_density: float = 0.000018,
    random_seed: int = 617,
) -> Background:
    ...
```

默认 seed `617` 可作为稳定主题常量，不携带业务含义。自定义 `fill` 时仍保留装饰，
除非调用方明确把密度设为 `0`。

### `text()`

- 默认 Source Han Serif SC；
- 额外提供 `font="display"` 供 kit 内部使用；
- 共享 renderer 不传 `font=`；
- `color is None` 时使用 `text_color`，不要用 `color or text_color`，以免透明色被误判。

### `image()`

直接复用 `KitImage`，不添加统一紫色色调或 vignette。业务图片应保持原样。

### `panel()`

- 默认返回 `RoseliaPanel`；
- `radius=None` 使用 `20px`；
- 显式 `radius=0` 必须保留直角；
- `fill=None` 使用 `panel_fill`；
- 不透明业务面板可由调用方传入 fill。

### `separator()`

- 纵向分隔直接使用 `KitSeparator`；
- 横向分隔绘制双端渐隐线和中央小菱形；
- `thickness` 影响主线，不应改变中央标记的整体高度。

### `page_title()`

覆盖基础实现并返回 `RoseliaTitle`。这是 BaseKit 已提供的可移植 hook，
不需要业务 renderer 知道 `RoseliaKit` 类型。

第一版不新增 `game_title()`。当前它不是 `BaseKit` 契约；为了一个主题在多个游戏 renderer
中增加类型分支会扩大范围。游戏页面通过 Roselia 背景、panel 和 Tier A 身份条保持识别度。
如果以后要统一 Kasumi、Mewtype 和 Roselia 的游戏标题，应另行把标题提升为中立 BaseKit hook。

## 8. Tier A 详细设计

### 8.1 `game_identity`

目标：像舞台节目单上的演出者铭牌，而不是缩小版资料卡。

规格：

- 高度：`80px`；
- 宽度：调用方传入，通常 `720px`；
- 背景：`background_top` 上提亮约 8%，不透明；
- 边框：外侧 `primary 2px`，内侧 `glass 1px`；
- 头像：`54px`，主题 frame 约 `66px` 画布；
- 昵称：`26px`，象牙白；
- 等级 chip：`36px` 高，古金描边、深底，不用金色实心块；
- detail：`22–24px`，右对齐；ASCII 可使用 display 字体，CJK 使用正文体。

宽度降级顺序：

1. 宽度充足：头像、昵称、等级、detail；
2. 首次不足：删除等级 chip；
3. 再次不足：删除 detail；
4. 始终保留头像和至少 `96px` 昵称空间；
5. `200px` 仍可测量、渲染且不抛异常。

主题签名只使用双线、花蕾和字体；对局中不铺花瓣，避免每一步棋的图都显得在庆祝。

### 8.2 `player_card`

目标：一张现代化的专辑内页或礼仪档案卡。

默认规格：`784 × 420px`。

布局：

```text
┌──────────────────────────────────────────────┐
│  [头像]  昵称                    右上小蔷薇章 │
│          Lv.42 · 2,350 Pt                    │
│  ─────────── 细双线分隔 ───────────          │
│  [称号槽 1] [称号槽 2]                      │
│                                              │
│  简介，最多 6 行                             │
└──────────────────────────────────────────────┘
```

规则：

- 默认不内置官方角色图；
- `standing_art` 非空时，在右侧 `220–240px` contain-fit，左侧信息区保持固定最小宽度；
- `standing_art=None` 时不保留空列；
- avatar 缺失显示首字；
- title 资产缺失时保留固定 `40px` 槽位，以抽象枝叶短线占位，避免未来资产造成回流；
- 空简介显示 muted 占位“这个人还没有写简介。”；
- 正文区不使用背景花纹，只允许右上角一个低透明度徽章；
- 传入窄宽度时先取消立绘列，再压缩头像，最后隐藏头像；昵称和主要数据始终保留。

资料页当前只有 Kasumi 在没有装备立绘时注入默认立绘。Roselia v1 不修改
`plugins/inventory/render/profile.py`，因此不会产生额外的跨主题特殊分支。

### 8.3 `pull_reveal`

目标：像一组窄幅演出票或唱片收藏卡，视觉高潮来自“晋级仪式”。

布局：

- 1 抽：宽幅英雄卡；
- 2–5 抽：同一行等高卡；
- 6–10 抽：默认 5 列两行；足够宽时允许 10 列；
- `200px`：单列；
- 所有 tile 使用 `Fixed` 轨道，note 为空也保留固定行高。

卡片结构：

1. 顶部窄轨：稀有度、`NEW`、`PICK UP`；
2. 尖拱或轻圆角图片槽；
3. 双线分隔；
4. 名称，最多两行；
5. 星槽与 note。

稀有度编码：

| 稀有度 | 结构 |
| --- | --- |
| ★1–3 | 单线边框、空心星槽 |
| ★4 | 双线边框、顶部小菱形 |
| ★5 | 双线边框、实心星槽、两侧叶片 |
| ★6 | `3px` 外框＋`1px` 内框、冠形蔷薇章、实心 `★6` chip、固定 seed 花瓣层 |

最高稀有度不能只把卡变成金色。古金只用于线和小面积徽章，主体仍保持 Roselia 的冷蓝紫。

## 9. 业务页面表现

不为 Roselia 单独改业务 renderer。共享页面应自然获得：

- 深色渐变背景；
- 浅色双线 panel；
- 衬线正文；
- 蔷薇式分隔；
- `page_title()` 的仪式标题；
- Tier A 的身份条、资料卡和抽卡结果。

以下业务色仍由业务域负责，不被主题重染：

- mines 的格子状态；
- one-stroke 的路径状态；
- blackjack 花色与牌面；
- 邮箱、奖励和货币的语义状态色；
- 用户上传或卡池提供的图片。

## 10. 主题目录与产品接入

注册建议：

```python
KITS["roselia"] = RoseliaKit
KIT_DISPLAY_NAMES["roselia"] = "Roselia · 蔷薇穹庭"
```

主题物品建议：

```json
{
  "item_id": "theme_roselia",
  "category": "cosmetic",
  "name": "Roselia · 蔷薇穹庭",
  "description": "深蓝紫穹顶、冷色彩窗与新艺术蔷薇线框组成的 Roselia 主题。",
  "stackable": false,
  "visible": true,
  "sort_order": 174,
  "cosmetic": {
    "cosmetic_type": "theme",
    "rarity": 6
  },
  "metadata": {
    "kit": "roselia",
    "aliases": ["roselia", "ロゼリア", "蔷薇穹庭"]
  }
}
```

这里只让主题可被目录解析和装备。是否加入 `plugins/ryuseido/shop.json`、
赛季奖励或卡池，由产品层另行决定。

## 11. 实现文件图

必要改动：

```text
plugins/render/kits/roselia/__init__.py       新增
plugins/render/kits/roselia/kit.py            新增
plugins/render/kits/roselia/components.py     新增
plugins/render/kits/roselia/resources/...     新增开放字体与许可
plugins/render/kits/__init__.py               注册 kit 和显示名
plugins/inventory/items.json                  注册 theme_roselia
tests/test_tier_a_roselia.py                  新增专属测试
tests/test_render_kits.py                     更新完整 kit 集合
docs/design/roselia-render-kit.md              本文档
```

不应修改：

- `utils.cards` Tier A 分发逻辑；
- 数据库 schema；
- 业务游戏模型；
- 其他 kit 的颜色或布局；
- profile 默认立绘逻辑。

## 12. 测试与验收

### 12.1 自动测试

- `RoseliaKit` 已注册且继承 `BaseKit`；
- 三个 Tier A 方法均覆盖基类；
- palette 四通道完整；
- 主题物品可通过 `roselia`、`ロゼリア`、`蔷薇穹庭` 和 `theme_roselia` 解析；
- `avatar=None`、`detail=None`、空简介、空 title/frame、`standing_art=None` 均可渲染；
- `game_identity` 在 `200 / 240 / 420 / 720px` 下可测量；
- `pull_reveal` 的 1–10 抽全部可渲染；
- 同一行 tile 等高；
- ★6 与普通卡在灰度下仍有结构差异；
- 两次相同输入输出字节一致；
- 1× 与 2× pixel ratio 均无越界；
- 随机效果不使用 Python `hash()`；
- 必读文字不低于 `22px`；
- 单个常规 Tier A 卡片目标渲染时间 `< 0.15s`。

### 12.2 视觉验收

使用：

```bash
.venv/bin/python scripts/render_kits_showcase.py \
  --kit roselia \
  --output-dir .cache/render-kits

.venv/bin/python scripts/preview_kasumi_surfaces.py \
  --kit roselia
```

人工检查：

- 缩到聊天客户端常见显示宽度后，昵称、积分、稀有度仍可读；
- panel 不会因为花框显得比内容更抢眼；
- 深色背景与彩色游戏格不冲突；
- ★6 有庆祝感，但不变成 `ROZEN HORIZON` 式大面积橙红；
- 不看主题名称也能从尖拱、双线、蔷薇徽章和蓝紫空间识别该主题；
- 与 `midnight` 的区别足够明显：Roselia 更古典、对称、植物性，`midnight` 更简洁和通用；
- 与 `kasumi` 的区别足够明显：Roselia 冷静、庄重、锐利，Kasumi 明亮、温暖、星芒化。

建议验证命令：

```bash
.venv/bin/python -m pytest \
  tests/test_tier_a_roselia.py \
  tests/test_render_kits.py \
  tests/test_theming.py \
  tests/test_cards.py -q

uvx ruff check \
  plugins/render/kits/roselia \
  tests/test_tier_a_roselia.py
```

## 13. 版权与来源边界

Roselia、BanG Dream!、角色形象、官方 Logo、封面和演出主视觉属于其权利人。
本 kit 应只复用不可专有化的设计方法和抽象元素：颜色关系、对称结构、尖拱、植物线框、
原创蔷薇几何与玻璃碎光。

允许提交到仓库的素材：

- SIL OFL 字体及完整许可文本；
- 项目自行绘制的抽象 ornament；
- 程序生成的背景、花瓣和线框；
- 来源、版本、SHA-256 与许可清晰的开放素材。

不提交：

- 官方 Logo 或描摹版本；
- CD 封面、海报截图和角色立绘；
- 从游戏或网站提取、但未单独记录版权状态的 UI 图片；
- 仅用于本设计研究的临时参考图。

如未来确需官方角色立绘，应把它作为独立 `standing_art` 装扮管理，记录来源，
不要让 `RoseliaKit` 在未装备时自动显示。

## 14. 实现顺序

1. 建立开放字体与来源 manifest；
2. 完成 background、panel、separator 和 page title；
3. 渲染基础 showcase，先验证色彩、可读性和与其他 kit 的差异；
4. 完成 `game_identity`；
5. 完成 `player_card`；
6. 完成 `pull_reveal` 及 1–10 抽布局；
7. 注册 kit 和主题物品；
8. 补齐确定性、窄幅、空素材和灰度结构测试；
9. 渲染所有业务页面做视觉巡检；
10. 产品层最后决定商店、赛季或卡池投放方式。

该顺序把最基础、最容易影响所有业务页面的颜色与面板系统放在前面，
避免 Tier A 完成后才发现共享页面不可读而返工。
