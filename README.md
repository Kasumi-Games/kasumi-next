# Kasumi Next
Kasumi Bot 的新一代版本

## 介绍
**Kasumi Next** 是一个基于 [NoneBot2](https://github.com/nonebot/nonebot2) 的跨平台机器人项目，采用 [Satori](https://satori.js.org/zh-CN/) 协议与客户端通信，旨在提供一个「キラキラドキドキ」的 BanGDream! 小游戏机器人。

## 功能
目前正在开发中，敬请期待。

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
