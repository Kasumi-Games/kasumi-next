import cv2
import random
from pathlib import Path
from nonebot.log import logger
import nonebot_plugin_localstore as store
from PIL import Image, ImageDraw, ImageFont
from typing import Tuple, Optional, Callable, TYPE_CHECKING, Dict, Any

if TYPE_CHECKING:
    from .models import Hand


class BlackjackRenderer:
    """可配置资源路径的黑杰克卡牌渲染器"""

    # 全局配置
    SUITS = ["cool", "happy", "powerful", "pure"]

    # 卡牌配置
    CARD_CONFIGS = {
        "2": ("1", 2, 0, 1),  # 2 -> 1框 2黄 1星
        "3": ("1", 3, 0, 1),  # 3 -> 1框 3黄 1星
        "4": ("2", 4, 0, 2),  # 4 -> 2框 4黄 2星
        "5": ("2", 5, 0, 2),  # 5 -> 2框 5黄 2星
        "6": ("3", 0, 3, 3),  # 6 -> 3框 3彩 3星
        "7": ("3", 1, 3, 3),  # 7 -> 3框 3彩1黄 3星
        "8": ("4", 0, 4, 4),  # 8 -> 4框 4彩 4星
        "9": ("4", 1, 4, 4),  # 9 -> 4框 4彩1黄 4星
        "10": ("4", 0, 5, 5),  # 10 -> 4框 5彩 5星
        "J": ("4", 0, 5, 5),  # J -> 4框 5彩 5星
        "Q": ("4", 0, 5, 5),  # Q -> 4框 5彩 5星
        "K": ("4", 0, 5, 5),  # K -> 4框 5彩 5星
    }

    # A牌的两种配置 (点数值: (frame_type, star_num, star_trained_num, rarity))
    ACE_CONFIGS = {
        1: ("5", 1, 0, 5),  # A=1 -> 5框 1黄 5星
        11: ("5", 1, 5, 5),  # A=11 -> 5框 5彩1黄 5星
    }

    def __init__(
        self,
        resource_dir: str = "plugins/blackjack/recourses",
        card_data: Optional[Dict[str, Any]] = None,
        character_data: Optional[Dict[str, Any]] = None,
        face_positions: Optional[Dict[str, Any]] = None,
        cascade: Optional[cv2.CascadeClassifier] = None,
    ):
        """
        初始化 BlackjackRenderer，支持自定义资源路径

        参数说明:
            resource_dir: 资源文件所在目录
            card_data: 卡牌数据
            character_data: 角色数据
            face_positions: 人脸位置数据
            cascade: 级联分类器
        """
        self.resource_dir = Path(resource_dir)
        self.card_data = card_data
        self.character_data = character_data
        self.face_positions = face_positions
        self.cascade = cascade

        # Initialize resource containers
        self.attrs: Dict[str, Image.Image] = {}
        self.bands: Dict[str, Image.Image] = {}
        self.frames: Dict[str, Any] = {}
        self.star: Optional[Image.Image] = None
        self.star_trained: Optional[Image.Image] = None
        self.image_face_cache: Dict[str, Image.Image] = {}

        # Load all resources
        self._load_resources()

    def _load_resources(self):
        """加载所有图片资源到内存"""
        logger.info("正在加载黑杰克资源...")

        self.get_font = lambda size: ImageFont.truetype(
            str(self.resource_dir / "old.ttf"), size
        )

        # Load attribute images
        self.attrs = {
            "cool": Image.open(self.resource_dir / "cool.png").convert("RGBA"),
            "happy": Image.open(self.resource_dir / "happy.png").convert("RGBA"),
            "powerful": Image.open(self.resource_dir / "powerful.png").convert("RGBA"),
            "pure": Image.open(self.resource_dir / "pure.png").convert("RGBA"),
        }

        # Load band images
        self.bands = {
            "1": Image.open(self.resource_dir / "band_1.png").convert("RGBA"),
            "2": Image.open(self.resource_dir / "band_2.png").convert("RGBA"),
            "3": Image.open(self.resource_dir / "band_3.png").convert("RGBA"),
            "4": Image.open(self.resource_dir / "band_4.png").convert("RGBA"),
            "5": Image.open(self.resource_dir / "band_5.png").convert("RGBA"),
            "18": Image.open(self.resource_dir / "band_18.png").convert("RGBA"),
            "21": Image.open(self.resource_dir / "band_21.png").convert("RGBA"),
            "45": Image.open(self.resource_dir / "band_45.png").convert("RGBA"),
        }

        # Load frame images
        self.frames = {
            "1": {
                "cool": Image.open(self.resource_dir / "card-1-cool.png").convert(
                    "RGBA"
                ),
                "happy": Image.open(self.resource_dir / "card-1-happy.png").convert(
                    "RGBA"
                ),
                "powerful": Image.open(
                    self.resource_dir / "card-1-powerful.png"
                ).convert("RGBA"),
                "pure": Image.open(self.resource_dir / "card-1-pure.png").convert(
                    "RGBA"
                ),
            },
            "2": Image.open(self.resource_dir / "card-2.png").convert("RGBA"),
            "3": Image.open(self.resource_dir / "card-3.png").convert("RGBA"),
            "4": Image.open(self.resource_dir / "card-4.png").convert("RGBA"),
            "5": Image.open(self.resource_dir / "card-5.png").convert("RGBA"),
        }
        self.card_back = Image.open(self.resource_dir / "card-back.png").convert("RGBA")

        # Load star images
        self.star = Image.open(self.resource_dir / "star.png").convert("RGBA")
        self.star_trained = Image.open(self.resource_dir / "star_trained.png").convert(
            "RGBA"
        )

        # Load face positions (if exists)
        if self.face_positions:
            logger.info(f"已加载 {len(self.face_positions)} 张图片的人脸位置数据")
        else:
            logger.info("未找到预计算的人脸位置数据，将使用备用检测方法")

        # Load face cascade classifier
        if self.cascade:
            logger.info("已加载人脸级联分类器")
        else:
            logger.info("未找到人脸级联分类器，将使用备用检测方法")
        # Anime Face Detector from https://github.com/nagadomi/lbpcascade_animeface
        # Thanks to nagadomi for the model!

        logger.info("黑杰克资源加载完成")

    def filter_cards(
        self, attr: str, star_num: int, character_id: Optional[int] = None
    ):
        """根据属性、星级和可选的角色ID筛选卡牌"""
        cards = [
            (card_id, card)
            for card_id, card in self.card_data.items()
            if card["attribute"] == attr
            and card["rarity"] == star_num
            and (character_id is None or card["characterId"] == character_id)
        ]
        return [
            {
                "id": card_id,
                "character_id": card["characterId"],
                "band_id": self.character_data[str(card["characterId"])]["bandId"],
                "resource_set_name": card["resourceSetName"],
            }
            for card_id, card in cards
        ]

    def get_card_images(self, resource_set_name: str) -> list[str]:
        """获取指定资源集名称的卡牌图片路径"""
        folder = store.get_data_dir("cck") / "cards" / resource_set_name[:6]
        if not folder.exists():
            return []
        return [
            str(file)
            for file in folder.glob("*.png")
            if file.name.startswith(resource_set_name)
        ]

    def get_face_center_from_precomputed(
        self, image_path: str
    ) -> Optional[Tuple[int, int]]:
        """
        从预计算的 JSON 文件中获取人脸中心位置

        Args:
            image_path: 图片路径

        Returns:
            Optional[Tuple[int, int]]: 人脸中心坐标 (x, y)，如果未找到返回 None
        """
        # 标准化路径（使用文件名作为键）
        normalized_path = str(Path(image_path).name)

        if normalized_path in self.face_positions:
            face_data = self.face_positions[normalized_path]
            if isinstance(face_data, dict) and "center" in face_data:
                center = face_data["center"]
                if isinstance(center, list) and len(center) == 2:
                    return (int(center[0]), int(center[1]))
            elif isinstance(face_data, list) and len(face_data) == 2:
                # 兼容简单格式：直接存储 [x, y]
                return (int(face_data[0]), int(face_data[1]))
            elif isinstance(face_data, list) and len(face_data) == 4:
                # 兼容旧格式：直接存储 [x, y, w, h]
                return (
                    int(face_data[0] + face_data[2] // 2),
                    int(face_data[1] + face_data[3] // 2),
                )

        return None

    def detect_face_with_opencv(self, image: cv2.Mat) -> Tuple[int, int]:
        """
        使用 OpenCV 检测人脸中心位置（备用方案）

        Args:
            image: OpenCV 图片对象

        Returns:
            Tuple[int, int]: 人脸中心坐标 (x, y)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        faces = self.cascade.detectMultiScale(
            gray,
            # detector options
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(24, 24),
        )

        # 处理越界行为：如果没有检测到人脸，使用图片中心作为默认值
        if len(faces) == 0:
            # 如果没有检测到人脸，使用图片中心
            return (image.shape[1] // 2, image.shape[0] // 2)
        else:
            # 选择中间的人脸
            face = faces[len(faces) // 2]
            return (face[0] + face[2] // 2, face[1] + face[3] // 2)

    def cut_card(self, image_name: str) -> Image.Image:
        """
        裁剪卡牌图片，优先使用预计算的人脸位置，否则使用 OpenCV 检测

        Args:
            image_name: 图片路径

        Returns:
            Image.Image: 裁剪后的图片
        """
        if image_name in self.image_face_cache:
            return self.image_face_cache[image_name]

        image = cv2.imread(image_name, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"无法读取图片: {image_name}")

        # 首先尝试从预计算数据中获取人脸位置
        center = self.get_face_center_from_precomputed(image_name)

        if center is None:
            # 如果预计算数据中没有，使用 OpenCV 检测
            logger.info(f"使用备用人脸检测方法处理图片: {image_name}")
            center = self.detect_face_with_opencv(image)
        else:
            logger.info(f"使用预计算的人脸位置数据处理图片: {Path(image_name).name}")

        target_width, target_height = 594, 850

        # 计算裁剪区域的左上角坐标
        left = center[0] - target_width // 2
        top = center[1] - target_height // 2

        # 处理越界行为：确保裁剪区域不超出图片边界
        image_height, image_width = image.shape[:2]
        left = max(0, min(left, image_width - target_width))
        top = max(0, min(top, image_height - target_height))

        # 如果图片太小，需要调整目标尺寸
        actual_width = min(target_width, image_width - left)
        actual_height = min(target_height, image_height - top)

        # 裁剪图片
        cropped = image[top : top + actual_height, left : left + actual_width]

        # 转换为PIL Image并返回
        cropped_rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(cropped_rgb)

        # 如果裁剪后的尺寸不够，需要填充到目标尺寸
        if actual_width < target_width or actual_height < target_height:
            # 创建一个目标尺寸的空白图片
            result = Image.new("RGB", (target_width, target_height), (255, 255, 255))
            # 将裁剪的图片粘贴到中心位置
            paste_x = (target_width - actual_width) // 2
            paste_y = (target_height - actual_height) // 2
            result.paste(pil_image, (paste_x, paste_y))
            self.image_face_cache[image_name] = result
            return result

        self.image_face_cache[image_name] = pil_image
        return pil_image

    def generate_card(
        self,
        card_value: str,
        suit: str,
        card_image_path: Optional[str] = None,
        band_id: Optional[int] = None,
        ace_value: Optional[int] = None,
    ) -> Tuple[Image.Image, Callable[[Optional[int]], Image.Image]]:
        """
        根据牌面值生成一张卡牌

        Args:
            card_value: 牌面值 ("2"-"10", "A", "J", "Q", "K")
            suit: 卡牌花色 ("cool", "happy", "powerful", "pure")
            card_image_path: 卡牌图片路径
            band_id: 卡牌背景id
            ace_value: A牌的点数值 (1 或 11)，仅当card_value为"A"时需要

        Returns:
            Tuple[Image.Image, Callable[[Optional[int]], Image.Image]]: (卡牌图片, 生成器函数)
        """
        if card_value == "A":
            if ace_value not in [1, 11]:
                raise ValueError("A牌必须指定点数值为1或11")
            frame_type, star_num, star_trained_num, rarity = self.ACE_CONFIGS[ace_value]
        elif card_value in self.CARD_CONFIGS:
            frame_type, star_num, star_trained_num, rarity = self.CARD_CONFIGS[
                card_value
            ]
        else:
            raise ValueError(f"无效的牌面值: {card_value}")

        # 获取框架和属性图片
        if frame_type == "1":
            frame = self.frames["1"][suit]
        else:
            frame = self.frames[frame_type]

        attr = self.attrs[suit]

        # 创建画布
        canvas = frame.copy()
        canvas.paste(attr, (473, 11), attr)

        # 添加星星
        y = 896 - (640 - 513)
        for _ in range(star_trained_num):
            canvas.paste(self.star_trained, (10, y), self.star_trained)
            y -= 80

        for _ in range(star_num):
            canvas.paste(self.star, (10, y), self.star)
            y -= 80

        # 随机选择一张符合条件的卡牌
        if card_image_path is None or band_id is None:
            available_cards = self.filter_cards(
                suit, rarity, 1 if card_value == "A" else None
            )
            if not available_cards:
                raise ValueError(
                    f"没有找到符合条件的卡牌 (suit={suit}, rarity={rarity})"
                )

            # 重试逻辑：最多尝试3次选择卡牌和图片
            card = None
            card_images = []

            for attempt in range(3):
                card = random.choice(available_cards)
                card_images = self.get_card_images(card["resource_set_name"])

                if card_images:
                    card_image_path = random.choice(card_images)
                    band_id = card["band_id"]
                    break
                else:
                    logger.warning(
                        f"尝试 {attempt + 1}: 没有找到卡牌图片: {card['resource_set_name']}"
                    )

            if card_image_path is None:
                raise ValueError(
                    f"重试3次后仍然没有找到可用的卡牌图片 (suit={suit}, rarity={rarity})"
                )

        card_image = self.cut_card(card_image_path)

        # 生成最终的卡牌图片
        final_canvas = Image.new("RGBA", (640, 896), (0, 0, 0, 0))
        final_canvas.paste(card_image, (23, 23))
        final_canvas.paste(canvas, (0, 0), canvas)
        final_canvas.paste(self.bands[str(band_id)], (0, 0), self.bands[str(band_id)])

        # 构建卡牌数据
        def generate_the_card(ace_value: Optional[int] = None) -> Image.Image:
            return self.generate_card(
                card_value, suit, card_image_path, band_id, ace_value
            )[0]

        return final_canvas, generate_the_card

    def draw_rounded_rectangle(
        self,
        draw: ImageDraw.ImageDraw,
        bbox: Tuple[int, int, int, int],
        corner_radius: int = 10,
        fill: Optional[Tuple[int, int, int, int]] = None,
        outline: Optional[Tuple[int, int, int, int]] = None,
        width: int = 1,
    ):
        """
        绘制圆角矩形

        参数说明:
            draw: ImageDraw 对象
            bbox: 矩形边界框 (left, top, right, bottom)
            corner_radius: 圆角半径，默认为10
            fill: 填充颜色 (R, G, B, A)，None表示不填充
            outline: 边框颜色 (R, G, B, A)，None表示无边框
            width: 边框宽度，默认为1
        """
        left, top, right, bottom = bbox

        # 确保圆角半径不超过矩形的一半
        max_radius = min((right - left) // 2, (bottom - top) // 2)
        corner_radius = min(corner_radius, max_radius)

        # 如果圆角半径为0，直接绘制普通矩形
        if corner_radius <= 0:
            draw.rectangle(bbox, fill=fill, outline=outline, width=width)
            return

        # 创建临时图像来绘制圆角矩形
        temp_img = Image.new("RGBA", (right - left, bottom - top), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp_img)

        # 绘制圆角矩形的各个部分
        w, h = right - left, bottom - top

        # 绘制填充部分
        if fill:
            # 中心矩形（水平）
            temp_draw.rectangle([corner_radius, 0, w - corner_radius, h], fill=fill)
            # 中心矩形（垂直）
            temp_draw.rectangle([0, corner_radius, w, h - corner_radius], fill=fill)

            # 四个圆角
            # 左上角
            temp_draw.pieslice(
                [0, 0, corner_radius * 2, corner_radius * 2], 180, 270, fill=fill
            )
            # 右上角
            temp_draw.pieslice(
                [w - corner_radius * 2, 0, w, corner_radius * 2], 270, 360, fill=fill
            )
            # 左下角
            temp_draw.pieslice(
                [0, h - corner_radius * 2, corner_radius * 2, h], 90, 180, fill=fill
            )
            # 右下角
            temp_draw.pieslice(
                [w - corner_radius * 2, h - corner_radius * 2, w, h], 0, 90, fill=fill
            )

        # 绘制边框
        if outline and width > 0:
            # 如果有边框，需要多次绘制来实现指定宽度
            for i in range(width):
                # 上边框
                temp_draw.line([corner_radius, i, w - corner_radius, i], fill=outline)
                # 下边框
                temp_draw.line(
                    [corner_radius, h - i - 1, w - corner_radius, h - i - 1],
                    fill=outline,
                )
                # 左边框
                temp_draw.line([i, corner_radius, i, h - corner_radius], fill=outline)
                # 右边框
                temp_draw.line(
                    [w - i - 1, corner_radius, w - i - 1, h - corner_radius],
                    fill=outline,
                )

                # 四个圆角边框
                # 左上角
                temp_draw.arc(
                    [i, i, corner_radius * 2 - i, corner_radius * 2 - i],
                    180,
                    270,
                    fill=outline,
                )
                # 右上角
                temp_draw.arc(
                    [w - corner_radius * 2 + i, i, w - i, corner_radius * 2 - i],
                    270,
                    360,
                    fill=outline,
                )
                # 左下角
                temp_draw.arc(
                    [i, h - corner_radius * 2 + i, corner_radius * 2 - i, h - i],
                    90,
                    180,
                    fill=outline,
                )
                # 右下角
                temp_draw.arc(
                    [
                        w - corner_radius * 2 + i,
                        h - corner_radius * 2 + i,
                        w - i,
                        h - i,
                    ],
                    0,
                    90,
                    fill=outline,
                )

        # 将临时图像粘贴到原图像上
        if hasattr(draw, "_image"):
            draw._image.paste(temp_img, (left, top), temp_img.split()[3])

    def _generate_background(self, width: int, height: int) -> Image.Image:
        """生成背景图片"""
        background = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        pattern = Image.open(self.resource_dir / "bg_object_big.png").convert("RGBA")
        for x in range(0, width, pattern.width):
            for y in range(0, height, pattern.height):
                background.paste(pattern, (x, y), pattern.split()[3])
        return background

    def generate_hand(self, hand: "Hand", second_card_back: bool) -> Image.Image:
        """生成手牌的图片"""
        # 计算布局尺寸
        card_count = len(hand.cards)
        container_width, container_height = self._calculate_card_container_dimensions(
            card_count
        )

        # 为分数文字添加额外空间
        score_area_height = self.TableLayout.CARD_TEXT_FONT_SIZE
        total_width = container_width + self.TableLayout.MARGIN * 2
        total_height = (
            container_height + score_area_height + self.TableLayout.MARGIN * 2
        )

        background = self._generate_background(total_width, total_height)

        # 绘制卡牌
        cards_start_x = (
            self.TableLayout.MARGIN
            + self.TableLayout.CARD_CONTAINER_PADDING_HORIZONTAL
            + self.TableLayout.CARD_SPACING
        )
        cards_start_y = (
            self.TableLayout.MARGIN + self.TableLayout.CARD_CONTAINER_PADDING_VERTICAL
        )
        self._draw_hand_cards(
            background, hand, cards_start_x, cards_start_y, second_card_back
        )

        # 绘制分数文字
        draw = ImageDraw.Draw(background)
        if second_card_back:
            score_text = f"共 {hand.cards[0].get_value()} + ? 点"
        else:
            score_text = f"共 {hand.value} 点"

        text_bbox = draw.textbbox(
            (0, 0), score_text, font=self.get_font(self.TableLayout.CARD_TEXT_FONT_SIZE)
        )
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # 将分数文字绘制在右下角
        text_x = total_width - text_width - self.TableLayout.MARGIN // 4
        text_y = total_height - text_height - self.TableLayout.MARGIN // 4

        draw.text(
            (text_x, text_y),
            score_text,
            fill=self.TableLayout.WHITE_TEXT_COLOR,
            font=self.get_font(self.TableLayout.CARD_TEXT_FONT_SIZE),
            stroke_width=self.TableLayout.CARD_TEXT_STROKE_WIDTH,
            stroke_fill=self.TableLayout.BLACK_TEXT_COLOR,
        )

        return background

    class TableLayout:
        """游戏桌面布局配置"""

        # 基础尺寸
        CARD_WIDTH = 640
        CARD_HEIGHT = 896
        CARD_PADDING = 32  # 卡牌内部padding

        # 间距配置
        MARGIN = 64  # 外边距
        CARD_SPACING = 64  # 卡牌间距
        SECTION_SPACING = 32  # 区块间距

        # 名字标签配置
        NAME_TAG_WIDTH = 320
        NAME_TAG_HEIGHT = 90
        NAME_TAG_FONT_SIZE = 80
        NAME_TAG_TEXT_OFFSET = 16  # 文字在标签内的偏移

        # 卡牌容器配置
        CARD_CONTAINER_PADDING_HORIZONTAL = 32  # 容器水平内边距
        CARD_CONTAINER_PADDING_VERTICAL = 64  # 容器垂直内边距
        CORNER_RADIUS = 32
        BORDER_WIDTH = 4

        # 文字配置
        CARD_TEXT_FONT_SIZE = 64
        CARD_TEXT_PADDING_HORIZONTAL = 20  # 卡牌点数水平偏移
        CARD_TEXT_PADDING_VERTICAL = 30  # 卡牌点数垂直偏移
        CARD_TEXT_STROKE_WIDTH = 2

        # 颜色配置
        DEALER_TAG_COLOR = (0xFF, 0x55, 0x22, 255)
        PLAYER_TAG_COLOR = (0x33, 0x75, 0xD6, 255)
        CONTAINER_FILL_COLOR = (255, 255, 255, 230)
        CONTAINER_BORDER_COLOR = (200, 200, 200, 255)
        WHITE_TEXT_COLOR = (255, 255, 255, 255)
        BLACK_TEXT_COLOR = (0, 0, 0, 255)

    def _calculate_card_container_dimensions(self, card_count: int) -> tuple[int, int]:
        """计算卡牌容器的尺寸"""
        width = (
            card_count * self.TableLayout.CARD_WIDTH
            + (card_count + 1) * self.TableLayout.CARD_SPACING
            + self.TableLayout.CARD_CONTAINER_PADDING_HORIZONTAL * 2  # 左右padding
        )
        height = (
            self.TableLayout.CARD_HEIGHT
            + self.TableLayout.CARD_CONTAINER_PADDING_VERTICAL * 2  # 上下padding
        )
        return width, height

    def _calculate_table_size(
        self, dealer_hand: "Hand", player_hand: "Hand"
    ) -> tuple[int, int]:
        """计算整个桌面的尺寸"""
        max_cards = max(len(dealer_hand.cards), len(player_hand.cards))
        base_width = (
            max_cards * self.TableLayout.CARD_WIDTH
            + (max_cards + 1) * self.TableLayout.CARD_SPACING
            + self.TableLayout.CARD_CONTAINER_PADDING_HORIZONTAL * 2  # 容器左右padding
            + self.TableLayout.MARGIN * 2  # 外边距
        )

        total_height = (
            self.TableLayout.MARGIN  # 顶部边距
            + self.TableLayout.NAME_TAG_HEIGHT  # 庄家标签
            + self.TableLayout.MARGIN  # 标签下边距
            + self.TableLayout.CARD_HEIGHT
            + self.TableLayout.CARD_CONTAINER_PADDING_VERTICAL
            * 2  # 庄家卡牌区域(上下padding)
            + self.TableLayout.SECTION_SPACING  # 区块间距
            + self.TableLayout.NAME_TAG_HEIGHT  # 玩家标签
            + self.TableLayout.MARGIN  # 标签下边距
            + self.TableLayout.CARD_HEIGHT
            + self.TableLayout.CARD_CONTAINER_PADDING_VERTICAL
            * 2  # 玩家卡牌区域(上下padding)
            + self.TableLayout.MARGIN  # 底部边距
        )

        return base_width, total_height

    def _draw_name_tag_with_score(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        name: str,
        score_text: str,
        color: tuple,
    ):
        """绘制包含名字和分数的标签"""
        # 计算需要的标签宽度
        font = self.get_font(self.TableLayout.NAME_TAG_FONT_SIZE)
        name_bbox = draw.textbbox((0, 0), name, font=font)
        score_bbox = draw.textbbox((0, 0), f" - {score_text}", font=font)

        name_width = name_bbox[2] - name_bbox[0]
        score_width = score_bbox[2] - score_bbox[0]
        total_text_width = name_width + score_width

        # 动态调整标签宽度
        tag_width = max(self.TableLayout.NAME_TAG_WIDTH, total_text_width + 32)

        self.draw_rounded_rectangle(
            draw,
            bbox=(
                x,
                y,
                x + tag_width,
                y + self.TableLayout.NAME_TAG_HEIGHT,
            ),
            corner_radius=self.TableLayout.CORNER_RADIUS,
            fill=color,
        )

        # 计算文字居中位置
        text_height = name_bbox[3] - name_bbox[1]
        text_x = x + (tag_width - total_text_width) // 2
        text_y = y + (self.TableLayout.NAME_TAG_HEIGHT - text_height) // 2 - 20

        # 绘制名字（白色）
        draw.text(
            (text_x, text_y),
            name,
            fill=self.TableLayout.WHITE_TEXT_COLOR,
            font=font,
        )

        # 绘制分数（稍微透明的白色）
        draw.text(
            (text_x + name_width, text_y),
            f" - {score_text}",
            fill=(255, 255, 255, 200),
            font=font,
        )

        return tag_width

    def _draw_card_container(
        self, draw: ImageDraw.ImageDraw, x: int, y: int, width: int, height: int
    ):
        """绘制卡牌容器背景"""
        self.draw_rounded_rectangle(
            draw,
            bbox=(x, y, x + width, y + height),
            corner_radius=self.TableLayout.CORNER_RADIUS,
            fill=self.TableLayout.CONTAINER_FILL_COLOR,
            outline=self.TableLayout.CONTAINER_BORDER_COLOR,
            width=self.TableLayout.BORDER_WIDTH,
        )

    def _render_card_with_text(self, card, show_back: bool = False) -> Image.Image:
        """渲染单张卡牌并添加文字"""
        if show_back:
            card_image = self.card_back.copy()
        else:
            if card._get_image is not None:
                card_image = card._get_image(card.ace_value)
            else:
                card_image, generate_the_card = self.generate_card(
                    card.rank, card.suit, None, None, card.ace_value
                )
                card._get_image = generate_the_card

            # 在卡牌上添加数值文字
            card_draw = ImageDraw.Draw(card_image)
            text = str(card.get_value())
            text_bbox = card_draw.textbbox(
                (0, 0), text, font=self.get_font(self.TableLayout.CARD_TEXT_FONT_SIZE)
            )
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            card_draw.text(
                (
                    self.TableLayout.CARD_WIDTH
                    - text_width
                    - self.TableLayout.CARD_TEXT_PADDING_HORIZONTAL,
                    self.TableLayout.CARD_HEIGHT
                    - text_height
                    - self.TableLayout.CARD_TEXT_PADDING_VERTICAL,
                ),
                text,
                fill=self.TableLayout.WHITE_TEXT_COLOR,
                font=self.get_font(self.TableLayout.CARD_TEXT_FONT_SIZE),
                stroke_width=self.TableLayout.CARD_TEXT_STROKE_WIDTH,
                stroke_fill=self.TableLayout.BLACK_TEXT_COLOR,
            )

        return card_image

    def _draw_hand_score(
        self,
        background: Image.Image,
        hand: "Hand",
        container_x: int,
        score_y: int,
        container_width: int,
        show_hidden: bool = False,
    ):
        """绘制手牌分数"""
        draw = ImageDraw.Draw(background)

        if show_hidden:
            score_text = f"共 {hand.cards[0].get_value()} + ? 点"
        else:
            score_text = f"共 {hand.value} 点"

        font = self.get_font(self.TableLayout.CARD_TEXT_FONT_SIZE)
        text_bbox = draw.textbbox((0, 0), score_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]

        # 将分数文字居中显示在容器内
        text_x = container_x + (container_width - text_width) // 2

        draw.text(
            (text_x, score_y),
            score_text,
            fill=self.TableLayout.BLACK_TEXT_COLOR,
            font=font,
        )

    def _draw_hand_cards(
        self,
        background: Image.Image,
        hand: "Hand",
        start_x: int,
        start_y: int,
        show_second_back: bool = False,
    ):
        """绘制一手牌"""
        for i, card in enumerate(hand.cards):
            show_back = show_second_back and i == 1
            card_image = self._render_card_with_text(card, show_back)

            card_x = start_x + i * (
                self.TableLayout.CARD_WIDTH + self.TableLayout.CARD_SPACING
            )
            background.paste(card_image, (card_x, start_y), card_image.split()[3])

    def generate_table(
        self, dealer_hand: "Hand", player_hand: "Hand", dealer_card_back: bool
    ) -> Image.Image:
        """生成包含庄家和玩家手牌的游戏桌面"""
        # 计算布局尺寸
        table_width, table_height = self._calculate_table_size(dealer_hand, player_hand)
        background = self._generate_background(table_width, table_height)
        draw = ImageDraw.Draw(background)

        # 当前Y位置追踪器
        current_y = self.TableLayout.MARGIN

        # 绘制庄家标签（包含分数）
        if dealer_card_back:
            dealer_score = f"共 {dealer_hand.cards[0].get_value()} + ? 点"
        else:
            dealer_score = f"共 {dealer_hand.value} 点"

        _dealer_tag_width = self._draw_name_tag_with_score(
            draw,
            self.TableLayout.MARGIN,
            current_y,
            "Kasumi",
            dealer_score,
            self.TableLayout.DEALER_TAG_COLOR,
        )
        current_y += self.TableLayout.NAME_TAG_HEIGHT + self.TableLayout.MARGIN

        # 绘制庄家卡牌容器
        dealer_container_width, dealer_container_height = (
            self._calculate_card_container_dimensions(len(dealer_hand.cards))
        )
        self._draw_card_container(
            draw,
            self.TableLayout.MARGIN,
            current_y,
            dealer_container_width,
            dealer_container_height,
        )

        # 绘制庄家卡牌
        cards_start_x = (
            self.TableLayout.MARGIN
            + self.TableLayout.CARD_CONTAINER_PADDING_HORIZONTAL
            + self.TableLayout.CARD_SPACING
        )
        cards_start_y = current_y + self.TableLayout.CARD_CONTAINER_PADDING_VERTICAL
        self._draw_hand_cards(
            background, dealer_hand, cards_start_x, cards_start_y, dealer_card_back
        )

        current_y += dealer_container_height + self.TableLayout.SECTION_SPACING

        # 绘制玩家标签（包含分数）
        player_score = f"共 {player_hand.value} 点"
        _player_tag_width = self._draw_name_tag_with_score(
            draw,
            self.TableLayout.MARGIN,
            current_y,
            "You",
            player_score,
            self.TableLayout.PLAYER_TAG_COLOR,
        )
        current_y += self.TableLayout.NAME_TAG_HEIGHT + self.TableLayout.MARGIN

        # 绘制玩家卡牌容器
        player_container_width, player_container_height = (
            self._calculate_card_container_dimensions(len(player_hand.cards))
        )
        self._draw_card_container(
            draw,
            self.TableLayout.MARGIN,
            current_y,
            player_container_width,
            player_container_height,
        )

        # 绘制玩家卡牌
        cards_start_x = (
            self.TableLayout.MARGIN
            + self.TableLayout.CARD_CONTAINER_PADDING_HORIZONTAL
            + self.TableLayout.CARD_SPACING
        )
        cards_start_y = current_y + self.TableLayout.CARD_CONTAINER_PADDING_VERTICAL
        self._draw_hand_cards(
            background, player_hand, cards_start_x, cards_start_y, False
        )

        # 确保没有透明背景
        result = Image.new("RGBA", (table_width, table_height), (255, 255, 255, 255))
        result.paste(background, (0, 0), background.split()[3])

        # 缩小图片
        result = result.resize(
            (table_width // 2, table_height // 2), Image.Resampling.LANCZOS
        )
        result = result.convert("RGB")

        return result
