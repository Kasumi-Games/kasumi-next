from typing import Optional
from pydantic import BaseModel


class Config(BaseModel):
    bestdori_proxy: Optional[str] = None
    enable_guess_chart: Optional[bool] = True
