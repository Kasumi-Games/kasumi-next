from pydantic import BaseModel
from typing import List, Optional


class Config(BaseModel):
    whitelist: Optional[List[str]] = None
