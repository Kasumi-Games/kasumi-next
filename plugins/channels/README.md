# Channels

**Kasumi Next** 的成员管理插件

## 简介

Channels 是用于管理 Kasumi Next 成员系统的插件，提供了一套简单易用的方法用于获取频道或群聊的用户成员。通过使用数据库记录的方式，Channels 可以作为 QQ 群聊中 `guild.member.list` 的替代方案，在频道场景下，您应该使用 `bot.guild_member_list` 直接获取成员列表。

## 快速开始

### 导入插件

在您的插件中导入成员管理插件：

```python
from .. import channels
```

### 功能说明

以下是该插件的核心功能及其用法：

#### 获取指定 Channel 成员

获取指定 Channel 的所有已知成员：

```python
channels.get_channel_members(channel_id: str) -> List[Member]
```

- `channel_id` (str)：Channel 的唯一标识，可通过 `event.channel.id` 获取

返回值是该 Channel 的所有成员列表。

注意：`Channel` 在此处为 Satori 中的概念，可以是 QQ 群聊，也可以是 QQ 频道。

#### 获取指定成员所在的 Channels

获取指定成员所在的所有已知 Channels：

```python
channels.get_member_channels(member_id: str) -> List[Channel]
```

- `member_id` (str)：成员的唯一标识，可通过 `event.get_user_id()` 获取

返回值是该成员所在的所有 Channels 列表。

注意：`Channel` 在此处为 Satori 中的概念，可以是 QQ 群聊，也可以是 QQ 频道。

#### Member 对象

`Member` 对象是 Channels 插件中的核心对象，包含了成员的基本信息：

- `id` (str)：成员的唯一标识
- `avatar_url` (str)：成员的头像 URL，可能为 `None`

#### Channel 对象

`Channel` 对象是 Channels 插件中的核心对象，包含了 Channel 的基本信息：

- `id` (str)：Channel 的唯一标识
