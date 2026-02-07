import random
from enum import Enum, StrEnum

from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base


class BlockType(Enum):
    EMPTY = 0
    MINE = 1
    EMPTY_SHOWN = 2
    MINE_SHOWN = 3


class Field:
    def __init__(self, width: int = 5, height: int = 5, mines: int = 3):
        self.width = width
        self.height = height
        self.mines = mines
        self.field = [[BlockType.EMPTY for _ in range(width)] for _ in range(height)]

        mine_positions = random.sample(range(width * height), mines)
        for position in mine_positions:
            self.field[position // width][position % width] = BlockType.MINE

    def get_block(self, index: int) -> BlockType:
        """
        Get the block type at the given index.

        Args:
            index: The index of the block (0 to width*height-1).

        Returns:
            The block type.
        """
        return self.field[index // self.width][index % self.width]

    def reveal_block(self, index: int) -> BlockType:
        """
        Reveal the block at the given index.

        Args:
            index: The index of the block (0 to width*height-1).

        Returns:
            The block type.
        """
        block = self.field[index // self.width][index % self.width]
        try:
            return block
        finally:
            if block == BlockType.MINE:
                self.field[index // self.width][index % self.width] = (
                    BlockType.MINE_SHOWN
                )
            else:
                self.field[index // self.width][index % self.width] = (
                    BlockType.EMPTY_SHOWN
                )

    def reveal_all_mines(self) -> None:
        for row in range(self.height):
            for col in range(self.width):
                if self.field[row][col] == BlockType.MINE:
                    self.field[row][col] = BlockType.MINE_SHOWN

    def total_cells(self) -> int:
        return self.width * self.height

    def safe_cells(self) -> int:
        return self.total_cells() - self.mines


Base = declarative_base()


class GameResult(StrEnum):
    WIN = "win"
    LOSE = "lose"
    CASHOUT = "cashout"
    TIMEOUT = "timeout"


class MinesGame(Base):
    __tablename__ = "mines_games"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False)
    bet_amount = Column(Integer, nullable=False)
    mines = Column(Integer, nullable=False)
    revealed_count = Column(Integer, nullable=False)
    result = Column(String, nullable=False)
    winnings = Column(Integer, nullable=False)
    timestamp = Column(Integer, nullable=False)
