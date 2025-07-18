# Monetary

**Kasumi Next** 的货币系统插件

## 简介

Monetary 是用于管理 Kasumi Next 货币系统的插件，提供了一整套简单易用的 API 用于增加、减少、获取、设置用户货币，以及进行转账操作。

## 快速开始

### 导入插件

在您的项目中导入货币系统插件：

```python
from .. import monetary
```

### 功能说明

以下是该插件的核心功能及其用法：

#### 增加货币

向指定用户账户增加货币：

```python
monetary.add(user_id: str, amount: int, description: str)
```

- `user_id` (str)：用户的唯一标识
- `amount` (int)：要增加的货币数量
- `description` (str)：增加货币的原因描述

#### 减少货币

从指定用户账户减少货币：

```python
monetary.cost(user_id: str, amount: int, description: str)
```

- `user_id` (str)：用户的唯一标识
- `amount` (int)：要减少的货币数量
- `description` (str)：减少货币的原因描述

#### 获取货币

获取指定用户的货币余额：

```python
monetary.get(user_id: str) -> int
```

- `user_id` (str)：用户的唯一标识

返回值是该用户的当前货币余额。

#### 设置货币

直接设置用户的货币余额：

```python
monetary.set(user_id: str, amount: int, description: str)
```

- `user_id` (str)：用户的唯一标识
- `amount` (int)：要设置的货币数量
- `description` (str)：设置货币的原因描述

#### 转账

在两个用户之间进行货币转账：

```python
monetary.transfer(from_user_id: str, to_user_id: str, amount: int, description: str)
```

- `from_user_id` (str)：转出方的用户唯一标识
- `to_user_id` (str)：接收方的用户唯一标识
- `amount` (int)：转账的货币数量
- `description` (str)：转账的原因描述

### 每日签到

检查并记录用户每日签到：

```python
monetary.daily(user_id: str) -> bool
```

- `user_id` (str)：用户的唯一标识

返回值是布尔值，`True` 表示今日首次签到成功，`False` 表示今日已签到。

## 用户等级系统

除了货币系统外，本插件还提供了用户等级管理功能。每个用户都有一个等级，初始等级为 1。

### 获取用户等级

获取指定用户的当前等级：

```python
monetary.get_level(user_id: str) -> int
```

- `user_id` (str)：用户的唯一标识

返回值是该用户的当前等级。

### 设置用户等级

直接设置用户的等级：

```python
monetary.set_level(user_id: str, level: int)
```

- `user_id` (str)：用户的唯一标识
- `level` (int)：要设置的等级值（必须 >= 1）

**注意**：如果设置的等级小于 1，将抛出 `ValueError` 异常。

### 增加用户等级

增加用户的等级：

```python
monetary.increase_level(user_id: str, levels: int = 1)
```

- `user_id` (str)：用户的唯一标识
- `levels` (int)：要增加的等级数量（默认为 1）

**注意**：如果 `levels` 为负数，将抛出 `ValueError` 异常。

### 减少用户等级

减少用户的等级（最低为 1 级）：

```python
monetary.decrease_level(user_id: str, levels: int = 1)
```

- `user_id` (str)：用户的唯一标识
- `levels` (int)：要减少的等级数量（默认为 1）

**注意**：
- 如果 `levels` 为负数，将抛出 `ValueError` 异常
- 用户等级永远不会低于 1，即使减少的数量会导致等级为负数

### 获取用户统计信息

获取用户的综合统计信息，包括余额、等级、排名等：

```python
from ..monetary import get_user_stats, UserStats

stats: UserStats = monetary.get_user_stats(user_id)
```

- `user_id` (str)：用户的唯一标识

返回值是 `UserStats` 数据类，包含：
- `user_id`：用户 ID
- `balance`：当前余额
- `level`：当前等级
- `rank`：按等级（优先）和余额（次要）的综合排名
- `distance_to_next_rank`：距离下一名的余额差距（仅当等级相同时有效，否则为 0）
- `distance_to_next_level`：距离下一等级的等级差距（如果没有更高等级则为 0）
- `last_daily_time`：上次签到时间戳

## 排名系统

本插件的排名系统采用**等级优先、余额次要**的综合排名方式：

1. **主要排名依据**：用户等级（等级越高排名越靠前）
2. **次要排名依据**：当等级相同时，按余额排名（余额越多排名越靠前）

### 获取排行榜

获取排行榜前几名用户：

```python
from ..monetary import get_top_users, TopUser

top_users: list[TopUser] = monetary.get_top_users(limit=10)
```

- `limit` (int)：返回的用户数量（默认为 10）

返回值是 `TopUser` 数据类列表，每个 `TopUser` 包含：
- `user_id`：用户 ID
- `level`：用户等级
- `balance`：用户余额

### 获取用户排名

获取指定用户的排名信息：

```python
from ..monetary import get_user_rank, UserRank

rank_info: UserRank = monetary.get_user_rank(user_id)
```

- `user_id` (str)：用户的唯一标识

返回值是 `UserRank` 数据类，包含：
- `rank`：用户的当前排名
- `distance_to_next_rank`：距离下一名的余额差距（仅当等级相同时有效，否则为 0）
- `distance_to_next_level`：距离下一等级的等级差距（如果没有更高等级则为 0）

### 等级系统使用示例

```python
from .. import monetary
from ..monetary import TopUser, UserRank, UserStats

user_id = "player123"

# 查看当前等级
current_level = monetary.get_level(user_id)
print(f"当前等级: {current_level}")

# 升级用户
monetary.increase_level(user_id, 1)

# 获取完整统计信息
stats: UserStats = monetary.get_user_stats(user_id)
print(f"用户 {user_id} - 等级: {stats.level}, 余额: {stats.balance}, 排名: {stats.rank}")
print(f"距离下一名: {stats.distance_to_next_rank} 余额")
print(f"距离下一等级: {stats.distance_to_next_level} 等级")

# 获取排名信息
rank_info: UserRank = monetary.get_user_rank(user_id)
print(f"排名: {rank_info.rank}, 距离下一名: {rank_info.distance_to_next_rank}, 距离下一等级: {rank_info.distance_to_next_level}")

# 管理员设置等级
monetary.set_level(user_id, 10)

# 降级（但不会低于 1 级）
monetary.decrease_level(user_id, 5)

# 查看排行榜
top_users: list[TopUser] = monetary.get_top_users(5)
for i, user in enumerate(top_users, 1):
    print(f"第{i}名: 用户 {user.user_id} - 等级 {user.level}, 余额 {user.balance}")
```

## 注意事项

- 所有的 `user_id` 必须是唯一的字符串，推荐使用 `event.get_user_id()` 方法获取。
- `amount` 应为正整数。
- 确保在使用 `cost` 和 `transfer` 方法时，用户账户中有足够的余额。
- `description` 可以只是一个关键词。例如：签到的描述就是 `daily`。
- 等级系统是独立的，不会影响货币交易记录。
- 新用户会自动创建，初始等级为 1，初始余额为 0。
