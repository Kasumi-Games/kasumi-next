import random
from typing import List

suits = ("红", "蓝", "橙", "绿")
number_ranks = ("2", "3", "4", "5", "6", "7", "8", "9", "10")

# 每个属性对应的主唱组合 (J, Q, K, A)
# 确保所有8个乐队主唱都能出现，同时 Kasumi 在每个属性都是 A
suit_vocalists = {
    "红": {
        "J": "Yukina",
        "Q": "Ran",
        "K": "Aya",
        "A": "Kasumi",
    },
    "蓝": {
        "J": "Kokoro",
        "Q": "Mashiro",
        "K": "Layer",
        "A": "Kasumi",
    },
    "橙": {
        "J": "Tomori",
        "Q": "Yukina",
        "K": "Ran",
        "A": "Kasumi",
    },
    "绿": {
        "J": "Aya",
        "Q": "Kokoro",
        "K": "Mashiro",
        "A": "Kasumi",
    },
}


class Card:
    """代表一张牌"""

    def __init__(self, suit: str, rank: str):
        self.suit = suit
        self.rank = rank

    def __str__(self):
        return f"{self.suit} {self.rank}"

    def get_value(self) -> int:
        """获取牌的点数值"""
        if self.rank in ["2", "3", "4", "5", "6", "7", "8", "9", "10"]:
            return int(self.rank)
        elif self.rank in [
            "Yukina",
            "Ran",
            "Aya",
            "Kokoro",
            "Mashiro",
            "Layer",
            "Tomori",
        ]:  # J, Q, K 对应的主唱们
            return 10
        elif self.rank == "Kasumi":  # A (Kasumi)
            return 11
        else:
            raise ValueError(f"未知的牌面等级: {self.rank}")


class Shoe:
    """
    代表一个牌靴 (Shoe)，可以包含多副牌
    """

    def __init__(self, num_decks: int = 6):
        """
        初始化牌靴

        Args:
            num_decks: 牌靴中包含的扑克牌副数
        """
        self.deck = []
        for _ in range(num_decks):
            for suit in suits:
                ranks = number_ranks + (
                    suit_vocalists[suit]["J"],
                    suit_vocalists[suit]["Q"],
                    suit_vocalists[suit]["K"],
                    suit_vocalists[suit]["A"],
                )
                for rank in ranks:
                    self.deck.append(Card(suit, rank))

    def shuffle(self):
        """洗牌"""
        random.shuffle(self.deck)

    def deal(self):
        """从牌靴中发一张牌。须确保牌靴不为空。

        Raises:
            AssertionError: 牌靴为空

        Returns:
            Card: 发出的牌
        """
        assert self.deck, "牌靴为空"
        return self.deck.pop()


class Hand:
    """代表玩家或庄家手中的牌"""

    def __init__(self):
        """初始化手牌"""
        self.cards: List[Card] = []
        self.value: int = 0
        self.aces: int = 0

    def add_card(self, card: Card):
        """添加一张牌到手牌中"""
        self.cards.append(card)
        self.value += card.get_value()
        if card.rank == "Kasumi":  # A (Kasumi)
            self.aces += 1
        self._adjust_for_ace()

    def _adjust_for_ace(self):
        """调整手牌中的A值"""
        while self.value > 21 and self.aces > 0:
            self.value -= 10
            self.aces -= 1
