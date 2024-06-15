from typing import Optional
from pydantic import BaseModel


class Config(BaseModel):
    enable_cck: Optional[bool] = True
