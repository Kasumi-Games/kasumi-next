# coding = utf-8
import cairosvg
from PIL import Image, ImageDraw, ImageFilter
from io import BytesIO
from aiohttp import ClientSession
from nonebot.adapters.satori import MessageSegment


def paste_img(imgbase: Image, imgadd: Image, position: tuple[int, int]) -> Image:
    """将图片粘贴到指定位置并返回结果。

    Args:
        imgbase: 被粘贴的底图
        imgadd: 要粘贴的图片
        position: 粘贴位置坐标(x, y)

    Returns:
        粘贴后的图片对象
    """
    a = imgadd.split()[3]
    imgbase.paste(imgadd, position, a)
    return imgbase


def resize_img(img: Image, target_size: int) -> Image:
    """缩放图片到指定尺寸。

    Args:
        img: 原始图片
        target_size: 目标尺寸(宽高相同)

    Returns:
        缩放后的图片
    """
    img = img.resize((target_size, target_size), Image.BICUBIC)
    img = img.filter(ImageFilter.SHARPEN)
    return img


def circle_corner(img: Image, radii: int) -> Image:
    """为图片添加圆角效果。

    Args:
        img: 输入图片
        radii: 圆角半径(像素)

    Returns:
        添加圆角后的图片
    """
    img = img.convert("RGBA")
    width, height = img.size
    radii = min(radii, min(width, height) // 2)

    circle = Image.new('L', (radii * 2, radii * 2), 0)
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, radii * 2, radii * 2), fill=255)

    alpha = Image.new('L', img.size, 255)
    positions = [
        (0, 0),  # 左上
        (width - radii, 0),  # 右上
        (width - radii, height - radii),  # 右下
        (0, height - radii)  # 左下
    ]

    for i, (x, y) in enumerate(positions):
        quadrant = circle.crop((
            0 if i in [0, 3] else radii,
            0 if i in [0, 1] else radii,
            radii if i in [0, 3] else radii * 2,
            radii if i in [0, 1] else radii * 2
        ))
        alpha.paste(quadrant, (x, y))

    img.putalpha(alpha)
    return img


async def get_group_member_head(app_id: str, user_id: str, avatar_url: str = None, mode: int = 5) -> Image:
    """获取用户头像图片。

    Args:
        app_id: 机器人应用ID
        user_id: 用户ID
        avatar_url: 自定义头像URL(可选)
        mode: 头像分辨率模式(默认5=640x640)

    Returns:
        头像图片对象
    """
    if not avatar_url:
        avatar_url = f"https://q.qlogo.cn/qqapp/{app_id}/{user_id}/{mode}"

    async with ClientSession() as cs:
        async with await cs.get(avatar_url) as response:
            response.raise_for_status()
            img_bytes = await response.read()
            img = Image.open(BytesIO(img_bytes))
            return img


def image_to_message(image: Image.Image) -> MessageSegment:
    """将PIL图片转换为消息段对象。

    Args:
        image: PIL图片对象

    Returns:
        图片消息段对象
    """
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return MessageSegment.image(raw=buffer, mime="image/png")


def svg_to_png(svg_path: str, output_path: str, width: int, height: int) -> None:
    """将SVG文件转换为PNG并保存。

    Args:
        svg_path: SVG文件路径
        output_path: 输出PNG路径
        width: 输出宽度
        height: 输出高度
    """
    png_data = cairosvg.svg2png(
        url=svg_path,
        output_width=width,
        output_height=height,
        dpi=300
    )
    with open(output_path, 'wb') as f:
        f.write(png_data)