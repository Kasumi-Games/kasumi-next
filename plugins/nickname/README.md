# Nickname

**Kasumi Next** 的昵称系统插件

## 简介

Nickname 是用于管理 Kasumi Next 昵称系统的插件，提供了获取用户昵称的方法。设置和修改用户昵称的部分已经在插件内实现，直接与用户交互，不提供方法供其他插件调用。

## 快速开始

### 导入插件

在您的项目中导入昵称系统插件：

```python
from .. import nickname
```

### 功能说明

以下是该插件的核心功能及其用法：

#### 获取昵称

获取指定用户的昵称：

```python
nickname.get(user_id: str) -> Optional[str]
```

- `user_id` (str)：用户的唯一标识，推荐使用 `event.get_user_id()` 获取
- 返回值是该用户的当前昵称，如果用户没有设置昵称，返回 `None`
