# 赛季制 + 装扮 + 抽卡 重构计划 v3

> 从「碎片经济 + XP 等级」转向「赛季点数 + 装扮抽卡」体系。

---

## 目录

1. [术语变更](#1-术语变更)
2. [点数系统](#2-点数系统)
3. [赛季系统](#3-赛季系统)
4. [装扮系统](#4-装扮系统)
5. [抽卡系统](#5-抽卡系统)
6. [个人信息](#6-个人信息)
7. [绘图与主题](#7-绘图与主题)
8. [实施步骤](#8-实施步骤)

---

## 1. 术语变更

| 当前 | 变更后 | 说明 |
|------|--------|------|
| 星之碎片 / 碎片 | 点数 / Pt | 经济系统核心货币，赛季制 |
| 余额 / balance | `season_points` | 数据库字段名 |
| 星星贴纸 / sticker | 星星贴纸 / 贴纸 (不变) | 抽卡专用，永久保留 |
| XP / 等级 | 不变 | 永久，不随赛季重置 |

---

## 2. 点数系统

### 2.1 核心逻辑

点数（Pt）是**赛季内**经济货币：
- 通过游玩小游戏获得
- 可用于下注（黑香澄 / 探险）
- 每赛季初清零
- 赛季结束时按点数排名发放奖励

### 2.2 与 XP / 等级的协作

点数**不参与** XP / 等级计算。XP 和等级保持永久，不受赛季影响。

```
点数 (Pt)     = 赛季货币 → 下注 / 排名
XP + 等级     = 永久成长 → 等级奖励贴纸
星星贴纸      = 永久货币 → 抽卡
```

也就是说，玩家在赛季中玩游戏能得到：
1. **点数**（排名用）
2. **XP**（永久成长，照现在的逻辑）
3. **星星贴纸**（通过每日任务 / 签到 / 升级获得，抽卡用）

### 2.3 变动的具体文件

| 文件 | 改动 |
|------|------|
| `plugins/monetary/models.py` | `balance` → `season_points`，新增 `season_id` 字段 |
| `plugins/monetary/user_service.py` | 所有 `balance` 引用改名 |
| `plugins/monetary/__init__.py` | 导出名更新 |
| `plugins/daily/__init__.py` | 余额展示改为 "Pt" |
| 所有游戏插件 | 余额相关文本 "碎片" → "Pt" |

新建 `plugins/monetary/season_service.py` 处理赛季相关逻辑。

---

## 3. 赛季系统

### 3.1 参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 赛季时长 | 28 天（4 周） | 每月一季，节奏适中 |
| 起始点数 | 100 Pt | 新赛季每位玩家自动获得，用于起步下注 |
| 点数来源 | 游戏收益 + 签到 + 邮件 | 与当前碎片获取方式相同 |

### 3.2 数据模型

```python
class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    season_number: Mapped[int] = Column(Integer, nullable=False, unique=True)
    start_time: Mapped[int] = Column(Integer, nullable=False)  # unix ts
    end_time: Mapped[int] = Column(Integer, nullable=False)    # unix ts
    is_settled: Mapped[bool] = Column(Boolean, default=False)

class SeasonRanking(Base):
    """赛季结束时快照排名"""
    __tablename__ = "season_rankings"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    season_id: Mapped[int] = Column(Integer, nullable=False)
    user_id: Mapped[str] = Column(String, nullable=False)
    final_points: Mapped[int] = Column(Integer, nullable=False)
    rank: Mapped[int] = Column(Integer, nullable=False)
    reward_json: Mapped[str] = Column(String, default="{}")  # 已发放奖励
```

### 3.3 `User` 表变更

```python
class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True)
    season_points = Column(Integer, default=100)   # 改名 + 改默认值
    season_id = Column(Integer, default=0)          # 当前赛季 ID
    # 以下字段不变
    last_daily_time = Column(Integer)
    level = Column(Integer, default=1)
    xp = Column(Integer, default=0)
    star_stickers = Column(Integer, default=0)
    consecutive_checkins = Column(Integer, default=0)
```

### 3.4 赛季生命周期

**新赛季开始：**
```
1. 管理员调用 /season start（或 Scheduler 自动触发）
2. 创建 Season 记录
3. 所有 User.season_points = 100（起始点数）
4. 所有 User.season_id = 新季节 ID
5. 全服通知（通过邮箱或广播消息）
```

**赛季进行中：**
- 点数经济正常运转
- 玩家实时查看当前排名：`/赛季排行`

**赛季结束（结算）：**
```
1. /season settle（或 Scheduler 自动触发）
2. 冻结当前点数，快照写入 SeasonRanking 表
3. 按排名发放奖励：
   - Top 1:  限定头像框 + 限定称号 + 500 贴纸
   - Top 2-3: 限定头像框 + 300 贴纸
   - Top 4-10: 稀有头像框 + 200 贴纸
   - Top 11-50: 普通头像框 + 100 贴纸
   - 参与奖: 50 贴纸
4. 通过邮箱发放奖励
5. 标记 Season.is_settled = True
```

**赛季更替（结算 → 新赛季）：**
```
结算完成 → 可立即开启新赛季
或设置间隔期（1-3 天 "休赛期"）
```

### 3.5 排名计算

```python
def get_season_ranking(season_id: int, limit: int = 50):
    """当前赛季实时排名（结算前用）"""
    return session.query(User).filter_by(season_id=season_id)\
        .order_by(User.season_points.desc())\
        .limit(limit).all()

def get_season_user_rank(user_id: str, season_id: int) -> int:
    rank = session.query(User).filter(
        User.season_id == season_id,
        User.season_points > get_user(user_id).season_points
    ).count() + 1
    return rank
```

### 3.6 指令

| 指令 | 功能 |
|------|------|
| `/赛季` | 查看本赛季信息：赛季编号、剩余时间、当前排名、点数 |
| `/赛季排行` | 显示赛季点数 Top 排行榜 |
| `/赛季历史` | 查看历史赛季成绩和排名 |

管理员指令：
| 指令 | 功能 |
|------|------|
| `/season start` | 手动开启新赛季 |
| `/season settle` | 手动结算当前赛季 |
| `/season info` | 查看赛季配置 |

### 3.7 赛季点数与 XP 的解耦

点数和 XP 在现有系统中是**同一笔收入分两次入账**（`monetary.add` + `monetary.add_xp`），这个模式不变。区别是点数会随赛季重置，而 XP 永久保留。

```python
# 游戏结算时的调用（示例，一笔画）
monetary.add(user_id, final_reward, "one_stroke")   # 加点数（赛季内）
monetary.add_xp(user_id, final_reward)               # 加 XP（永久）
```

---

## 4. 装扮系统

### 4.1 装扮类型

| 类型 | 说明 | 稀有度 |
|------|------|--------|
| 头像框 (Avatar Frame) | 用户头像外围的装饰框 | N/R/SR/UR |
| 称号 (Title) | 显示在昵称前/后的文本 | N/R/SR/UR |
| 主题 (Theme) | 游戏界面的配色/背景/字体 | SR/UR |

### 4.2 数据模型

```python
class Cosmetic(Base):
    """装扮定义表（游戏预置数据）"""
    __tablename__ = "cosmetics"

    id: Mapped[str] = Column(String, primary_key=True)  # "frame_001", "title_001"
    type: Mapped[str] = Column(String, nullable=False)   # "frame" | "title" | "theme"
    name: Mapped[str] = Column(String, nullable=False)   # 展示名称
    rarity: Mapped[str] = Column(String, nullable=False)  # "N" | "R" | "SR" | "UR"
    description: Mapped[str] = Column(String, default="")
    image_path: Mapped[str] = Column(String, default="")  # 头像框图片路径
    color_theme: Mapped[str] = Column(String, default="") # 主题的配色 JSON
    gacha_weight: Mapped[int] = Column(Integer, default=100)  # 抽卡权重

class UserCosmetic(Base):
    """用户已获得的装扮"""
    __tablename__ = "user_cosmetics"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = Column(String, nullable=False)
    cosmetic_id: Mapped[str] = Column(String, nullable=False)
    obtained_at: Mapped[int] = Column(Integer, nullable=False)
    is_equipped: Mapped[bool] = Column(Boolean, default=False)

class UserCosmeticEquip(Base):
    """用户当前装备（每种类型一个）"""
    __tablename__ = "user_cosmetic_equip"

    user_id: Mapped[str] = Column(String, primary_key=True)
    equipped_frame: Mapped[str] = Column(String, default="")   # 当前头像框 ID
    equipped_title: Mapped[str] = Column(String, default="")    # 当前称号 ID
    equipped_theme: Mapped[str] = Column(String, default="")    # 当前主题 ID
```

### 4.3 装扮来源

| 来源 | 说明 |
|------|------|
| 赛季排名奖励 | 限定头像框 + 称号 |
| 抽卡 | 大部分装扮通过抽卡获得 |
| 成就/特殊活动 | 未来扩展 |

### 4.4 穿戴指令

```
/装扮            → 查看拥有的装扮列表
/装扮 装备 <id>  → 装备指定装扮
/装扮 卸下 <类型> → 卸下某类型装扮
/装扮图鉴        → 查看所有可获得的装扮（灰/亮区分是否拥有）
```

### 4.5 装扮在消息中的呈现

效果参考：

**称号**：在用户昵称前显示（仅 bot 发出的消息中）
```
[雷光の核] Alice: ...
```

**头像框**：目前游戏图片（黑香澄、探险等）左上角用户信息区绘制头像框

**主题**：改变游戏界面的配色 / 背景 / 装饰元素

---

## 5. 抽卡系统

### 5.1 基本参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 单抽价格 | 120 贴纸 | 与现有每日任务体系对齐 |
| 十连 | 1200 贴纸 | 十连 = 10×单抽价格（无折扣） |
| 卡池构成 | 角色 (+ 未来：主题) | |
| UR 概率 | 1% | |
| SR 概率 | 9% | |
| R 概率 | 30% | |
| N 概率 | 60% | |
| 保底 | 90 抽必出 UR | |
| 软保底 | 70 抽起 UR 概率线性提升至 100% | |

### 5.2 UR 概率曲线（软保底）

```
抽数    UR 概率
────────────────
1-69    1%          (基准)
70      5%
71      10%
...
85      90%
86-90   100%        (硬保底)
```

SR 概率 = `9%` (全程固定，被 UR 溢出时挤压)
R 概率 = `90% - UR概率 - 9% - 60%` → 当 UR 概率提升时，R 概率相应降低

### 5.3 卡池权重

每个稀有度内，按 `gacha_weight` 分配。

```
池内总数: 15 个头像框 + 10 个称号 = 25 项

UR (1%):  2 个头像框 + 1 个称号 = 3 项
SR (9%):  5 个头像框 + 3 个称号 = 8 项
R  (30%): 5 个头像框 + 4 个称号 = 9 项
N  (60%): 3 个头像框 + 2 个称号 = 5 项

各稀有度内均匀分布（也可设置权重差异化）。
```

### 5.4 重复处理

抽取到已拥有的装扮时，转化为「星之碎片」：

| 重复稀有度 | 补偿点数（Pt） |
|-----------|--------------|
| N → 重复 | 20 Pt |
| R → 重复 | 40 Pt |
| SR → 重复 | 120 Pt |
| UR → 重复 | 300 Pt |

**为什么不补偿贴纸？** 补偿贴纸会让抽卡 ≈ 贴纸换贴纸，经济闭环塌缩。补偿点数（Pt）是赛季货币，有自然贬值周期，不会造成通货膨胀。

### 5.5 指令

```
/抽卡             → 单抽
/抽卡 十连        → 十连
/抽卡 卡池        → 查看当前卡池内容 + 概率
/抽卡 记录        → 查看抽卡历史
/贴纸            → 查看贴纸余额
```

### 5.6 卡池轮换

- **常驻卡池**：永久可用，包含基础装扮
- **限定卡池**：随赛季轮换，包含赛季限定装扮
  - 限定装扮在赛季结束后不再进入常驻池
  - 未来可通过「复刻卡池」返场

### 5.7 Gacha 动画与反馈

由于是聊天 bot，抽卡结果通过文字 + 图片展示：

```
Alice 抽了 1 次 ⭐

★★★★★ UR ★★★★★
  樱花缭乱 · 头像框
★★★★★★★★★★★★★

[头像框预览图片]
```

不同稀有度使用不同颜色和符号：
- N: 灰色 `◆`
- R: 蓝色 `◆◆`
- SR: 紫色 `◆◆◆`
- UR: 金色 ◆ 特效/彩虹

十连时展示所有结果，高亮稀有物品。

---

## 6. 个人信息

### 6.1 指令

```
/个人信息 或 /info 或 /我
```

### 6.2 展示内容

```
╔══════════════════════╗        ← 头像框（若有）
║  [称号] Alice        ║
║  Lv.15  XP: 1250/1417║
║                      ║
║  本赛季              ║
║  Pt: 2,350  #3 名    ║
║  游戏: 28 局          ║
║                      ║
║  贴纸: ♥ 240         ║
║  装扮: 5/25 收集     ║
║                      ║
║  最长连胜: 5          ║
║  累计签到: 42 天      ║
╚══════════════════════╝
```

### 6.3 数据来源

| 数据项 | 来源 |
|--------|------|
| 称号 | `UserCosmeticEquip.equipped_title` |
| 等级/XP | `User.level`, `User.xp` |
| 点数/排名 | `User.season_points`, `get_season_user_rank()` |
| 游戏局数 | 各游戏统计表 |
| 贴纸 | `User.star_stickers` |
| 装扮收集 | `UserCosmetic` count |
| 签到 | `User.consecutive_checkins` |

### 6.4 图片渲染

个人信息通过**图片**展示（类似排行榜/游戏界面的渲染方式），而非纯文本。这样能集成头像框、主题配色等视觉元素。

```python
def render_profile(user_data) -> Image:
    """渲染个人信息卡片"""
    # 1. 加载用户头像（如果有）
    # 2. 绘制头像框（调用 frame 渲染层）
    # 3. 应用主题配色
    # 4. 填充文本信息
    # 5. 返回 PIL Image
```

---

## 7. 绘图与主题

### 7.1 问题分析

当前各游戏的绘图是各自独立的：

```
plugins/blackjack/render.py      → 直接绘制牌桌
plugins/mines/render.py           → 直接绘制雷区
plugins/one_stroke/render.py      → 直接绘制连线图
plugins/guess_chart/render.py     → 直接绘制谱面（Bestdori 渲染）
plugins/cck/render_card.py        → 直接绘制卡面
plugins/monetary/ranking_service.py → 直接绘制排行榜
```

每个渲染函数各自管理布局、配色、字体。要在所有这些图片中加上玩家信息区域 + 支持主题切换，需要对渲染层进行抽象。

### 7.2 分层渲染架构（建议）

```
┌─────────────────────────────────────┐
│  render_service/                     │
│  ├── canvas.py       画布管理         │
│  ├── layout.py       布局系统          │
│  ├── theme.py        主题引擎          │
│  ├── frame.py        头像框渲染        │
│  ├── text.py         文本渲染（多字体） │
│  └── info_panel.py   玩家信息面板      │
└─────────────────────────────────────┘
```

**`canvas.py`** — 统一的画布起点：
```python
class GameCanvas:
    """每张游戏图片的绘制入口"""
    def __init__(self, width, height, theme_id="default"):
        self.base = Image.new("RGBA", (width, height))
        self.theme = ThemeEngine(theme_id)
        self.info_panel = None  # 由各游戏自行决定是否添加

    def add_info_panel(self, user_data, position="top-left"):
        """在指定位置添加玩家信息面板"""
        panel = InfoPanel(user_data, theme=self.theme)
        self.base.paste(panel.render(), position)
```

**`theme.py`** — 主题引擎：
```python
class ThemeEngine:
    """读取主题配置，提供配色/字体/背景"""
    def __init__(self, theme_id: str):
        config = self._load_config(theme_id)
        self.colors = config["colors"]       # 主色/辅色/文字色/...
        self.background = config["background"]  # 背景图或渐变
        self.fonts = config["fonts"]         # 字体族/字号
        self.decorations = config.get("decorations", [])  # 装饰元素

    def apply(self, canvas: Image) -> Image:
        """将主题应用到画布（渲染背景、装饰等）"""
```

**`info_panel.py`** — 玩家信息面板：
```python
class InfoPanel:
    """在游戏图片角落绘制玩家信息"""
    def __init__(self, user_data, theme):
        self.user_data = user_data
        self.theme = theme

    def render(self) -> Image:
        """描绘信息面板，返回透明背景的图层"""
        # ┌──────────────┐
        # │ [头像框]       │
        # │  Lv.15 称号   │
        # │  Pt: 2,350    │
        # └──────────────┘
```

### 7.3 分步实施

**Phase 1（基础设施）**：创建 `render_service/` 目录，建立画布和主题引擎框架，不修改现有游戏渲染代码。

**Phase 2（信息面板）**：实现 `InfoPanel`，在 2-3 个游戏中添加（黑香澄、探险、一笔画）。此时所有游戏仍用默认主题。

**Phase 3（主题系统）**：定义 3-5 个内置主题，允许玩家通过命令切换。主题仅影响信息面板区域 + 游戏界面的边框/背景。

**Phase 4（深度集成）**：逐步将各游戏的渲染迁移到 `GameCanvas` 体系。这是一个持续优化的过程，不阻塞功能上线。

### 7.4 主题定义示例

```json
{
  "id": "sakura",
  "name": "樱花缭乱",
  "rarity": "UR",
  "colors": {
    "primary": "#FFB7C5",
    "secondary": "#FF8C9E",
    "accent": "#D44D6A",
    "text": "#4A2D3A",
    "background": "#FFF0F5"
  },
  "background": "themes/sakura/bg.png",
  "fonts": {
    "title": "fonts/NotoSansSC-Bold.ttf",
    "body": "fonts/NotoSansSC-Regular.ttf"
  },
  "decorations": [
    {"type": "petal", "x": "10%", "y": "5%", "opacity": 0.3}
  ]
}
```

---

## 8. 关于细节的建议

### 8.1 赛季节奏

- **赛季时长 28 天**比 30 天更好——每周都是完整的周循环，赛季始终在周日结束，方便玩家记忆
- **赛季尾声提醒**：赛季结束前 7 天 / 3 天 / 1 天，通过签到消息自动提醒
- **休赛期**：结算和新赛季之间留 1 天空窗，用于发放奖励 + 公告
- **新玩家补偿**：赛季中途加入的新玩家，起始点数仍是 100 Pt，不会因为晚加入而完全失去排名机会（因为 100 起步远低于活跃玩家的点数，需鼓励连续参与多赛季）

### 8.2 抽卡商业化设计

- **每日免费一抽**：每天首次抽卡免费，刺激日活。由每日签到逻辑赠送一张「免费抽卡券」实现
- **十连无折扣**：保持单抽 = 120 贴纸，十连 = 1200 贴纸。跳过十连动画的需求不大，有十连更多是为了批量抽
- **卡池详情展示**：`/抽卡 卡池` 需展示每个稀有度的具体内容列表，让玩家可以有针对性地规划
- **Cross-season 贴纸保值**：贴纸不随赛季重置，新玩家可以通过多赛季积累追赶老玩家

### 8.3 装扮稀有度与获取

- **限定装扮**必须有视觉区分度（不只是配色不同），否则玩家感受不到"限定"的价值
- **称号**除了文本，可以考虑颜色 + 图标前缀（如 🏆 赛季冠军）
- **头像框**最简单的实现方式：外圈 PNG 图片 + 头像裁切。PNG 图片有透明通道即可叠加
- **装扮图鉴**（`/装扮图鉴`）是重要的留存工具，收集欲驱动玩家持续参与

### 8.4 关于"主题"的建议

目前不建议立刻实现主题，原因：
1. **渲染架构需要先抽象**：当前各游戏渲染代码是平铺直叙的 PIL 绘图，没有统一的画布/图层概念
2. **主题的价值密度偏低**：相对于头像框和称号（简单的文本/PNG 叠加），主题需要修改整个游戏的视觉呈现，投入产出比不高
3. **推荐顺序**：头像框 → 称号 → 主题。头框和称号实现简单、效果直接，主题放到 roadmap 末尾

如果确实想做主题，建议的方案是：
- 把 `render_service/` 的基础设施建好（画布、信息面板）
- 主题引擎只影响面板区域 + 少量装饰元素（如边框颜色）
- 不做全量主题渲染，等玩家对装扮系统有反馈后再深入

### 8.5 头像框渲染参考

最简单的头像框实现（可在 profile 和游戏信息面板中复用）：

```python
def render_avatar_frame(avatar: Image, frame_img: Image) -> Image:
    """将头像嵌入头像框"""
    # 1. 将头像裁切为圆形（或适应框的形状）
    # 2. 缩放 frame_img 到头像尺寸
    # 3. 头像在下层，框在上层（frame 有透明区域）
    # 4. 合并输出
    result = Image.new("RGBA", frame_img.size, (0, 0, 0, 0))
    avatar_resized = avatar.resize(frame_img.size)
    result.paste(avatar_resized, (0, 0), mask=avatar_resized)
    result = Image.alpha_composite(result, frame_img)
    return result
```

头像框 PNG 设计规范：
- 尺寸：120×120 px
- 外圈透明，框线部分不透明
- 中心区域透明（露出头像）
- 常见形状：圆框、六边形框、勋章形框

### 8.6 关于渲染抽象的务实建议

不要试图一步到位重构所有游戏的渲染代码。推荐的做法：

```
1. 创建 render_service/ 目录
2. 实现 InfoPanel（在已有渲染图上叠加一层玩家信息）
3. InfoPanel 本身支持主题（通过传递颜色参数）
4. 各游戏的渲染函数在最后一步添加 InfoPanel
5. 主题引擎慢慢迭代
```

这样信息面板可以立即上线，主题作为一个持续改进的体验目标，随版本逐步优化。

---

## 9. 实施步骤

按依赖关系分 9 步：

| 步骤 | 内容 | 涉及文件 | 依赖 |
|------|------|---------|------|
| **1** | 碎片 → 点数 重命名（数据库 + 代码） | `monetary/models.py`, `user_service.py`, `__init__.py`, 所有插件 | — |
| **2** | Season + SeasonRanking 数据模型 | `monetary/models.py` | 1 |
| **3** | 赛季服务 + 赛季生命周期 + 点数重置 | `monetary/season_service.py`, Scheduler | 2 |
| **4** | 赛季指令（/赛季, /赛季排行） | `monetary/season_cmd.py` 或新建插件 | 3 |
| **5** | 装扮数据模型 + 基础 CRUD 服务 | `plugins/cosmetics/` (新插件) | — |
| **6** | 抽卡逻辑 + 指令（单抽/十连/卡池） | `plugins/gacha/` (新插件) | 5 |
| **7** | 个人信息指令 + 渲染 | `plugins/profile/` (新插件) | 5 |
| **8** | 信息面板 + 游戏集成 | `render_service/`, 各游戏渲染 | 5, 7 |
| **9** | 赛季结算 + 奖励发放 | `monetary/season_service.py`, `plugins/cosmetics/` | 3, 5 |

> **注意**：步骤 6（抽卡）和步骤 5（装扮）紧密耦合，可以一起开发。步骤 9（主题）推迟到后续迭代。

**工作量评估**（粗略）：
- 步骤 1-4（赛季制）：~3-5 天
- 步骤 5-6（装扮 + 抽卡）：~5-7 天
- 步骤 7-8（个人信息 + 面板）：~3-5 天
- 步骤 9 主题系统：推迟到后续版本
