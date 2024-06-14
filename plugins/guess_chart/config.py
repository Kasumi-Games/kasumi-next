from typing import Optional
from pydantic import BaseModel


class Config(BaseModel):
    bestdori_proxy: Optional[str] = None
