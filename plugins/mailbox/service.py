"""
邮件服务模块 - 处理邮件的创建、读取、领取等操作 (优化版本)
使用新的规范化数据库设计，消除数据重复
采用 SQLAlchemy 关系查询，更优雅简洁
"""

import time
import datetime
from sqlalchemy import and_
from nonebot.log import logger
from typing import List, Optional

from .database import get_session
from .models import Mail, MailRecipient, ServiceMail


class MailService:
    """邮件服务类 - 优化版本"""

    def send_mail(
        self,
        recipient_id: str,
        title: str,
        content: str,
        star_kakeras: int = 0,
        expire_days: int = 7,
        sender_id: str = "system",
    ) -> int:
        """
        发送邮件给指定用户

        Args:
            recipient_id: 接收者用户ID
            title: 邮件标题
            content: 邮件内容
            star_kakeras: 星之碎片奖励
            expire_days: 过期天数
            sender_id: 发送者用户ID

        Returns:
            int: 邮件ID
        """
        session = get_session()

        try:
            # 创建邮件内容
            mail = Mail(
                title=title,
                content=content,
                star_kakeras=star_kakeras,
                expire_days=expire_days,
                sender_id=sender_id,
                is_broadcast=False,
            )
            session.add(mail)
            session.flush()  # 获取 mail.id

            # 创建接收者记录
            recipient = MailRecipient(
                mail_id=mail.id,
                user_id=recipient_id,
            )
            session.add(recipient)
            session.commit()

            mail_id = mail.id
            logger.info(f"邮件已发送给用户 {recipient_id}，邮件ID: {mail_id}")
            return mail_id

        except Exception as e:
            session.rollback()
            logger.error(f"发送邮件时发生错误: {e}")
            raise
        finally:
            session.close()

    def send_broadcast_mail(
        self,
        title: str,
        content: str,
        star_kakeras: int = 0,
        expire_days: int = 7,
        sender_id: str = "system",
    ) -> int:
        """
        发送广播邮件给所有用户
        注意: 这里不预先创建所有用户的记录，而是在用户查看邮箱时动态创建

        Args:
            title: 邮件标题
            content: 邮件内容
            star_kakeras: 星之碎片奖励
            expire_days: 过期天数
            sender_id: 发送者用户ID

        Returns:
            int: 邮件ID
        """
        session = get_session()

        try:
            # 创建广播邮件内容
            mail = Mail(
                title=title,
                content=content,
                star_kakeras=star_kakeras,
                expire_days=expire_days,
                sender_id=sender_id,
                is_broadcast=True,  # 标记为广播邮件
            )
            session.add(mail)
            session.commit()

            mail_id = mail.id
            logger.info(f"广播邮件已创建，邮件ID: {mail_id}")
            return mail_id

        except Exception as e:
            session.rollback()
            logger.error(f"创建广播邮件时发生错误: {e}")
            raise
        finally:
            session.close()

    def get_user_mails(self, user_id: str) -> List[ServiceMail]:
        """
        获取用户的所有邮件（包括广播邮件）

        Args:
            user_id: 用户ID

        Returns:
            List[ServiceMail]: 邮件列表
        """
        session = get_session()

        try:
            current_time = int(time.time())

            # 获取广播邮件（用户可能还没有接收记录）
            broadcast_mails = (
                session.query(Mail)
                .filter(
                    and_(
                        Mail.is_broadcast,
                        Mail.created_at + (Mail.expire_days * 24 * 60 * 60)
                        > current_time,  # 未过期
                    )
                )
                .all()
            )

            # 为广播邮件创建用户记录（如果不存在）
            for broadcast_mail in broadcast_mails:
                existing = (
                    session.query(MailRecipient)
                    .filter(
                        and_(
                            MailRecipient.mail_id == broadcast_mail.id,
                            MailRecipient.user_id == user_id,
                        )
                    )
                    .first()
                )

                if not existing:
                    # 为用户创建广播邮件接收记录
                    recipient = MailRecipient(
                        mail_id=broadcast_mail.id,
                        user_id=user_id,
                    )
                    session.add(recipient)

            session.commit()

            # 查询用户的所有邮件接收记录
            recipients = (
                session.query(MailRecipient)
                .join(Mail, MailRecipient.mail_id == Mail.id)
                .filter(
                    and_(
                        MailRecipient.user_id == user_id,
                        Mail.created_at + (Mail.expire_days * 24 * 60 * 60)
                        > current_time,  # 未过期
                    )
                )
                .order_by(Mail.created_at.desc())
                .all()
            )

            # 转换为字典格式 - 使用关系访问邮件内容
            mail_list = []
            for recipient in recipients:
                mail = recipient.mail  # 使用关系访问邮件内容
                expire_time = mail.created_at + (mail.expire_days * 24 * 60 * 60)
                mail_dict = ServiceMail(
                    id=mail.id,
                    title=mail.title,
                    content=mail.content,
                    star_kakeras=mail.star_kakeras,
                    sender_id=mail.sender_id,
                    created_at=datetime.datetime.fromtimestamp(mail.created_at),
                    expire_time=datetime.datetime.fromtimestamp(expire_time),
                    is_broadcast=mail.is_broadcast,
                    is_read=recipient.is_read,
                    read_at=datetime.datetime.fromtimestamp(recipient.read_at)
                    if recipient.read_at
                    else None,
                )
                mail_list.append(mail_dict)

            mail_list.sort(key=lambda x: x.created_at, reverse=True)

            return mail_list

        except Exception as e:
            session.rollback()
            logger.error(f"获取用户邮件时发生错误: {e}")
            raise
        finally:
            session.close()

    def read_mail(self, user_id: str, mail_id: int) -> Optional[ServiceMail]:
        """
        读取指定邮件并标记为已读

        Args:
            user_id: 用户ID
            mail_id: 邮件ID

        Returns:
            Optional[ServiceMail]: 邮件详情，如果邮件不存在或已过期返回 None
        """
        session = get_session()

        try:
            current_time = int(time.time())

            # 查询用户的邮件接收记录
            recipient = (
                session.query(MailRecipient)
                .join(Mail, MailRecipient.mail_id == Mail.id)
                .filter(
                    and_(
                        Mail.id == mail_id,
                        MailRecipient.user_id == user_id,
                        Mail.created_at + (Mail.expire_days * 24 * 60 * 60)
                        > current_time,  # 未过期
                    )
                )
                .first()
            )

            if not recipient:
                return None

            mail = recipient.mail  # 使用关系访问邮件内容

            # 标记为已读
            if not recipient.is_read:
                recipient.is_read = True
                recipient.read_at = current_time
                session.commit()

            # 返回邮件详情
            expire_time = mail.created_at + (mail.expire_days * 24 * 60 * 60)
            return ServiceMail(
                id=mail.id,
                title=mail.title,
                content=mail.content,
                star_kakeras=mail.star_kakeras,
                sender_id=mail.sender_id,
                created_at=datetime.datetime.fromtimestamp(mail.created_at),
                expire_time=datetime.datetime.fromtimestamp(expire_time),
                is_broadcast=mail.is_broadcast,
                is_read=recipient.is_read,
                read_at=datetime.datetime.fromtimestamp(recipient.read_at)
                if recipient.read_at
                else None,
            )

        except Exception as e:
            session.rollback()
            logger.error(f"读取邮件时发生错误: {e}")
            raise
        finally:
            session.close()

    def cleanup_expired_mails(self) -> int:
        """
        清理过期邮件

        Returns:
            int: 清理的邮件数量
        """
        session = get_session()

        try:
            current_time = int(time.time())

            # 查找过期的邮件
            expired_mails = (
                session.query(Mail)
                .filter(
                    Mail.created_at + (Mail.expire_days * 24 * 60 * 60) <= current_time
                )
                .all()
            )

            expired_count = len(expired_mails)

            if expired_count > 0:
                # 删除过期邮件（级联删除接收记录）
                for mail in expired_mails:
                    session.delete(mail)

                session.commit()
                logger.info(f"已清理 {expired_count} 封过期邮件")

            return expired_count

        except Exception as e:
            session.rollback()
            logger.error(f"清理过期邮件时发生错误: {e}")
            raise
        finally:
            session.close()
