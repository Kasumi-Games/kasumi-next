from typing import Optional
from pydantic import BaseModel


class Config(BaseModel):
    bert_vits_api_url: Optional[str] = "http://127.0.0.1:4371"
