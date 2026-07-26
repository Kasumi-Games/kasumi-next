"""
邮箱系统的数据模型 - 优化版本，消除数据重复
"""

import time
import datetime
from typing import Optional
from dataclasses import dataclass

from pydantic import Field
from pydantic import BaseModel
from sqlalchemy import Text
from sqlalchemy import String
from sqlalchemy import Boolean
from sqlalchemy import Integer
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import relationship
from sqlalchemy.orm import mapped_column
from sqlalchemy.ext.declarative import declarative_base

from ..inventory.models import GrantResult

Base = declarative_base()


class Mail(Base):
    __tablename__ = "mails"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    star_kakeras: Mapped[int] = mapped_column(default=0)
    star_stickers: Mapped[int] = mapped_column(Integer, default=0)
    expire_days: Mapped[int] = mapped_column(default=7)
    created_at: Mapped[int] = mapped_column(
        nullable=False, default=lambda: int(time.time())
    )
    sender_id: Mapped[str] = mapped_column(String, nullable=False)
    is_broadcast: Mapped[bool] = mapped_column(default=False)

    recipients: Mapped[list["MailRecipient"]] = relationship(
        back_populates="mail", cascade="all, delete-orphan"
    )
    attachments: Mapped[list["MailAttachment"]] = relationship(
        back_populates="mail", cascade="all, delete-orphan"
    )


class MailAttachment(Base):
    __tablename__ = "mail_attachments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    mail_id: Mapped[int] = mapped_column(
        ForeignKey("mails.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    scope_type: Mapped[str] = mapped_column(String, default="", nullable=False)
    scope_id: Mapped[str] = mapped_column(String, default="", nullable=False)

    mail: Mapped["Mail"] = relationship(back_populates="attachments")


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
    star_kakeras: Mapped[int] = mapped_column(Integer, default=0)  # Pt奖励
    star_stickers: Mapped[int] = mapped_column(Integer, default=0)  # 星星贴纸奖励
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

    attachments: Mapped[list["ScheduledMailAttachment"]] = relationship(
        back_populates="scheduled_mail", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<ScheduledMail(id={self.id}, name={self.name}, scheduled_time={self.scheduled_time})>"


class ScheduledMailAttachment(Base):
    __tablename__ = "scheduled_mail_attachments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scheduled_mail_id: Mapped[int] = mapped_column(
        ForeignKey("scheduled_mails.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    scope_type: Mapped[str] = mapped_column(String, default="", nullable=False)
    scope_id: Mapped[str] = mapped_column(String, default="", nullable=False)

    scheduled_mail: Mapped["ScheduledMail"] = relationship(back_populates="attachments")


class ServiceMailAttachment(BaseModel):
    item_id: str
    quantity: int
    scope_type: str = ""
    scope_id: str = ""


class ServiceMail(BaseModel):
    """服务端邮件模型"""

    id: int
    title: str
    content: str
    star_kakeras: int
    star_stickers: int = 0
    attachments: list[ServiceMailAttachment] = Field(default_factory=list)
    sender_id: str
    created_at: datetime.datetime
    expire_time: datetime.datetime
    is_broadcast: bool
    is_read: bool
    read_at: Optional[datetime.datetime]


@dataclass(frozen=True)
class ClaimedMail:
    """一封在批量领取中被领取的邮件及其发放结果

    Attributes:
        mail: 邮件本体
        results: ``grant_many`` 的返回值，与 ``mail.attachments`` 一一对应
    """

    mail: ServiceMail
    results: tuple[GrantResult, ...] = ()


@dataclass(frozen=True)
class ClaimTotal:
    """一种物品在整次批量领取中的汇总

    Attributes:
        item_id: 物品 ID
        granted: 本次实际发放数量
        already_owned: 因幂等或已拥有而跳过的数量
    """

    item_id: str
    granted: int = 0
    already_owned: int = 0


@dataclass(frozen=True)
class ClaimOutcome:
    """一次 ``/邮件 领取`` 的完整结果

    Attributes:
        claimed: 被领取的邮件，按邮箱顺序排列
        totals: 按发放数量降序排列的物品汇总
        remaining_notices: 仍未读的无附件通知数量
        total_mails: 领取前邮箱中的邮件总数
    """

    claimed: tuple[ClaimedMail, ...] = ()
    totals: tuple[ClaimTotal, ...] = ()
    remaining_notices: int = 0
    total_mails: int = 0
