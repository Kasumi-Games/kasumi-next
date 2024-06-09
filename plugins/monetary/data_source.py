from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True)
    balance = Column(Integer)
    last_daily_time = Column(Integer) # Unix timestamp
