from dataclasses import dataclass
from enum import IntEnum, StrEnum
import random


class Band(IntEnum):
    poppin_party = 1
    afterglow = 2
    hello_happy_world = 3
    pastel_palettes = 4
    roselia = 5
    raise_a_suilen = 18
    morfonica = 21
    mygo = 45


class Star(IntEnum):
    one = 1
    two = 2
    three = 3
    four = 4
    five = 5


class Attribute(StrEnum):
    cool = "cool"
    pure = "pure"
    powerful = "powerful"
    happy = "happy"


@dataclass
class WifeData:
    # data part
    user_id: str
    lp_id: str

    # render data part
    band: int = None
    star: int = None
    attribute: str = None

    def generate_wife_data(self):
        self.band = random.choice(list(Band))
        self.star = random.choice(list(Star))
        self.attribute = random.choice(list(Attribute))
        return self
