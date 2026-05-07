"""Daily task ORM model."""

from pydantic import BaseModel
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Boolean, UniqueConstraint

Base = declarative_base()


class DailyTask(Base):
    __tablename__ = "daily_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False)
    date = Column(String, nullable=False)
    task_id = Column(String, nullable=False)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(Integer)

    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_user_date"),)


class DailyTaskConfig(BaseModel):
    id: str
    name: str
    description: str
    reward: int
    type: str
    conditions: list[dict]
