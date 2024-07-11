import os
import random
import aiohttp
from typing import Tuple
from pathlib import Path
from nonebot import logger
from aiohttp import ClientTimeout

from .downloader import AsyncDownloader


class Card:
    """
    卡牌信息获取
    """

    def __init__(self, proxy: str = None):
        self.initialized = False
        self._proxy = proxy

    async def initialize(self, base_path: Path, cache_path: Path):
        logger.info("Card: 正在初始化")

        self.base_path = base_path / "cards"

        self.downloader = AsyncDownloader(cache_path, self.base_path)

        await self._get_data()

        logger.success("Card: 成功初始化")
        self.initialized = True

    async def _get_data(self):
        summary_url = "https://bestdori.com/api/cards/all.5.json"
        async with aiohttp.ClientSession(timeout=ClientTimeout(30)) as session:
            async with session.get(summary_url, proxy=self._proxy) as response:
                self.__summary_data__: dict = await response.json()
        logger.success("Card: 成功获取卡牌简略数据")

        self.__processed_data__ = {
            k: v
            for k, v in self.__summary_data__.items()
            if int(k) < 5001 and v["type"] != "others"
        }

        # 更新立绘、缩略图
        await self._update_card_img()

    async def _update_card_img(self):
        res, server_dict = [], {}

        bad_res = await self._get_bad_res()

        for i, v in self.__summary_data__.items():
            res_data, server = await self._get_res_info(i)
            server_dict[v["resourceSetName"]] = server
            if res_data["normal"]:
                res.append(f'{v["resourceSetName"]}_card_normal.png')
            if res_data["trained"]:
                res.append(f'{v["resourceSetName"]}_card_after_training.png')

        _miss_cards = list(
            set(res).difference(set(await self._get_file_name(self.base_path)))
        )

        miss_cards = []

        for v in _miss_cards:
            if v not in bad_res:
                miss_cards.append(v)

        if len(miss_cards) > 0:
            logger.warning(f"Card: 卡面资源未下载: {miss_cards}")
            logger.info("Card: 开始尝试下载卡面资源")
            await self.downloader.download_cards(miss_cards, server_dict)
        else:
            logger.info("Card: 卡面资源加载成功")

    async def _get_file_name(self, file_dir):
        names = []
        for _, _, files in os.walk(file_dir):
            names += files
        return names

    async def _get_bad_res(self) -> tuple:
        res_lst = []
        for s in await self.downloader.get_bad_urls():
            if "characters" in s:
                res_id = s.split("/")[7].split("_")[0][3:]
                if "after_training" in s:
                    res_lst.append(f"res{res_id}_card_after_training.png")
                elif "normal" in s:
                    res_lst.append(f"res{res_id}_card_normal.png")
        return res_lst

    async def _get_res_info(self, card_id: int) -> Tuple[dict, str]:
        card_id = str(card_id)
        type = self.__summary_data__[card_id]["type"]
        server = "jp"
        for i in [0, 3, 2, 1, 4]:
            if self.__summary_data__[card_id]["prefix"][i]:
                server = ["jp", "en", "tw", "cn", "kr"][i]
                break

        result_map = {
            "initial": ({"normal": True, "trained": False}, server),
            "permanent": (
                {
                    "normal": True,
                    "trained": (
                        True
                        if self.__summary_data__[card_id]["stat"].get("training")
                        else False
                    ),
                },
                server,
            ),
            "event": (
                {
                    "normal": True,
                    "trained": (
                        True
                        if self.__summary_data__[card_id]["stat"].get("training")
                        else False
                    ),
                },
                server,
            ),
            "limited": (
                {
                    "normal": True,
                    "trained": (
                        True
                        if self.__summary_data__[card_id]["stat"].get("training")
                        else False
                    ),
                },
                server,
            ),
            "campaign": (
                {
                    "normal": True,
                    "trained": (
                        True
                        if self.__summary_data__[card_id]["stat"].get("training")
                        else False
                    ),
                },
                server,
            ),
            "others": (
                {
                    "normal": (
                        True
                        if self.__summary_data__[card_id]["stat"].get("training")
                        else False
                    ),
                    "trained": True,
                },
                server,
            ),
            "dreamfes": ({"normal": True, "trained": True}, server),
            "birthday": ({"normal": False, "trained": True}, server),
            "kirafes": ({"normal": False, "trained": True}, server),
        }

        return result_map[type]

    async def random_card_image(self) -> Tuple[str, str, Path]:
        """随机获取一张卡面图片

        Returns:
            Tuple[str, str, Path]: 包含角色ID，卡片ID，和卡片图像路径的元组。
        """
        filtered_data = {
            key: value
            for key, value in self.__processed_data__.items()
            if value.get("rarity", 0) >= 3
        }
        card_id: str = random.choice(list(filtered_data.keys()))
        card_data = self.__processed_data__[card_id]

        character_id = str(card_data["characterId"])

        res_data, _ = await self._get_res_info(card_id)

        if res_data["normal"] and not res_data["trained"]:
            card_path = (
                self.base_path
                / f"res{character_id.zfill(3)}"
                / f"{card_data['resourceSetName']}_card_normal.png"
            )
        elif res_data["trained"] and not res_data["normal"]:
            card_path = (
                self.base_path
                / f"res{character_id.zfill(3)}"
                / f"{card_data['resourceSetName']}_card_after_training.png"
            )
        else:
            # 随机选择一个
            card_path = random.choice(
                [
                    self.base_path
                    / f"res{character_id.zfill(3)}"
                    / f"{card_data['resourceSetName']}_card_normal.png",
                    self.base_path
                    / f"res{character_id.zfill(3)}"
                    / f"{card_data['resourceSetName']}_card_after_training.png",
                ]
            )

        if not card_path.exists():
            logger.warning(f"Card: 未找到卡面图片 {card_path}")
            return await self.random_card_image()

        return character_id, card_id, card_path
