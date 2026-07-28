from pathlib import Path

from PIL import Image
from nonebot import logger

from .utils import resize_img
from .utils import svg_to_png
from .models import Band
from .models import Star
from .models import Attribute
from .downloader import AsyncDownloader

BAND_URL = "https://bestdori.com/res/icon/band_{}.svg"
CARD_URL = "https://bestdori.com/res/image/card-{}.png"
ATTRIBUTE_URL = "https://bestdori.com/res/icon/{}.svg"
ONE_STAR_CARD_URL = "https://bestdori.com/res/image/card-1-{}.png"
STAR_URL = "https://bestdori.com/res/icon/star.png"
STAR_TRAINED_URL = "https://bestdori.com/res/icon/star_trained.png"


def _valid_png(path: Path, size: tuple[int, int]) -> bool:
    """Check both image integrity and the processed size used by rendering."""

    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            return image.size == size
    except OSError:
        return False


def _valid_svg(path: Path) -> bool:
    """A compact check for the cached source SVGs used to rebuild icons."""

    try:
        return b"<svg" in path.read_bytes()[:1024].lower()
    except OSError:
        return False


async def initialize(src_path: Path, cache_path: Path):
    # 准备乐队图标资源(SVG)
    band_resources = [
        (BAND_URL.format(band.value), f"band_{band.value}.svg")
        for band in Band
    ]
    
    # 准备卡片资源(PNG)
    card_resources = [
        (CARD_URL.format(star.value), f"card-{star.value}.png")
        for star in Star if star != Star.one  # 跳过one=1的情况
    ]
    
    # 准备属性资源(SVG)
    attribute_resources = [
        (ATTRIBUTE_URL.format(attr.value), f"{attr.value}.svg")
        for attr in Attribute
    ]
    
    # 准备一星卡片资源(PNG)
    one_star_card_resources = [
        (ONE_STAR_CARD_URL.format(attr.value), f"card-1-{attr.value}.png")
        for attr in Attribute
    ]
    
    # 准备星级图标资源(PNG)
    star_resources = [
        (STAR_URL, "star.png"),
        (STAR_TRAINED_URL, "star_trained.png")
    ]

    src_path.mkdir(parents=True, exist_ok=True)
    cache_path.mkdir(parents=True, exist_ok=True)
    expected = {
        **{f"band_{band.value}.png": (170, 170) for band in Band},
        **{f"{attr.value}.png": (160, 160) for attr in Attribute},
        **{
            f"card-{star.value}.png": (640, 640)
            for star in Star
            if star != Star.one
        },
        **{f"card-1-{attr.value}.png": (640, 640) for attr in Attribute},
        "star.png": (107, 107),
        "star_trained.png": (107, 107),
    }
    missing = {
        name
        for name, size in expected.items()
        if not _valid_png(src_path / name, size)
    }
    logger.info(
        "BanGAvatar: 开机资源自检 "
        f"cached={len(expected) - len(missing)}/{len(expected)} "
        f"repair={len(missing)}"
    )
    if not missing:
        return

    svg_downloader = AsyncDownloader(cache_path, cache_path)
    png_downloader = AsyncDownloader(cache_path, src_path)
    svg_resources = [
        (url, name)
        for url, name in band_resources + attribute_resources
        if name.removesuffix(".svg") + ".png" in missing
        and not _valid_svg(cache_path / name)
    ]
    png_resources = [
        (url, name)
        for url, name in card_resources + one_star_card_resources + star_resources
        if name in missing
    ]
    if svg_resources:
        await svg_downloader.download_svgs(
            [url for url, _ in svg_resources],
            "",
            [name for _, name in svg_resources],
        )
    if png_resources:
        await png_downloader.download_cards(
            [url for url, _ in png_resources],
            "",
            [name for _, name in png_resources],
        )
    
    # SVG转PNG预处理
    logger.info("BanGAvatar: 开始SVG转PNG预处理")
    
    try:
        # 处理band图标 (170x170)
        for band in Band:
            svg_path = cache_path / f"band_{band.value}.svg"
            png_path = src_path / f"band_{band.value}.png"
            if f"band_{band.value}.png" in missing and _valid_svg(svg_path):
                svg_to_png(str(svg_path), str(png_path), 170, 170)
        
        # 处理attr图标 (160x160)
        for attr in Attribute:
            svg_path = cache_path / f"{attr.value}.svg"
            png_path = src_path / f"{attr.value}.png"
            if f"{attr.value}.png" in missing and _valid_svg(svg_path):
                svg_to_png(str(svg_path), str(png_path), 160, 160)
        
        logger.success("BanGAvatar: SVG转PNG预处理完成")
    except Exception as e:
        logger.error("BanGAvatar: SVG转PNG失败: {}", e)
    
    # PNG图片缩放预处理
    logger.info("BanGAvatar: 开始PNG缩放预处理")
    
    try:
        # 处理card_*.png (640x640)
        for star in Star:
            if star == Star.one:  # 跳过one=1的情况
                continue
            png_path = src_path / f"card-{star.value}.png"
            if (
                f"card-{star.value}.png" in missing
                and png_path.exists()
            ):
                img = Image.open(png_path)
                img = resize_img(img, 640)
                img.save(png_path)
        
        # 处理card-1-*.png (640x640)
        for attr in Attribute:
            png_path = src_path / f"card-1-{attr.value}.png"
            if f"card-1-{attr.value}.png" in missing and png_path.exists():
                img = Image.open(png_path)
                img = resize_img(img, 640)
                img.save(png_path)
        
        # 处理star.png和star_trained.png (107x107)
        for star_file in ["star.png", "star_trained.png"]:
            png_path = src_path / star_file
            if star_file in missing and png_path.exists():
                img = Image.open(png_path)
                img = resize_img(img, 107)
                img.save(png_path)
        
        logger.success("BanGAvatar: PNG缩放预处理完成")
    except Exception as e:
        logger.error("BanGAvatar: PNG缩放失败: {}", e)
    
    logger.success("BanGAvatar: 资源初始化完成")
