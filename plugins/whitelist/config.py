from typing import List
from typing import Optional

from pydantic import BaseModel


class Config(BaseModel):
    whitelist: Optional[List[str]] = None
