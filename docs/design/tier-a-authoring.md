# Tier A 表面创作指南（角色主题填空手册）

给每一个想为角色主题（KasumiKit 是第一个）编写 Tier A 表面的人。
参考实现是 **BanGDreamKit**：`plugins/render/kits/bangdream/kit.py`（三个方法）
和 `plugins/render/kits/bangdream/components.py`（配套组件）。"不将就"是唯一标准：
你的表面必须一眼看出是这个角色的主题，而不是"通用回退换了件外套"。

---

## 1. 什么是 Tier A

三个曝光率最高的表面，每个 kit 手工定制，不走共享组合：

| 表面 | 场景 | 曝光 |
|---|---|---|
| `game_identity` | 每张对局图上方的身份条 | 一局游戏 5-15 张图，每张都有它 |
| `player_card` | `/资料` 的身份卡 | 玩家主动晒出来的那张卡 |
| `pull_reveal` | 抽卡结果格 | 最常被截图转发的画面 |

## 2. 契约（不许偏离）

签名以 `plugins/render/kit.py` 的 `BaseKit` 为准：

```python
def game_identity(self, identity: PlayerIdentity, *,
                  width: SizeValue | int, detail: str | None = None) -> Component: ...

def player_card(self, *, avatar_image, frame_image, title1_image, title2_image,
                nickname: str, level: int, current_pt: int, description: str,
                width: SizeValue | int, height: SizeValue | int) -> Component: ...

def pull_reveal(self, pulls: Sequence[PullRevealItem], *,
                width: SizeValue | int) -> Component: ...
```

规则：

1. **调用方永远只走 `utils.cards` 的分发器**（`cards.game_identity(kit, ...)` 等）。
   分发器用 `type(kit).game_identity is not BaseKit.game_identity` 判定你是否定制过；
   定制了就原样把数据交给你，没定制走通用回退。你不需要也不许改分发逻辑。
2. **`width` / `height` 可能是 `int` 也可能是 `Fixed(n)`**（`game_identity` 收裸 int，
   另外两个收 `Fixed`）。需要具体像素做排版预算时，学 bangdream 的 `_as_px`：
   `Fixed` 取值，其他情况用回退值。
3. **返回 `Component`，不画页面**。背景、页头、保底条都是页面（调用方）的事；
   `pull_reveal` 只是结果格本身。
4. kit 方法内可以在**构建期**量文字宽度（`load_font` + `text_width`）做预算，
   bangdream 的身份条就是这样决定"挤不下就先丢等级 chip、再丢 detail"的。

## 3. 硬约束（评审会逐条验证）

- **对比度**：填色强调只用 `cards.emphasis(kit)` 的组合——深色 `text_color` 底 + 白字。
  **永远不要 `primary` 底 + 白色正文**（bangdream 的 primary 对白只有 3.6:1）。
  primary 留给描边、圆环、装饰线、星星——bangdream 的 ★6 tile 就是
  primary **边框** + 深色横幅 chip，庆祝感一点没少。
- **必读文字 ≥ 22px**，且永远不用 `muted_text_color`。muted 只做标签和装饰
  （空简介占位、note 注释是先例允许的 muted）。
- **None 全都要处理**：`identity.avatar`（画首字母替代，别留洞）、`detail=None`（省略）、
  `frame_image` / `title1_image` / `title2_image`（资产还不存在！布局必须预留槽位，
  资产以后到位时**不能引起回流**——bangdream 用固定高度的标题槽 + primary 装饰条占位）、
  `description=""`（muted 占位文案）、`pull.note=""`（保留行高，保证 tile 等高）。
- **`game_identity` 高度 64-88px**，它在棋盘上方，不是替代棋盘。
- **`pull_reveal` 1-10 抽都要能画**；同一行 tile 必须等高（用 `Grid` 的
  `Fixed` 轨道，别让内容撑高）。稀有度必须有**形状/重量**编码（chip、边框、
  实心/空心星槽），不能只靠颜色。
- **渲染必须确定性**：任何随机效果（星星散布）必须播种（bangdream 用抽数下标做 seed）。
- **性能**：单卡 < 0.15s。贵的逐格美术记得 `lru_cache`；路径素材优于内存 `Image`。
- **isinstance 守卫**：主题专属 helper 只在自己的 kit 里；共享代码里出现必须
  `isinstance(kit, XxxKit)` 守卫（见房规 §9）。

## 4. 填空模板

在 `plugins/render/kits/<theme>/kit.py` 里补三个方法，配套画法放
`plugins/render/kits/<theme>/components.py`（frozen dataclass，实现
`measure(ctx, constraints) -> Size` + `render(ctx, canvas, rect) -> None`，
render 里所有逻辑像素都过 `ctx.scale_px()`）。

每个表面先回答这四个问题，再动手：

1. 这个主题的**视觉词汇**是什么？（bangdream：title pill 双层药丸、48px 圆角、
   primary 圆环、Orbitron 数字；你的主题呢？＿＿＿＿）
2. **庆祝**用什么表达而不违反对比度规则？（边框？描边？散布？形状？＿＿＿＿）
3. avatar/frame/title 为 None 时画什么，槽位怎么留？（＿＿＿＿）
4. 哪些字体安全？展示字体（Orbitron 类）通常**没有 CJK 字形**——bangdream 只在
   `detail.isascii()` 时才用 display 字体，中文一律 chinese 字体。（＿＿＿＿）

## 5. 上线检查清单

- [ ] 三个方法都实现，`type(Kit).surface is not BaseKit.surface` 全为真
- [ ] `avatar=None`、`detail=None`、`description=""`、frame/title 为 None、
      1 抽、10 抽、窄宽度（200px）全部不崩
- [ ] 一行内 tile 等高；★6 tile 与普通 tile 形状可区分（不靠色相）
- [ ] 没有 primary 底 + 白正文；必读字 ≥ 22px 且非 muted
- [ ] 渲染两次字节相同（确定性）
- [ ] 新增测试仿照 `tests/test_tier_a_bangdream.py`；`uv run pytest -q` 全绿
- [ ] 预览图渲进 `.cache/render-previews/` 肉眼过一遍（大小、留白、降采样后可读性）
- [ ] `uvx ruff check <files>` 干净（isort：一行一个符号，按行长排序）

## 6. 参考

- 契约与数据类型：`plugins/render/kit.py`（`PlayerIdentity`、`PullRevealItem`）
- 分发器与通用回退：`utils/cards.py`（回退长什么样，你就要明显比它好）
- 范例实现：`plugins/render/kits/bangdream/kit.py` + `components.py`
- 范例测试：`tests/test_tier_a_bangdream.py`
- 房规全文：`docs/design/image-responses/00-house-style.md`
