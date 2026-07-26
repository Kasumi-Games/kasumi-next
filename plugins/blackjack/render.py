import random
from typing import TYPE_CHECKING
from typing import Any
from typing import Dict
from typing import Tuple
from typing import Callable
from typing import Optional
from pathlib import Path

import cv2
import nonebot_plugin_localstore as store
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from nonebot.log import logger

from utils import cards
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import ColorLike
from plugins.render import Component
from plugins.render import RenderContext
from plugins.render import PlayerIdentity
from plugins.render.kits.bangdream import BanGDreamKit

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
        kit: Optional[BaseKit] = None,
    ):
        """
        初始化 BlackjackRenderer，支持自定义资源路径

        参数说明:
            resource_dir: 资源文件所在目录
            card_data: 卡牌数据
            character_data: 角色数据
            face_positions: 人脸位置数据
            cascade: 级联分类器
            kit: 渲染主题组件集合
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
        self.kit: BaseKit = kit or BanGDreamKit()

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

    def generate_hand(
        self,
        hand: "Hand",
        second_card_back: bool,
        identity: Optional[PlayerIdentity] = None,
        detail: Optional[str] = None,
    ) -> Image.Image:
        """生成手牌的图片"""
        if second_card_back:
            score_text = f"共 {hand.cards[0].get_value()} + ? 点"
        else:
            score_text = f"共 {hand.value} 点"
        sections: list[Component] = []
        strip = self._identity_strip(
            identity, detail, width=self._cards_panel_width(len(hand.cards))
        )
        if strip is not None:
            sections.append(strip)
        sections.append(
            self._hand_label(
                "Kasumi",
                score_text,
                self.RenderLayout.DEALER_TAG_COLOR,
            )
        )
        sections.append(self._cards_panel(hand, second_card_back))
        page = AutoPage(
            padding=self.RenderLayout.PAGE_PADDING,
            background=self.kit.background(),
            child=VStack(
                sections,
                gap=self.RenderLayout.SECTION_GAP,
                align="start",
            ),
        )
        return page.render(RenderContext())

    class RenderLayout:
        PAGE_PADDING = 32
        SECTION_GAP = 24
        CARD_GAP = 32
        PANEL_PADDING = 32
        PANEL_RADIUS = 32
        TABLE_MIN_WIDTH = 832

        CARD_SOURCE_WIDTH = 640
        CARD_SOURCE_HEIGHT = 896
        CARD_WIDTH = 160 * 2
        CARD_HEIGHT = 224 * 2

        NAME_TAG_WIDTH = 450
        NAME_TAG_HEIGHT = 48
        NAME_TAG_FONT_SIZE = 36

        CARD_TEXT_FONT_SIZE = 64
        CARD_TEXT_PADDING_HORIZONTAL = 20
        CARD_TEXT_PADDING_VERTICAL = 30
        CARD_TEXT_STROKE_WIDTH = 2

        DEALER_TAG_COLOR = (0xFF, 0x55, 0x22, 255)
        PLAYER_TAG_COLOR = (0x34, 0x74, 0xD6, 255)
        WHITE_TEXT_COLOR = (255, 255, 255, 255)
        BLACK_TEXT_COLOR = (0, 0, 0, 255)

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
                (0, 0), text, font=self.get_font(self.RenderLayout.CARD_TEXT_FONT_SIZE)
            )
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            card_draw.text(
                (
                    self.RenderLayout.CARD_SOURCE_WIDTH
                    - text_width
                    - self.RenderLayout.CARD_TEXT_PADDING_HORIZONTAL,
                    self.RenderLayout.CARD_SOURCE_HEIGHT
                    - text_height
                    - self.RenderLayout.CARD_TEXT_PADDING_VERTICAL,
                ),
                text,
                fill=self.RenderLayout.WHITE_TEXT_COLOR,
                font=self.get_font(self.RenderLayout.CARD_TEXT_FONT_SIZE),
                stroke_width=self.RenderLayout.CARD_TEXT_STROKE_WIDTH,
                stroke_fill=self.RenderLayout.BLACK_TEXT_COLOR,
            )

        return card_image

    def _cards_panel_width(self, card_count: int) -> int:
        """Width of a cards panel holding ``card_count`` cards."""
        layout = self.RenderLayout
        count = max(1, card_count)
        return (
            count * layout.CARD_WIDTH
            + (count - 1) * layout.CARD_GAP
            + layout.PANEL_PADDING * 2
        )

    def _identity_strip(
        self,
        identity: Optional[PlayerIdentity],
        detail: Optional[str],
        *,
        width: int,
    ) -> Optional[Component]:
        """The player identity strip above the table, or ``None`` without one."""
        if identity is None:
            return None
        return cards.game_identity(self.kit, identity, width=width, detail=detail)

    def _hand_label(self, name: str, score_text: str, fill: ColorLike):
        if isinstance(self.kit, BanGDreamKit):
            return self.kit.pill(
                f"{name} - {score_text}",
                fill=fill,
                width=Fixed(self.RenderLayout.NAME_TAG_WIDTH),
                height=Fixed(self.RenderLayout.NAME_TAG_HEIGHT),
                font_size=self.RenderLayout.NAME_TAG_FONT_SIZE,
            )
        return self.kit.panel(
            Frame(
                self.kit.text(
                    f"{name} - {score_text}",
                    font_size=self.RenderLayout.NAME_TAG_FONT_SIZE,
                    color=self.RenderLayout.WHITE_TEXT_COLOR,
                    align="center",
                    max_lines=1,
                ),
                align_x="center",
                align_y="center",
            ),
            width=Fixed(self.RenderLayout.NAME_TAG_WIDTH),
            height=Fixed(self.RenderLayout.NAME_TAG_HEIGHT),
            fill=fill,
            radius=self.RenderLayout.NAME_TAG_HEIGHT // 2,
        )

    def _cards_panel(self, hand: "Hand", show_second_back: bool = False):
        cards = []
        for index, card in enumerate(hand.cards):
            show_back = show_second_back and index == 1
            cards.append(
                self.kit.image(
                    self._render_card_with_text(card, show_back),
                    width=Fixed(self.RenderLayout.CARD_WIDTH),
                    height=Fixed(self.RenderLayout.CARD_HEIGHT),
                )
            )
        return self.kit.panel(
            HStack(cards, gap=self.RenderLayout.CARD_GAP, align="center"),
            padding=self.RenderLayout.PANEL_PADDING,
            radius=self.RenderLayout.PANEL_RADIUS,
        )

    def _hand_section(
        self,
        name: str,
        hand: "Hand",
        score_text: str,
        color: ColorLike,
        show_second_back: bool = False,
    ):
        return VStack(
            [
                self._hand_label(name, score_text, color),
                self._cards_panel(hand, show_second_back),
            ],
            gap=self.RenderLayout.SECTION_GAP,
            align="start",
        )

    def _draw_hand_cards(
        self,
        background: Image.Image,
        hand: "Hand",
        start_x: int,
        start_y: int,
        show_second_back: bool = False,
    ):
        """Compatibility helper for older tests and ad hoc scripts."""
        for i, card in enumerate(hand.cards):
            show_back = show_second_back and i == 1
            card_image = self._render_card_with_text(card, show_back)

            card_x = start_x + i * (
                self.RenderLayout.CARD_SOURCE_WIDTH + self.RenderLayout.CARD_GAP
            )
            background.paste(card_image, (card_x, start_y), card_image.split()[3])

    def generate_table(
        self,
        dealer_hand: "Hand",
        player_hand: "Hand",
        dealer_card_back: bool,
        identity: Optional[PlayerIdentity] = None,
        detail: Optional[str] = None,
    ) -> Image.Image:
        """生成包含庄家和玩家手牌的游戏桌面"""
        if dealer_card_back:
            dealer_score = f"共 {dealer_hand.cards[0].get_value()} + ? 点"
        else:
            dealer_score = f"共 {dealer_hand.value} 点"
        player_score = f"共 {player_hand.value} 点"
        strip_width = max(
            self.RenderLayout.TABLE_MIN_WIDTH - self.RenderLayout.PAGE_PADDING * 2,
            self._cards_panel_width(
                max(len(dealer_hand.cards), len(player_hand.cards))
            ),
        )
        sections: list[Component] = []
        strip = self._identity_strip(identity, detail, width=strip_width)
        if strip is not None:
            sections.append(strip)
        sections.append(
            self._hand_section(
                "Kasumi",
                dealer_hand,
                dealer_score,
                self.RenderLayout.DEALER_TAG_COLOR,
                dealer_card_back,
            )
        )
        sections.append(
            self._hand_section(
                "You",
                player_hand,
                player_score,
                self.RenderLayout.PLAYER_TAG_COLOR,
                False,
            )
        )
        page = AutoPage(
            min_width=self.RenderLayout.TABLE_MIN_WIDTH,
            padding=self.RenderLayout.PAGE_PADDING,
            background=self.kit.background(),
            child=VStack(
                sections,
                gap=self.RenderLayout.SECTION_GAP,
                align="stretch",
            ),
        )
        result = page.render(RenderContext())
        return result.convert("RGB")
