# 魔法少女的魔女审判 · ManosabaKit

基于本机 Steam 游戏 **Magical Girl Witch Trials / 魔法少女的魔女审判** 的原始 UI 素材制作。基础组件返回 `Component`；业务页面先选择插件专属的 `FolioPage` 布局，再渲染成 Pillow 图像。

## 使用

```python
from plugins.render import AutoPage, Frame, VStack
from plugins.render.kits import KITS

kit = KITS["manosaba"]()
page = AutoPage(
    Frame(
        VStack([
            kit.page_title("审判记录"),
            kit.panel(kit.text("新的证言已经收录。", font_size=28), padding=28),
            kit.choice("继续阅读", active=True),
        ], gap=24, align="stretch"),
        width=784,
    ),
    background=kit.background(),
    padding=40,
)
page.render().save("manosaba.png")
# 在异步消息处理器中使用 await page.render_async()
```

- 注册名：`manosaba`；导出类：`plugins.render.kits.ManosabaKit`。
- 主题装扮：`theme_manosaba`；别名包括 `manosaba`、`魔女审判`、`魔女裁判`。
- 现有 `kit_for_user`、`kit_by_name` 和 `utils.cards` 分发器直接支持此主题。
- 拥有该主题后通过现有 `/装扮 装备 魔女审判` 装备。第四赛季将其配置为首次获得六星角色的赠礼及前十排名奖励；不在流星堂常驻售卖。
- 运行时仅使用现有 Pillow 依赖和随 kit 附带的资源；无需 Steam 进程或 UnityPy。

## 视觉构成

灰粉旧纸与淡色正文面板提供清晰的文字底色；炭黑字牌、蔷薇色标题首字、细双线边框、藤蔓角花及菱形分隔构成主题特征。标题直接使用原作墨迹按钮纹理，名片与单抽使用图鉴书页纹理，选项条保留原作左右花饰的比例。角花限制在内边距之内，嵌套面板只保留单线边框，避免列表编号、稀有度和正文被装饰遮挡。

| 元素 | 色值 / 字体 |
| --- | --- |
| 正文与深色容器 | `#2B2227` |
| 蔷薇强调 | `#882B41` |
| 深底标题强调 | `#FF92AE` |
| 纸张底色 | `#E8DBD6` |
| 正文面板 | `#F7EDE5` |
| 次要文字 | `#745F66` |
| 字体 | 游戏内 `Source Han Serif SC SemiBold`，保留完整字库 |

基础组件中三个高曝光表面单独实现：

- `game_identity`：80px 深色身份条，头像、昵称、等级、对局信息；200px 时先省去次要字段。
- `player_card`：旧书页身份档案、固定称号槽位、简介、积分与等级；显式传入的人物图装入右侧证物相框。头像为空显示昵称首字。窄幅省略头像与人物图以保留文字，积分区按等宽两列排列。
- `pull_reveal`：宽幅单抽使用证物框；多抽按可用宽度排列等高卡片，六抽采用 3×2，200px 自动单列。人物图和实际状态信息决定卡片高度。稀有度由星数、边框粗细及最高稀有度徽章共同表达；新获得与精选状态各占一行。

`portrait()` 把原作裁至屏幕边缘的艾玛/希罗侧像按相框内部裁切，其他调用方立绘保持完整比例。原始素材保持原样。`command_tile()` 让帮助页沿用原作选项条，`game_title()` 让探险、一笔画和竞速榜沿用墨迹字牌。

游戏棋盘、卡面和物品图片是业务内容，沿用调用方传入的素材；本 kit 负责页面、字体和卡片容器的风格。空简介和过长文字遵循固定槽位与省略规则。

## 插件专属布局

[`layouts/`](layouts/) 在业务页面构造入口选择布局，直接消费插件自己的展示数据。34 个入口覆盖目前画廊的全部 54 种业务状态。每个插件自行决定宽度、分栏、阅读顺序和重点；`folio.py` 只提供文字测量、线条、图像与延迟绘制工具。

| 插件 | 主题内的信息组织 |
| --- | --- |
| 资料、装扮、赛季 | 双页人物档案、藏品登记册、赛季纪事、带邻近排名的名册与积分观测图 |
| 签到、等级榜 | 连签印记、今日入账、任务状态；玩家侧栏与成长名册 |
| 帮助 | 按分类编排的手册目录、用法与示例对页 |
| 抽卡 | 限定藏品展陈、单抽证物展示、精选大图搭配十连编号图录、入手记录 |
| 邮箱 | 往来信件目录、独立信笺、合计与明细对照的领取回执 |
| 红包 | 赠礼邀请、领取目录、结算与领取记录对页 |
| 黑香澄 | 侧栏指令、庄家与玩家牌桌、规则书、收支账簿 |
| 探险 | 仓库平面图与操作侧栏、探索归档、收益纪要 |
| 一笔画 | 路径棋盘与进度侧栏、竞速记录、完成证书 |
| 猜卡面、猜谱面 | 答案图像与元数据、获胜者与奖励的对页展陈 |
| 巡演 | 四张横排手牌、体力与乐器侧栏、行程结算、分难度竞速档案 |
| 流星堂 | 分类索引、商品图版、主题样张与购买信息对页 |

布局保留原有对局、领取与装扮语义：隐藏的地雷与暗牌不泄漏答案，榜单保留头像框和本人标记，签到任务不误显示为已到账奖励，邮件按实际领取结果与道具作用域配对。邮件的道具目录在调用线程预先解析，异步渲染只执行图像工作。规则页与其他主题共用同一份规则文字。

## 完整示例交付

在仓库根目录执行：

```bash
.venv/bin/python scripts/preview_manosaba.py
```

生成 **`output/manosaba/index.html`**（离线搜索画廊）、**82 张完整 PNG**、`overview.jpg`、5 张分页缩略图和 `coverage.json`。点击画廊中任意缩略图可查看原尺寸。

### Kit 功能：28 张

| API | 示例文件（`output/manosaba/features/`） |
| --- | --- |
| `background()` | `01-background.png` |
| `background(fill=...)` | `02-background-paper.png`、`02-background-ink.png` |
| `text()`：字号、颜色、对齐、中日英与数字 | `03-text.png` |
| `text()`：换行、行数、行高、省略与缩小 | `04-text-overflow.png` |
| `image()`：contain / cover / stretch、透明度、圆角 | `05-images.png` |
| `panel()`：默认、深色、显式圆角、透明填充 | `06-panels.png` |
| `separator()`：横线、竖线、粗细；`ornament()` | `07-separators.png` |
| `page_title()`：中文、英文、长标题 | `08-titles.png` |
| `choice()`：普通、高亮、窄幅 | `09-choice.png` |
| `game_identity()`：头像、有/无等级、对局文字、窄幅 | `10-identity.png` |
| `player_card()`：人物图、空数据、称号与头像框 | `11-player-card.png`、`12-player-card-empty.png`、`13-player-cosmetics.png` |
| `pull_reveal()`：1–10 抽分别渲染 | `14-pulls-01.png` 至 `14-pulls-10.png` |
| `pull_reveal()`：无图、窄幅、空记录 | `15-pulls-no-art.png`、`16-pulls-narrow.png`、`17-pulls-empty.png` |
| 原始 UI 素材对照 | `18-source-assets.png` |

### 业务页面：54 张

`output/manosaba/business/` 中包含：资料完整/空状态、签到与连签升级、等级榜、赛季榜/趋势/信息、装扮背包、帮助总览/详情、卡池有图/无图、单抽/十连/抽卡记录、邮箱普通/密集/空状态、邮件领取/已读/批量领取/无可领取、红包创建/列表/空列表/结算/多人结算、黑香澄帮助/手牌/牌桌/统计、探险棋盘/撤退/失败/统计、一笔画棋盘/排行榜/结果、猜卡面成功/超时、猜谱面成功/超时、巡演帮助/状态/结果/排行榜、流星堂首页/立绘/头像框/主题列表/预览/已购/加抽。

业务图使用真实业务渲染器以及仓库既有测试夹具。测试初始化使用临时 localstore；部分夹具带当前日期，示例时间会随生成日期变化。姓名、原有 BanG Dream! 道具及棋盘占位图片属于测试输入，不代表主题的默认人物或新增游戏功能。Kit 本身在相同输入下确定性渲染。

通用预览命令也可使用：

```bash
.venv/bin/python scripts/render_kits_showcase.py --kit manosaba
.venv/bin/python scripts/preview_kasumi_surfaces.py --kit manosaba
```

## 素材来源与重新提取

本次只选取 **17 张 UI/选项人物 PNG 与 1 份字体**；没有复制整个游戏资源目录。清单见 [`resources/manifest.json`](resources/manifest.json)，逐项记录 Unity 对象名、类型、path ID、bundle 相对路径、原包与输出 SHA-256、尺寸及转换方式。

来源为本机 Steam App **3101040** 的 macOS 安装：

- `general-sprites_assets_all.bundle`：旧纸、书页、藤蔓、菱形、规则线、选项条、字牌、徽章、证物框及艾玛/希罗的原始选项侧像。
- `general-fonts-sourcehanserifsc_assets_all.bundle`：`SourceHanSerifSC` 字体数据。

使用 **UnityPy 1.25.3** 解包。Sprite 通过 `Sprite.image` 恢复图集中的裁切/旋转，再无缩放导出 RGBA PNG；字体直接写出 `Font.m_FontData`。应用中的混色、缩放、裁切均发生在渲染阶段。

```bash
uv venv .cache/manosaba-extract-venv
uv pip install --python .cache/manosaba-extract-venv/bin/python UnityPy==1.25.3
.cache/manosaba-extract-venv/bin/python scripts/extract_manosaba_assets.py
# 非默认 Steam 库：添加 --game-dir /path/to/manosaba_game
# 也支持包含 *_Data/StreamingAssets/aa 的安装目录。
```

提取脚本只读取游戏，并把挑选的素材写入 kit 目录。游戏更新后，清单的哈希可能变化；应重新出图检查。

**资源许可单独保留：**游戏图像版权归原权利人所有，不属于仓库根目录的 MIT 授权。字体是 Adobe Source Han Serif SC，字体名称表中的版权声明已保留于 [`resources/OFL-1.1.txt`](resources/OFL-1.1.txt)，采用 SIL OFL 1.1。此目录里的 Python 代码遵循仓库代码许可。

## 验证

```bash
.venv/bin/python -m pytest tests/test_manosaba_kit.py tests/test_render_kits.py tests/test_theming.py tests/test_cards.py -q
.venv/bin/python -m pytest tests/test_manosaba_plugin_layouts.py -q
.venv/bin/python scripts/audit_manosaba_layouts.py
.venv/bin/python -m pytest -q
uvx ruff check plugins/render/kits/manosaba scripts/extract_manosaba_assets.py scripts/preview_manosaba.py tests/test_manosaba_kit.py
```

专门检查：18 项资源哈希、主题目录解析、1–10 抽与 200/784/1460px 三种宽度、等高网格、None 素材、称号槽位、头像框尺寸、透明合成与绘制裁切、1×/2× 渲染、并发确定性及正文对比度。视觉回归覆盖测量后绘制不丢字、红包/邮箱完整双行提示、中文末行孤字和固定宽度选项条。

业务布局审计以真实测试夹具调用各插件入口，检查 34 个布局均被选中、54 张页面的实际字形边界与文字重叠；报告写入 `.cache/manosaba-layout-audit.json`。另有异步邮件目录访问、头像框、领取数量、待办任务和隐藏地雷的回归检查。自动几何检查仍需配合画廊中的人工视觉复核。

书页保留完整原始素材，以原图 49.5% 处的书脊为界，按布局所需的位置分别拉伸左右两页；破边、水渍、纸张阴影与弯曲折痕随各自纸页一起变形。双栏布局通过 `Sheet.gutter(left, right, top, bottom)` 声明正文空隙，整张背景的书脊随之移动，不另画分隔线或粘贴窄折痕。资料页通常保留至少 32px 的页缝侧距；牌桌等紧凑布局显式指定侧距。通栏信件、签到与多列图录把左页压缩到页边，保留完整右页的层次。基础名片和单抽面板同样按实际内容设置 `book_spine`。布局审计检查字形、图片与框体到页缝的距离，并输出各页书脊位置；中文标点的绘制与换行使用同一套行宽规则。回归测试覆盖左右纸页细节保留、非对称拉伸、整页书脊移动及 1×/2× 渲染。

## 第四赛季

第四赛季「魔女审判 · 未竟的证言」使用双六星并列卡池展陈，以及完整立绘独占面对页的装备档案。13 位角色立绘由本机 `manosaba-sprite-synth` 合成，配套五款原创头像框。配置、概率、来源与重建说明见[赛季素材说明](../../../inventory/resources/items/standing_art/manosaba/README.md)。执行 `.venv/bin/python scripts/preview_manosaba_season.py` 可生成 `output/manosaba-season/index.html`，查看实际赛季的卡池、角色和奖励。
