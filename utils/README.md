# Utils

**Kasumi Next** 工具函数库

## 简介

Utils 是 Kasumi Next 的工具函数库插件，提供了一系列常用的工具函数，帮助简化开发过程。

## 快速开始

### 导入函数

在您的项目中引入工具函数：

```python
from utils import some_function
```

### 功能说明

#### has_no_argument

用于 `on_command` 规则，检查用户是否未输入参数。

```python
from nonebot import on_command
from utils import has_no_argument

matcher = on_command("command", rule=has_no_argument)
```

此函数适合在需要使用 `on_command` 时阻止用户输入参数。例如：期望处理 `cck`，而不希望处理 `cck真好玩吧`。

#### is_qq_bot

用于 `on` 规则，检查消息是否来自 QQ 官方机器人。

```python
from nonebot import on
from utils import is_qq_bot

matcher = on(rule=is_qq_bot)
```

此函数适合在需要特殊处理 QQ 官方机器人消息时使用。

#### encode_to_silk

用于将音频文件编码为 Silk 格式。

```python
from utils import encode_to_silk

with open("example.wav", "rb") as f:
    audio = f.read()

silk_audio: bytes = encode_to_silk(audio, "wav")
```

此函数适合在需要将音频文件编码为 Silk 格式时使用。

#### PassiveGenerator

用于生成被动回复消息。

```python
from utils import PassiveGenerator
from nonebot.adapter.satori import MessageEvent

assert event, MessageEvent
passive_generator = PassiveGenerator(event)

matcher.send("something" + passive_generator.element)
```

此类适合在需要生成被动回复消息时使用。
如果还是不会用，推荐查看 `plugins/cck/__init__.py` 中的使用方法。
