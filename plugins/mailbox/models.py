"""
邮箱系统的数据模型 - 优化版本，消除数据重复
"""

import time
import datetime
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Text, Boolean, ForeignKey


Base = declarative_base()


class Mail(Base):
    __tablename__ = "mails"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    star_kakeras: Mapped[int] = mapped_column(default=0)
    expire_days: Mapped[int] = mapped_column(default=7)
    created_at: Mapped[int] = mapped_column(
        nullable=False, default=lambda: int(time.time())
    )
    sender_id: Mapped[str] = mapped_column(String, nullable=False)
    is_broadcast: Mapped[bool] = mapped_column(default=False)

    recipients: Mapped[list["MailRecipient"]] = relationship(
        back_populates="mail", cascade="all, delete-orphan"
    )


class MailRecipient(Base):
    __tablename__ = "mail_recipients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    mail_id: Mapped[int] = mapped_column(
        ForeignKey("mails.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(nullable=False)
    is_read: Mapped[bool] = mapped_column(default=False)  # 读取时自动获得奖励
    read_at: Mapped[Optional[int]] = mapped_column(nullable=True)

    mail: Mapped["Mail"] = relationship(back_populates="recipients")


class ScheduledMail(Base):
    """定时邮件表模型"""

    __tablename__ = "scheduled_mails"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String, nullable=False, unique=True
    )  # 定时邮件名称/标识
    recipients: Mapped[str] = mapped_column(
        String, nullable=False
    )  # 接收者："all" 或 "user1,user2,user3"
    title: Mapped[str] = mapped_column(String, nullable=False)  # 邮件标题
    content: Mapped[str] = mapped_column(Text, nullable=False)  # 邮件内容
    star_kakeras: Mapped[int] = mapped_column(Integer, default=0)  # 星之碎片奖励
    expire_days: Mapped[int] = mapped_column(Integer, default=7)  # 过期天数
    scheduled_time: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # 预定发送时间 (Unix时间戳)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)  # 创建时间
    created_by: Mapped[str] = mapped_column(String, nullable=False)  # 创建者用户ID
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否已发送
    sent_at: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # 实际发送时间

    def __repr__(self):
        return f"<ScheduledMail(id={self.id}, name={self.name}, scheduled_time={self.scheduled_time})>"


class ServiceMail(BaseModel):
    """服务端邮件模型"""

    id: int
    title: str
    content: str
    star_kakeras: int
    sender_id: str
    created_at: datetime.datetime
    expire_time: datetime.datetime
    is_broadcast: bool
    is_read: bool
    read_at: Optional[datetime.datetime]
