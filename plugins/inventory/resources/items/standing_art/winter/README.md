# 冬日合奏立绘来源

12 张素材均为 Bestdori 提供的原作卡面透明 CG (`trim_normal.png`)。
原始角色图包含半身、坐姿或局部人物构图；这些不是重新绘制的全身 Live2D。
保留完整原始透明画布和全部人物像素，只转换 RGBA 并添加四边 16px 透明安全边，
不拉伸、不抠场景、不使用 AI 人物图。

`recipes.json` 记录 Bestdori 角色 ID、卡号、资源版本、JP 来源 URL、原始字节哈希、
项目 slug 和本项目星级；`manifest.json` 记录输出文件、尺寸及 SHA-256。
两份清单同时保存 `card_title` 原卡名与 `item_name` 完整展示名。优先采用简体中文
原卡名，没有简体中文时回退日文；物品目录与卡池条目使用同一名称，不统一改名为「冬日」。
卡号仅用于溯源，六／五／四星是本项目卡池档位，不代表原作星级。
角色原始美术权利归 BanG Dream! 及相应权利人；来源公开不表示获得额外商业许可。

重建：在仓库根目录运行 `.venv/bin/python scripts/build_winter_ensemble_assets.py`。
优先使用 `.data/gacha/standing/<卡号>_normal.png`，缺失时下载记录的来源 URL，
原图哈希不符会停止。脚本同时以代码生成五款头像框，Ø416 头像窗保留透明。
头像框绘制实现位于 `scripts/draw_winter_frames.py`，借鉴魔女审判的框沿层级与
装饰体量，采用冬日原创雪晶、松枝、围巾结和徽章；中央脸部安全区保持透明。
输出目录属于仓库资产，运行时不依赖 Bestdori 网络或本地缓存。

本期双六星：香澄 #556、灯 #2123；五星：彩 #387、心 #1397、真白 #1682、六花 #1120；
四星：兰 #563、莉莎 #1691、有咲 #1111、沙绫 #2360、爱音 #2160、友希那 #1358。
未确认到合适的阿拉蕾冬装，本期依规划同档替换为有冬装的友希那。

界面字体复用仓库的 Resource Han Rounded CN Medium/Bold，来源和 OFL 许可见
`plugins/render/kits/mewtype/resources/fonts/`；不另行复制字体文件。
