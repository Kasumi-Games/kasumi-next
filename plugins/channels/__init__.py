from nonebot.adapters.satori.event import (
    GuildRemovedEvent,
    MessageCreatedEvent,
    GuildMemberAddedEvent,
    GuildMemberRemovedEvent,
)
from nonebot import on_message, on_notice, require

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store

from utils import is_qq_bot

from .data_source import ChannelMemberManager


member_file = store.get_data_file("member", "member.db")
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
async def handle_notice(event: GuildMemberRemovedEvent):
    if event.platform not in ["qq", "qqguild"]:
        return None
    manager.remove_member_from_channel(event.channel.id, event.get_user_id())


@on_notice(priority=1, block=False).handle()
async def handle_notice(event: GuildRemovedEvent):
    if event.platform not in ["qq", "qqguild"]:
        return None
    manager.remove_channel(event.channel.id)


get_channel_members = manager.get_channel_members
get_mamber_channels = manager.get_member_channels


__all__ = [
    "get_channel_members",
    "get_member_channels",
]
