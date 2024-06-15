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
