from pathlib import Path
from PIL import Image
from io import BytesIO
from nonebot.adapters.satori import MessageSegment
from nonebot import get_plugin_config
from .utils import get_group_member_head, paste_img, resize_img, circle_corner
from .models import WifeData
from .config import Config


APP_ID=get_plugin_config(Config).qq_bot_app_id

async def render(wife_data: WifeData,
            src_path: Path,
            avatar_url:str = None ) -> MessageSegment:
    
    """
    随机得到一张BanGDream风格的头像

    Returns:
        MessageSegment: 渲染后的图片
    """
    band = wife_data.band
    star = wife_data.star
    attr = wife_data.attribute
    user_id = wife_data.lp_id
    app_id = APP_ID
    # user_id = event.get_user_id()


    avatar = await get_group_member_head(app_id,user_id,avatar_url = avatar_url)

    #实际渲染，获取Image对象
    return _render(avatar,star,band,attr,src_path)


def _render(base:Image,
               stars: int,
               band: int,
               attr: str,
               src_path: Path) -> MessageSegment:
    
    """
    :param base: 头像
    :param stars: 星级
    :param band: 所属乐队
    :param attr: 属性
    :param src_path: 素材路径
    :returns MessageSegment: 渲染后的图片
    """
    base = circle_corner(base,48)

    if base.size != (640,640):
        base = resize_img(base,640)

    card_pic_path = f"card-1-{attr}.png" if stars == 1 else f"card-{stars}.png"
    card_pic = Image.open(src_path / card_pic_path)
    base = paste_img(base,card_pic,(0,0))

    band_pic = Image.open(src_path / f"band_{band}.png")
    base = paste_img(base,band_pic,(7,7))

    attr_pic = Image.open(src_path / f"{attr}.png")
    base = paste_img(base,attr_pic,(473,11))

    star_pic = (Image.open(src_path / "star.png") 
                if stars <= 2 
                else Image.open(src_path / "star_trained.png"))
    for i in range(stars):
        y = 513-i*80
        base = paste_img(base,star_pic,(10,y))

    #返回MessageSegment对象
    buffer = BytesIO()
    base.save(buffer, format="PNG")
    return MessageSegment.image(raw=buffer, mime="image/png")
    