import random
from nonebot import on_command, get_driver
import nonebot_plugin_localstore as localstore
from nonebot import get_plugin_config
from nonebot.adapters.satori import MessageEvent
from utils import has_no_argument
from ..monetary import monetary
from .. import channels
from ..nickname.data_source import get as get_user_nickname
from .config import Config
from .render import render
from .models import WifeData
from .initialize import initialize


plugin_config = get_plugin_config(Config)
WIFE_COST = plugin_config.wife_cost

src_path = localstore.get_data_dir("bang_avatar") / "src"
cache_path = localstore.get_cache_dir("bang_avatar")

if plugin_config.enable_bang_avatar:
    @get_driver().on_startup
    async def init_src():
        await initialize(src_path, cache_path)

def check_and_use_money(user_id: str) -> bool:
    if monetary.get(user_id) >= WIFE_COST:
        monetary.cost(user_id, WIFE_COST, "qqy")
        return True
    else:
        return False

bang_avatar = on_command(
    "娶群友",
    aliases={"qqy","ccb"},
    priority=10,
    block=True,
    rule=has_no_argument
)

@bang_avatar.handle()
async def handle_bang_avatar(event: MessageEvent):
    user_id = event.get_user_id()
    channel_id = event.channel.id
    platform = event.login.platform

    all_users = [
        member for member in channels.get_channel_members(channel_id)
        if member.id != user_id 
    ]

    if all_users:
        # 还有候选成员
        wife = random.choice(all_users)
        if check_and_use_money(user_id):
            await bang_avatar.finish(
                # 如果是qqguild就用获取到的头像，否则设为None用api获取
                await render(
                    WifeData(user_id, wife.id).generate_wife_data(), 
                    src_path, 
                    wife.avatar_url if platform == "qqguild" else None
                )
                + f"娶到 {get_user_nickname(wife.id) or "Ta"} 了哦~"
                + f"你手里还有 {monetary.get(user_id)} 个碎片"
            )
        else:
            await bang_avatar.finish(
                f"余额不足，你手里只有 {monetary.get(user_id)} 个碎片哦，先赚些星之碎片吧~"
            )
    else:
        await bang_avatar.finish("群里暂时没有人能被你娶到哦~")