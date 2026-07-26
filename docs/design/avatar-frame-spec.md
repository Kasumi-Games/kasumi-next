# 头像框素材规格

> 给手绘头像框用的落地规格。画完把文件放到指定路径即可生效，**零代码改动**。

## 文件

| 项 | 值 |
| --- | --- |
| 路径 | `plugins/render/kits/kasumi/resources/frames/avatar_frame.png` |
| 格式 | PNG，带 alpha 通道（RGBA） |
| 画布 | **512 × 512** 正方形 |

kit 启动时自动探测该文件：存在则使用，不存在则回退到代码绘制的占位框
（珊瑚色圆环 + 细金外环 + 两颗金色四芒星）。两者几何完全一致，
所以你随时替换，版式不会变。

## 几何约定

```
┌────────────── 512 ──────────────┐
│                                 │
│      ┌───── Ø416 ─────┐        │
│      │                 │        │
│      │   头像露出区    │        │   ← 这个圆内必须完全透明
│      │  （圆形，居中） │        │
│      │                 │        │
│      └─────────────────┘        │
│  框体艺术区：Ø416 圆以外的      │
│  全部区域，可画到画布边缘       │
└─────────────────────────────────┘
```

- **头像圆：直径 416，画布正中央**。渲染时头像先画（圆形裁剪），框叠在上面，
  框素材按「416 圆 = 头像直径」的比例缩放。
- **Ø416 圆内必须透明**（头像要从这里露出来）。框体元素可以少量侵入圆内
  （比如挂在环上的装饰、星星压住头像边缘），但别挡脸的位置 —— 侵入上限 **48px**
  （顶部/边缘装饰可接受的深度；有测试强制校验，见
  `tests/test_tier_a_kasumi.py::test_asset_respects_the_intrusion_allowance`）。
- **圆外到画布边缘全部可用**，四个角也可以画（比如伸出去的星星、缎带）。
  超出画布的部分会被裁掉。

## 渲染尺寸与笔触

框在实际表面上渲染为 **56–120 逻辑像素**（游戏面板身份条 52px 头像 → 框约 64px；
名片 84px 头像 → 框约 103px），再经聊天客户端二次压缩。因此：

- **主要笔触在 512 画布上不要细于 8px**（对应实际约 1–2px），细于这个会糊掉/消失
- 细节装饰（星星、宝石等）单个不要小于 40px，小于这个在身份条尺寸下不可辨
- 对比度：框会同时出现在深紫夜空面板上，浅色/高饱和描边比深色可靠

## 主题配色参考（星之鼓动 kit 的调色板）

| 用途 | 色值 |
| --- | --- |
| 香澄珊瑚红（主色） | `#FF7662` |
| 香槟金（星光） | `#FFD180` |
| 星光白 | `#F4EEE8` |
| 夜空深紫（底色，画框时避免同色） | `#201A36` |

不必拘泥于这几个色，但框要能在深紫底上立得住。

## 交付后验证

放好文件后跑一遍即可肉眼确认三个尺寸：

```shell
uv run python - <<'PY'
from plugins.render import PlayerIdentity
from plugins.render.kits.kasumi import KasumiKit
from utils import cards
kit = KasumiKit()
identity = PlayerIdentity(nickname="户山香澄", level=42)
cards.response_card(
    kit, title="头像框验证",
    body=cards.game_identity(kit, identity, width=cards.CONTENT_WIDTH, detail="押注 120 Pt"),
).save(".cache/render-previews/frame-check.png")
print("saved .cache/render-previews/frame-check.png")
PY
```

## 将来做成装扮道具时

头像框作为 `avatar_frame` 装扮上线时，素材同样按本规格制作，
经 `items.json` 的 cosmetic 条目挂载（参考 `frame_s1_6star_character` 的占位条目）；
渲染侧 `player_card` 的 `frame_image` 参数已经预留，装备后自动替换主题默认框。
