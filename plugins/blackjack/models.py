import random
from typing import List

suits = ("powerful", "cool", "happy", "pure")
number_ranks = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")


class Card:
    """代表一张牌"""

    def __init__(self, suit: str, rank: str):
        self.suit = suit
        self.rank = rank
        self._get_image = None
        # 对于A牌，默认值为11；其他牌此属性不使用
        self.ace_value = 11 if rank == "A" else None

    def __str__(self):
        return f"{self.suit} {self.rank}"

    def get_value(self) -> int:
        """获取牌的点数值"""
        if self.rank in ["2", "3", "4", "5", "6", "7", "8", "9", "10"]:
            return int(self.rank)
        elif self.rank in ["J", "Q", "K"]:
            return 10
        elif self.rank == "A":
            return self.ace_value
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
                for rank in number_ranks:
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

    def add_card(self, card: Card):
        """添加一张牌到手牌中"""
        self.cards.append(card)
        self._recalculate_value()

    def _recalculate_value(self):
        """重新计算手牌总值并调整A的值"""
        # 重置所有A为11
        for card in self.cards:
            if card.rank == "A":
                card.ace_value = 11

        # 计算总值
        self.value = sum(card.get_value() for card in self.cards)

        # 如果超过21，将A从11调整为1，直到不超过21或没有可调整的A
        aces_as_11 = [
            card for card in self.cards if card.rank == "A" and card.ace_value == 11
        ]
        while self.value > 21 and aces_as_11:
            # 将一个A从11调整为1
            ace_to_adjust = aces_as_11.pop()
            ace_to_adjust.ace_value = 1
            self.value -= 10  # 从11变为1，差值是10
