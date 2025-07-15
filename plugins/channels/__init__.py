from nonebot.adapters.satori.event import (
    GuildRemovedEvent,
    MessageCreatedEvent,
    GuildMemberAddedEvent,
    GuildMemberRemovedEvent,
)
from nonebot import on_message, on_notice, require

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store  # noqa: E402

from utils import is_qq_bot  # noqa: E402

from .data_source import ChannelMemberManager  # noqa: E402


member_file = store.get_data_file("channels", "channels.db")
database_url = f"sqlite:///{member_file.absolute()}"


manager = ChannelMemberManager(database_url)


@on_message(rule=is_qq_bot, priority=1, block=False).handle()
async def handle_message(event: MessageCreatedEvent):
    manager.add_member_to_channel(
        event.channel.id, event.get_user_id(), event.user.avatar
    )


@on_notice(priority=1, block=False).handle()
async def handle_notice(event: GuildMemberAddedEvent):
    if event.platform not in ["qq", "qqguild"]:
        return None
    manager.add_member_to_channel(
        event.channel.id, event.get_user_id(), event.user.avatar
    )


@on_notice(priority=1, block=False).handle()
async def handle_notice_remove(event: GuildMemberRemovedEvent):
    if event.platform not in ["qq", "qqguild"]:
        return None
    manager.remove_member_from_channel(event.channel.id, event.get_user_id())


@on_notice(priority=1, block=False).handle()
async def handle_notice_remove_channel(event: GuildRemovedEvent):
    if event.platform not in ["qq", "qqguild"]:
        return None
    manager.remove_channel(event.channel.id)


get_channel_members = manager.get_channel_members
get_mamber_channels = manager.get_member_channels


__all__ = [
    "get_channel_members",
    "get_member_channels",
]
