# Monetary

**Kasumi Next** 的货币系统插件

## 简介

Monetary 是用于管理 Kasumi Next 货币系统的插件，提供了一整套简单易用的 API 用于增加、减少、获取、设置用户货币，以及进行转账操作。

## 快速开始

### 导入插件

在您的项目中导入货币系统插件：

```python
from ..monetary import monetary
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

## 注意事项

- 所有的 `user_id` 必须是唯一的字符串，推荐使用 `event.get_user_id()` 方法获取。
- `amount` 应为正整数。
- 确保在使用 `cost` 和 `transfer` 方法时，用户账户中有足够的余额。
- `description` 可以只是一个关键词。例如：签到的描述就是 `daily`。
