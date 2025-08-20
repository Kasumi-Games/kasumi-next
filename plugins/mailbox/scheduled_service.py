"""
定时邮件服务 - 处理定时邮件的调度和发送
"""

import time
from sqlalchemy import and_
from nonebot.log import logger
from typing import List, Optional

from .service import MailService
from .database import get_session
from .models import ScheduledMail


class ScheduledMailService:
    """定时邮件服务类"""

    def __init__(self):
        self.mail_service = MailService()

    def create_scheduled_mail(
        self,
        recipients: str,  # "all" 或 "user1,user2,user3"
        title: str,
        content: str,
        scheduled_time: int,  # Unix时间戳
        star_kakeras: int = 0,
        expire_days: int = 7,
        created_by: str = "system",
        name: str = None,  # 如果不提供则自动生成
    ) -> int:
        """
        创建定时邮件

        Args:
            recipients: 接收者，"all"表示所有用户，否则为逗号分隔的用户ID
            title: 邮件标题
            content: 邮件内容
            scheduled_time: 预定发送时间(Unix时间戳)
            star_kakeras: 星之碎片奖励
            expire_days: 邮件过期天数
            created_by: 创建者用户ID
            name: 定时邮件名称/标识，如果不提供则自动生成

        Returns:
            int: 定时邮件ID
        """
        session = get_session()

        # 如果没有提供名称，自动生成唯一名称
        if name is None:
            import random
            import string

            timestamp = int(time.time())
            suffix = "".join(
                random.choices(string.ascii_lowercase + string.digits, k=6)
            )
            name = f"mail_{timestamp}_{suffix}"

        # 检查名称是否已存在
        existing = (
            session.query(ScheduledMail).filter(ScheduledMail.name == name).first()
        )
        if existing:
            raise ValueError(f"定时邮件名称 '{name}' 已存在")

        scheduled_mail = ScheduledMail(
            name=name,
            recipients=recipients,
            title=title,
            content=content,
            star_kakeras=star_kakeras,
            expire_days=expire_days,
            scheduled_time=scheduled_time,
            created_at=int(time.time()),
            created_by=created_by,
        )

        session.add(scheduled_mail)
        session.commit()

        logger.info(
            f"已创建定时邮件: {name} (预定时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(scheduled_time))})"
        )
        return scheduled_mail.id

    def get_scheduled_mails(self, include_sent: bool = False) -> List[ScheduledMail]:
        """
        获取定时邮件列表

        Args:
            include_sent: 是否包含已发送的邮件

        Returns:
            List[ScheduledMail]: 定时邮件列表
        """
        session = get_session()

        query = session.query(ScheduledMail)
        if not include_sent:
            query = query.filter(ScheduledMail.is_sent == False)  # noqa: E712

        return query.order_by(ScheduledMail.scheduled_time.asc()).all()

    def get_scheduled_mail_by_name(self, name: str) -> Optional[ScheduledMail]:
        """
        根据名称获取定时邮件

        Args:
            name: 邮件名称

        Returns:
            Optional[ScheduledMail]: 定时邮件对象
        """
        session = get_session()
        return session.query(ScheduledMail).filter(ScheduledMail.name == name).first()

    def update_scheduled_mail(
        self,
        name: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        scheduled_time: Optional[int] = None,
        star_kakeras: Optional[int] = None,
        expire_days: Optional[int] = None,
        recipients: Optional[str] = None,
    ) -> bool:
        """
        更新定时邮件

        Args:
            name: 邮件名称
            title: 新标题
            content: 新内容
            scheduled_time: 新预定时间
            star_kakeras: 新奖励数量
            expire_days: 新过期天数
            recipients: 新接收者

        Returns:
            bool: 是否更新成功
        """
        session = get_session()
        scheduled_mail = (
            session.query(ScheduledMail).filter(ScheduledMail.name == name).first()
        )

        if not scheduled_mail:
            return False

        if scheduled_mail.is_sent:
            logger.warning(f"定时邮件 '{name}' 已发送，无法修改")
            return False

        # 更新字段
        if title is not None:
            scheduled_mail.title = title
        if content is not None:
            scheduled_mail.content = content
        if scheduled_time is not None:
            scheduled_mail.scheduled_time = scheduled_time
        if star_kakeras is not None:
            scheduled_mail.star_kakeras = star_kakeras
        if expire_days is not None:
            scheduled_mail.expire_days = expire_days
        if recipients is not None:
            scheduled_mail.recipients = recipients

        session.commit()
        logger.info(f"已更新定时邮件: {name}")
        return True

    def delete_scheduled_mail(self, name: str) -> bool:
        """
        删除定时邮件

        Args:
            name: 邮件名称

        Returns:
            bool: 是否删除成功
        """
        session = get_session()
        scheduled_mail = (
            session.query(ScheduledMail).filter(ScheduledMail.name == name).first()
        )

        if not scheduled_mail:
            return False

        if scheduled_mail.is_sent:
            logger.warning(f"定时邮件 '{name}' 已发送，但仍可删除记录")

        session.delete(scheduled_mail)
        session.commit()
        logger.info(f"已删除定时邮件: {name}")
        return True

    def process_due_mails(self) -> int:
        """
        处理到期的定时邮件

        Returns:
            int: 处理的邮件数量
        """
        session = get_session()
        current_time = int(time.time())

        # 查找到期且未发送的邮件
        due_mails = (
            session.query(ScheduledMail)
            .filter(
                and_(
                    ScheduledMail.scheduled_time <= current_time,
                    ScheduledMail.is_sent == False,  # noqa: E712
                )
            )
            .all()
        )

        processed_count = 0

        for scheduled_mail in due_mails:
            name = scheduled_mail.name
            try:
                # 解析接收者
                if scheduled_mail.recipients.lower() == "all":
                    # 群发邮件
                    self.mail_service.send_broadcast_mail(
                        title=scheduled_mail.title,
                        content=scheduled_mail.content,
                        star_kakeras=scheduled_mail.star_kakeras,
                        expire_days=scheduled_mail.expire_days,
                        sender_id=scheduled_mail.created_by,
                    )
                else:
                    # 发送给指定用户
                    recipient_ids = [
                        uid.strip() for uid in scheduled_mail.recipients.split(",")
                    ]
                    for recipient_id in recipient_ids:
                        if recipient_id:  # 确保不是空字符串
                            self.mail_service.send_mail(
                                recipient_id=recipient_id,
                                title=scheduled_mail.title,
                                content=scheduled_mail.content,
                                star_kakeras=scheduled_mail.star_kakeras,
                                expire_days=scheduled_mail.expire_days,
                                sender_id=scheduled_mail.created_by,
                            )

                # 标记为已发送
                scheduled_mail.is_sent = True
                scheduled_mail.sent_at = int(time.time())

                session.merge(scheduled_mail)
                session.commit()

                processed_count += 1
                logger.info(f"已发送定时邮件: {name}")

            except Exception as e:
                logger.exception(
                    f"发送定时邮件 '{name}' 时发生错误: {e}",
                    exc_info=True,
                )
                continue

        return processed_count

    def get_pending_count(self) -> int:
        """
        获取待发送定时邮件数量

        Returns:
            int: 待发送邮件数量
        """
        session = get_session()
        return (
            session.query(ScheduledMail)
            .filter(ScheduledMail.is_sent == False)  # noqa: E712
            .count()
        )
