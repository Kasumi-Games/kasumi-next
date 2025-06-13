from typing import Optional
from pydantic import BaseModel


class Config(BaseModel):
    enable_bang_avatar: Optional[bool] = True
    qq_bot_app_id: int
    wife_cost: Optional[int] = 2