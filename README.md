# Kasumi Next
Kasumi Bot 的新一代版本

## 介绍
**Kasumi Next** 是一个基于 [NoneBot2](https://github.com/nonebot/nonebot2) 的跨平台机器人项目，采用 [Satori](https://satori.js.org/zh-CN/) 协议与客户端通信，旨在提供一个「キラキラドキドキ」的 BanGDream! 小游戏机器人。

## 功能
Kasumi Next 提供了以下功能：

### 帮助(help)
显示帮助信息。

#### 使用方法
- `help`：显示帮助信息。
- `help 插件名`：显示特定插件的用法。

### 信息(info)
显示 Kasumi 信息。

#### 使用方法
- `关于|info`：显示 Kasumi 信息。

### 星之碎片(monetary)
Kasumi 的货币系统。

#### 使用方法
- `余额|balance`：查看余额。
- `转账|transfer <@用户> <数量>`：转账。
- `签到|daily`：每日签到。

### 猜猜看(cck)
猜猜看小游戏。

#### 使用方法
- `猜猜看|cck`：开始猜猜看。
- `bzd`：猜不出来的时候就发这个吧。

### 猜谱面(cpm)
猜谱面小游戏。

#### 使用方法
- `猜谱面|cpm`：开始猜谱面。
- `猜谱面|cpm <难度>`：开始猜谱面，难度可选为 easy, normal, hard, expert, special，支持缩写为 ez, nm, hd, ex, sp。
- `<歌曲名称|ID>`：猜指定歌曲的谱面。
- `提示`：在猜谱面时获取提示。
- `bzd`：猜不出来的时候就发这个吧。

### tts(vits)
文本转BanG Dream! & 少女歌剧角色语音。

#### 使用方法
- `tts <角色> <文本>`：将文本转换为角色语音。角色和文本都可以省略，省略时会出现更多提示。

### 说明
- **`|`** 表示可以使用的多个命令的选项。 
- **`<@用户>`** 表示需要指定用户。
- **`<数量>`** 表示需要指定数量。
- **`<难度>`** 表示需要选择游戏难度。
- **`<歌曲名称|ID>`** 表示可以通过歌曲名称或ID进行猜谱面。

## 配置项
| 配置项 | 说明 | 默认值 |
| --- | --- | --- |
| `SATORI_CLIENTS` | Satori 客户端配置 | 见 `.env` 文件 |
| `LOCALSTORE_CACHE_DIR` | 本地缓存目录 | `.\.cache` |
| `LOCALSTORE_CONFIG_DIR` | 本地配置目录 | `.\.config` |
| `LOCALSTORE_DATA_DIR` | 本地数据目录 | `.\.data` |
| `WHITELIST` | 白名单, 类型为 `List[str]` | `[]` |
| `BESTDORI_PROXY` | bestdori-api 代理地址, 类型为 `str` | `null` |  
| `ENABLE_GUESS_CHART` | 是否启用 猜谱面 功能, 关闭可缩短初始化时间 | `true` |
| `ENABLE_CCK` | 是否启用 猜猜看 功能, 关闭可缩短初始化时间 | `true` |
| `BERT_VITS_API_URL` | BertVits API 地址 | `http://127.0.0.1:4371` |

> 默认值包含了 `.env` 文件中的默认配置项

## 开发指南

### 配置

1. **克隆项目：**
   将项目代码克隆到本地：
   ```shell
   git clone https://github.com/Kasumi-Games/kasumi-next.git
   cd kasumi-next
   ```

2. **创建配置文件：**
   项目的基础配置已在 `.env` 文件中给出。开发者需要新建一个 `.env.dev` 文件，并参考 `.env` 文件中的 `SATORI_CLIENTS` 配置项，将自己的 Satori 服务端信息填写到 `.env.dev` 中。
   ```shell
   cp .env .env.dev
   ```
   注意：`.env.dev` 文件已被列入 `.gitignore`，不会提交到版本控制系统中。

3. **配置密钥：**
   如果插件需要配置密钥，请在 `.env` 文件中添加相应的配置项，例如：
   ```env
   API_KEY=""
   ```
   然后，在 `.env.dev` 文件中添加实际的密钥值。

### 环境设置

推荐使用 [PDM](https://pdm-project.org/) 作为包管理器。请参考 [PDM 官方文档](https://pdm-project.org/en/latest/#installation) 安装。

### 运行项目

在项目根目录下，执行以下操作：

1. **安装依赖：**
   ```shell
   pdm install
   ```

2. **启动 Bot：**
   ```shell
   pdm run bot.py
   ```

### 插件开发

插件开发请参考 [NoneBot2 官方文档](https://nonebot.dev/docs/next/tutorial/matcher)。

完成插件开发后，将插件放入 `plugins` 目录中，Bot 会自动加载该插件。

### 插件测试

推荐在插件测试时，将 `.env.dev` 文件中的 `COMMAND_START` 配置为 `["!"]`，以避免与线上环境冲突。
