# 第四赛季 · 魔女审判 · 未竟的证言

赛季配置：`plugins/inventory/seasons.json` 中的 `2026-s04`。北京时间 UTC+8：2026-10-27 00:00 开始，2026-11-24 00:00 结束。沿用第三赛季结束后一天休赛期、28 天赛季、初始 100 Pt 的节奏。

卡池包含 13 位角色：

| 星级 | 角色 | 基础合计出率 |
| --- | --- | --- |
| 六星 | 樱羽艾玛、二阶堂希罗 | 1%，同档等权，各 0.5% |
| 五星 | 汉娜、雪莉、诺亚、可可 | 20%，同档等权，各 5% |
| 四星 | 梅露露、亚里沙、蕾雅、奈叶香、安安、玛格、米莉亚 | 79%，同档等权，各约 11.29% |

本期不设三星。以上为未进入软保底时的基础概率；六星保底提升时其他档位概率相应减少。物品名后半是本次赛季的设计题名，不是原作台词或原作卡名。所有立绘均为当前赛季限定；卡池不混入 Bestdori 普通池。单抽 120 / 十连 1200 星星贴纸，70 抽开始软保底，90 抽硬保底，保底计数沿用现有跨赛季机制。

首次获得任意六星时同时获得 `frame_manosaba_character`（双生誓约头像框）和 `theme_manosaba`。获得第二位六星仅发该角色立绘；重复六星立绘补偿 60 盆栽。排名奖励沿用上一赛季的四档：2400 / 1200 / 600 / 300 星星贴纸、对应排名框，前三档附带主题。

## 生成来源

使用本机 `~/Projects/manosaba-sprite-synth` 的 `Prefab.synthesize()`，按 [`recipes.json`](recipes.json) 的表情、手势组合生成。没有使用旧的半身裁图，也没有修改生成器项目。

输出为透明 RGBA PNG，裁至有效 alpha 边界，等比缩小至内容高度 2024px，再补四周 12px 透明留白，最终高度 2048px。游戏角色原始美术版权归原作权利人所有。

[`manifest.json`](manifest.json) 记录生成器源文件、角色树、组合表、实际合成图层和输出文件的 SHA-256。源项目目前没有可用 Git HEAD，使用这些文件哈希追溯实际输入。

仓库根目录重建：

```sh
~/Projects/manosaba-sprite-synth/.venv/bin/python scripts/build_manosaba_season_art.py
.venv/bin/python scripts/draw_manosaba_frames.py
.venv/bin/python scripts/preview_manosaba_season.py
.venv/bin/python -m pytest tests/test_manosaba_season.py -q
```

头像框是独立绘制的 512px 原创框体图案，中央脸部安全窗透明。角色框采用黑白缎带与双生蔷薇；冠军为金色天平，前三为三枚菱印，前十为蔷薇封蜡，前五十为档案封印。

完整预览输出到 `output/manosaba-season/index.html`，包括双六星卡池、单抽、示例十连、赛季信息、装备档案，以及头像框 64 / 96px 缩略效果。预览使用实际配置和渲染器；玩家数值、十连结果只作示例，不操作真实玩家数据。此次准备只更新仓库配置和素材，不执行线上部署或赛季激活。
