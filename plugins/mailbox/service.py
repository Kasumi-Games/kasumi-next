"""
邮件服务模块 - 处理邮件的创建、读取、领取等操作 (优化版本)
使用新的规范化数据库设计，消除数据重复
采用 SQLAlchemy 关系查询，更优雅简洁
"""

import time
import datetime
from typing import List
from typing import Optional

from sqlalchemy import and_
from nonebot.log import logger

from utils.clock import to_bot_time

from .models import Mail
from .models import ClaimTotal
from .models import ClaimedMail
from .models import ServiceMail
from .models import ClaimOutcome
from .models import MailRecipient
from .models import MailAttachment
from .models import ServiceMailAttachment
from .database import get_session
from ..inventory.models import ItemAmount
from ..inventory.service import grant_many


class MailService:
    """邮件服务类 - 优化版本"""

    def send_mail(
        self,
        recipient_id: str,
        title: str,
        content: str,
        star_kakeras: int = 0,
        star_stickers: int = 0,
        attachments: Optional[list[ItemAmount]] = None,
        expire_days: int = 7,
        sender_id: str = "system",
    ) -> int:
        """
        发送邮件给指定用户

        Args:
            recipient_id: 接收者用户ID
            title: 邮件标题
            content: 邮件内容
            star_kakeras: Pt奖励
            star_stickers: 星星贴纸奖励
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
                star_stickers=star_stickers,
                expire_days=expire_days,
                sender_id=sender_id,
                is_broadcast=False,
            )
            session.add(mail)
            session.flush()  # 获取 mail.id

            for attachment in _normalize_attachments(
                star_kakeras, star_stickers, attachments
            ):
                session.add(
                    MailAttachment(
                        mail_id=mail.id,
                        item_id=attachment.item_id,
                        quantity=attachment.quantity,
                        scope_type=attachment.scope_type or "",
                        scope_id=attachment.scope_id or "",
                    )
                )

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
            logger.error("发送邮件时发生错误: {}", e)
            raise
        finally:
            session.close()

    def send_broadcast_mail(
        self,
        title: str,
        content: str,
        star_kakeras: int = 0,
        star_stickers: int = 0,
        attachments: Optional[list[ItemAmount]] = None,
        expire_days: int = 7,
        sender_id: str = "system",
    ) -> int:
        """
        发送广播邮件给所有用户
        注意: 这里不预先创建所有用户的记录，而是在用户查看邮箱时动态创建

        Args:
            title: 邮件标题
            content: 邮件内容
            star_kakeras: Pt奖励
            star_stickers: 星星贴纸奖励
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
                star_stickers=star_stickers,
                expire_days=expire_days,
                sender_id=sender_id,
                is_broadcast=True,  # 标记为广播邮件
            )
            session.add(mail)
            session.flush()

            for attachment in _normalize_attachments(
                star_kakeras, star_stickers, attachments
            ):
                session.add(
                    MailAttachment(
                        mail_id=mail.id,
                        item_id=attachment.item_id,
                        quantity=attachment.quantity,
                        scope_type=attachment.scope_type or "",
                        scope_id=attachment.scope_id or "",
                    )
                )

            session.commit()

            mail_id = mail.id
            logger.info(f"广播邮件已创建，邮件ID: {mail_id}")
            return mail_id

        except Exception as e:
            session.rollback()
            logger.error("创建广播邮件时发生错误: {}", e)
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
                mail_list.append(_to_service_mail(mail, recipient, expire_time))

            mail_list.sort(key=lambda x: x.created_at, reverse=True)

            return mail_list

        except Exception as e:
            session.rollback()
            logger.error("获取用户邮件时发生错误: {}", e)
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
            return _to_service_mail(mail, recipient, expire_time)

        except Exception as e:
            session.rollback()
            logger.error("读取邮件时发生错误: {}", e)
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
            logger.error("清理过期邮件时发生错误: {}", e)
            raise
        finally:
            session.close()


def claim_all_mails(mail_service: "MailService", user_id: str) -> ClaimOutcome:
    """领取所有带附件的未读邮件

    只处理带附件的未读邮件。无附件的通知保持未读，因为 ``is_read``
    是系统里唯一的"玩家确实看过这条公告"的记录，批量领取不应该消费它。

    每封邮件都使用与单封领取完全相同的幂等键 ``mail:<id>``，
    否则已经单独领取过的邮件会被重复发放。

    Args:
        mail_service: 邮件服务实例
        user_id: 用户ID

    Returns:
        ClaimOutcome: 领取结果，含每封邮件的明细与物品汇总
    """

    mails = mail_service.get_user_mails(user_id)
    claimed: list[ClaimedMail] = []
    granted_totals: dict[str, int] = {}
    owned_totals: dict[str, int] = {}
    remaining_notices = 0

    for mail in mails:
        if mail.is_read:
            continue
        if not mail.attachments:
            remaining_notices += 1
            continue

        results = grant_many(
            user_id,
            [
                ItemAmount(
                    attachment.item_id,
                    attachment.quantity,
                    attachment.scope_type or None,
                    attachment.scope_id or None,
                )
                for attachment in mail.attachments
            ],
            reason=f"mail_reward_{mail.id}",
            source_type="mail",
            source_id=str(mail.id),
            idempotency_key=f"mail:{mail.id}",
        )
        mail_service.read_mail(user_id, mail.id)
        claimed.append(ClaimedMail(mail=mail, results=tuple(results)))

        for result in results:
            if result.granted > 0:
                granted_totals[result.item_id] = (
                    granted_totals.get(result.item_id, 0) + result.granted
                )
            else:
                owned_totals[result.item_id] = (
                    owned_totals.get(result.item_id, 0) + result.quantity
                )

    totals = [
        ClaimTotal(item_id=item_id, granted=granted)
        for item_id, granted in granted_totals.items()
    ]
    totals.extend(
        ClaimTotal(item_id=item_id, already_owned=quantity)
        for item_id, quantity in owned_totals.items()
        if item_id not in granted_totals
    )
    totals.sort(key=lambda total: (total.granted, total.already_owned), reverse=True)

    return ClaimOutcome(
        claimed=tuple(claimed),
        totals=tuple(totals),
        remaining_notices=remaining_notices,
        total_mails=len(mails),
    )


def _normalize_attachments(
    star_kakeras: int = 0,
    star_stickers: int = 0,
    attachments: Optional[list[ItemAmount]] = None,
) -> list[ItemAmount]:
    normalized = list(attachments or [])
    if star_kakeras > 0:
        normalized.append(ItemAmount("season_point", star_kakeras))
    if star_stickers > 0:
        normalized.append(ItemAmount("star_sticker", star_stickers))
    return normalized


def _to_service_mail(
    mail: Mail, recipient: MailRecipient, expire_time: int
) -> ServiceMail:
    attachments = [
        ServiceMailAttachment(
            item_id=attachment.item_id,
            quantity=attachment.quantity,
            scope_type=attachment.scope_type,
            scope_id=attachment.scope_id,
        )
        for attachment in mail.attachments
    ]
    if not attachments:
        attachments = [
            ServiceMailAttachment(
                item_id=attachment.item_id, quantity=attachment.quantity
            )
            for attachment in _normalize_attachments(
                mail.star_kakeras,
                mail.star_stickers,
                attachments=None,
            )
        ]

    return ServiceMail(
        id=mail.id,
        title=mail.title,
        content=mail.content,
        star_kakeras=mail.star_kakeras,
        star_stickers=mail.star_stickers,
        attachments=attachments,
        sender_id=mail.sender_id,
        created_at=to_bot_time(mail.created_at),
        expire_time=to_bot_time(expire_time),
        is_broadcast=mail.is_broadcast,
        is_read=recipient.is_read,
        read_at=to_bot_time(recipient.read_at)
        if recipient.read_at
        else None,
    )
