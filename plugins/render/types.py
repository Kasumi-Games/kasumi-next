from typing import Literal
from pathlib import Path

from PIL import Image

ImageSource = Image.Image | str | Path
TextAlign = Literal["left", "center", "right"]
Overflow = Literal["clip", "ellipsis", "shrink"]
ImageFit = Literal["contain", "cover", "stretch"]
