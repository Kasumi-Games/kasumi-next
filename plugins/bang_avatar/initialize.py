from nonebot import logger
from pathlib import Path
from PIL import Image
from .utils import resize_img
from .models import Band, Attribute, Star
from .downloader import AsyncDownloader
from .utils import svg_to_png


BAND_URL = "https://bestdori.com/res/icon/band_{}.svg"
CARD_URL = "https://bestdori.com/res/image/card-{}.png"
ATTRIBUTE_URL = "https://bestdori.com/res/icon/{}.svg"
ONE_STAR_CARD_URL = "https://bestdori.com/res/image/card-1-{}.png"
STAR_URL = "https://bestdori.com/res/icon/star.png"
STAR_TRAINED_URL = "https://bestdori.com/res/icon/star_trained.png"


async def initialize(src_path: Path, cache_path: Path):
    logger.info("BanGAvatar: 正在检查资源")
    
    # 检查所有处理后的PNG资源是否已存在
    all_resources_exist = True
    
    # 检查band PNG资源 (170x170)
    for band in Band:
        if not (src_path / f"band_{band.value}.png").exists():
            all_resources_exist = False
            break
    
    # 检查attr PNG资源 (160x160)
    for attr in Attribute:
        if not (src_path / f"{attr.value}.png").exists():
            all_resources_exist = False
            break
    
    # 检查card PNG资源 (640x640)
    for star in Star:
        if star == Star.one:  # 跳过one=1的情况
            continue
        if not (src_path / f"card-{star.value}.png").exists():
            all_resources_exist = False
            break
    
    # 检查card-1 PNG资源 (640x640)
    for attr in Attribute:
        if not (src_path / f"card-1-{attr.value}.png").exists():
            all_resources_exist = False
            break
    
    # 检查star PNG资源
    if not (src_path / "star.png").exists() or not (src_path / "star_trained.png").exists():
        all_resources_exist = False
    
    if all_resources_exist:
        logger.success("BanGAvatar: 所有资源已存在，跳过初始化")
        return
    
    logger.info("BanGAvatar: 开始初始化资源")
    
    # 初始化两个下载器
    svg_downloader = AsyncDownloader(cache_path, cache_path)  # SVG下载到cache目录
    png_downloader = AsyncDownloader(cache_path, src_path)    # PNG下载到src目录
    
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

    # 使用svg_downloader下载SVG资源到cache目录
    svg_urls = [url for url, _ in band_resources + attribute_resources]
    svg_names = [name for _, name in band_resources + attribute_resources]
    await svg_downloader.download_svgs(svg_urls, "", svg_names)
    
    # 使用png_downloader下载PNG资源到src目录
    png_urls = [url for url, _ in card_resources + one_star_card_resources + star_resources]
    png_names = [name for _, name in card_resources + one_star_card_resources + star_resources]
    await png_downloader.download_cards(png_urls, "", png_names)
    
    # SVG转PNG预处理
    logger.info("BanGAvatar: 开始SVG转PNG预处理")
    
    try:
        # 处理band图标 (170x170)
        for band in Band:
            svg_path = cache_path / f"band_{band.value}.svg"
            png_path = src_path / f"band_{band.value}.png"
            if svg_path.exists():
                svg_to_png(str(svg_path), str(png_path), 170, 170)
        
        # 处理attr图标 (160x160)
        for attr in Attribute:
            svg_path = cache_path / f"{attr.value}.svg"
            png_path = src_path / f"{attr.value}.png"
            if svg_path.exists():
                svg_to_png(str(svg_path), str(png_path), 160, 160)
        
        logger.success("BanGAvatar: SVG转PNG预处理完成")
    except Exception as e:
        logger.error(f"BanGAvatar: SVG转PNG失败: {str(e)}")
    
    # PNG图片缩放预处理
    logger.info("BanGAvatar: 开始PNG缩放预处理")
    
    try:
        # 处理card_*.png (640x640)
        for star in Star:
            if star == Star.one:  # 跳过one=1的情况
                continue
            png_path = src_path / f"card-{star.value}.png"
            if png_path.exists():
                img = Image.open(png_path)
                img = resize_img(img, 640)
                img.save(png_path)
        
        # 处理card-1-*.png (640x640)
        for attr in Attribute:
            png_path = src_path / f"card-1-{attr.value}.png"
            if png_path.exists():
                img = Image.open(png_path)
                img = resize_img(img, 640)
                img.save(png_path)
        
        # 处理star.png和star_trained.png (107x107)
        for star_file in ["star.png", "star_trained.png"]:
            png_path = src_path / star_file
            if png_path.exists():
                img = Image.open(png_path)
                img = resize_img(img, 107)
                img.save(png_path)
        
        logger.success("BanGAvatar: PNG缩放预处理完成")
    except Exception as e:
        logger.error(f"BanGAvatar: PNG缩放失败: {str(e)}")
    
    logger.success("BanGAvatar: 资源初始化完成")