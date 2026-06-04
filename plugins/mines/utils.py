import random
from pathlib import Path


def get_random_kasumi() -> Path:
    files = list(
        (Path(__file__).resolve().parent / "resources" / "kasumi").glob("*.png")
    )
    return random.choice(files)


def get_random_arisa() -> Path:
    files = list(
        (Path(__file__).resolve().parent / "resources" / "arisa").glob("*.png")
    )
    return random.choice(files)
