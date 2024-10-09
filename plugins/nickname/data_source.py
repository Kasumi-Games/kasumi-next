from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class Nickname(Base):
    __tablename__ = "nicknames"

    user_id = Column(String, primary_key=True)
    nickname = Column(String)
