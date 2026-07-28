"""
定时邮件服务 - 处理定时邮件的调度和发送
"""

import time
from typing import List
from typing import Optional

from sqlalchemy import and_
from nonebot.log import logger

from utils.clock import format_ts

from .models import ScheduledMail
from .models import ScheduledMailAttachment
from .service import MailService
from .service import _normalize_attachments
from .database import get_session
from ..inventory.models import ItemAmount


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
        star_stickers: int = 0,
        attachments: Optional[list[ItemAmount]] = None,
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
            star_kakeras: Pt奖励
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
            star_stickers=star_stickers,
            expire_days=expire_days,
            scheduled_time=scheduled_time,
            created_at=int(time.time()),
            created_by=created_by,
        )

        session.add(scheduled_mail)
        session.flush()

        for attachment in _normalize_attachments(
            star_kakeras, star_stickers, attachments
        ):
            session.add(
                ScheduledMailAttachment(
                    scheduled_mail_id=scheduled_mail.id,
                    item_id=attachment.item_id,
                    quantity=attachment.quantity,
                    scope_type=attachment.scope_type or "",
                    scope_id=attachment.scope_id or "",
                )
            )

        session.commit()

        logger.info(
            f"已创建定时邮件: {name} (预定时间: {format_ts(scheduled_time, '%Y-%m-%d %H:%M:%S')})"
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
        star_stickers: Optional[int] = None,
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

        # 更新字段。星星奖励要同时改列和附件行：发送走的是附件行
        # （_scheduled_attachments），只改列的话编辑会被静默忽略。
        if title is not None:
            scheduled_mail.title = title
        if content is not None:
            scheduled_mail.content = content
        if scheduled_time is not None:
            scheduled_mail.scheduled_time = scheduled_time
        if star_kakeras is not None:
            scheduled_mail.star_kakeras = star_kakeras
            _sync_star_attachment(
                session, scheduled_mail, "season_point", star_kakeras
            )
        if star_stickers is not None:
            scheduled_mail.star_stickers = star_stickers
            _sync_star_attachment(
                session, scheduled_mail, "star_sticker", star_stickers
            )
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

    def add_attachment(self, name: str, attachment: ItemAmount) -> bool:
        session = get_session()
        scheduled_mail = (
            session.query(ScheduledMail).filter(ScheduledMail.name == name).first()
        )
        if not scheduled_mail or scheduled_mail.is_sent:
            return False

        session.add(
            ScheduledMailAttachment(
                scheduled_mail_id=scheduled_mail.id,
                item_id=attachment.item_id,
                quantity=attachment.quantity,
                scope_type=attachment.scope_type or "",
                scope_id=attachment.scope_id or "",
            )
        )
        session.commit()
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

        # 发送前先把所有字段快照成普通值：send_mail/send_broadcast_mail
        # 会 commit 并 close 同一个共享 session，这些 ORM 实例随之过期又
        # 脱管（expired + detached），之后再碰属性就抛 DetachedInstanceError。
        # 具体症状：多个指定接收者的定时邮件，第一位每个调度周期收到一封
        # 新邮件，第二位永远收不到，is_sent 也永远置不上。
        snapshots = [
            (
                scheduled_mail.id,
                scheduled_mail.name,
                scheduled_mail.recipients,
                scheduled_mail.title,
                scheduled_mail.content,
                scheduled_mail.expire_days,
                scheduled_mail.created_by,
                # 奖励只通过 attachments 传递一次：这里已经包含 -k/-s 的
                # 星星奖励，再传 star_kakeras/star_stickers 会被 send_* 的
                # normalize 再次追加，这正是线上「星星贴纸 x2」重复附件
                # 的来源。
                _scheduled_attachments(scheduled_mail),
            )
            for scheduled_mail in due_mails
        ]

        processed_count = 0

        for (
            mail_id,
            name,
            recipients,
            title,
            content,
            expire_days,
            sender_id,
            attachments,
        ) in snapshots:
            try:
                if recipients.lower() == "all":
                    # 群发邮件
                    self.mail_service.send_broadcast_mail(
                        title=title,
                        content=content,
                        attachments=attachments,
                        expire_days=expire_days,
                        sender_id=sender_id,
                        external_key=f"scheduled:{mail_id}:broadcast",
                    )
                else:
                    # 发送给指定用户
                    recipient_ids = [uid.strip() for uid in recipients.split(",")]
                    for recipient_id in recipient_ids:
                        if recipient_id:  # 确保不是空字符串
                            self.mail_service.send_mail(
                                recipient_id=recipient_id,
                                title=title,
                                content=content,
                                attachments=attachments,
                                expire_days=expire_days,
                                sender_id=sender_id,
                                external_key=(
                                    f"scheduled:{mail_id}:recipient:{recipient_id}"
                                ),
                            )

                # 标记为已发送。按主键重新取行，而不是 merge 快照前的
                # 实例：发送关闭过 session，旧实例已脱管；若邮件在发送
                # 期间被删除，merge 还会把它重新插回去。
                session = get_session()
                row = session.get(ScheduledMail, mail_id)
                if row is not None:
                    row.is_sent = True
                    row.sent_at = int(time.time())
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


def _sync_star_attachment(
    session, scheduled_mail: ScheduledMail, item_id: str, quantity: int
) -> None:
    """Make the unscoped attachment row for ``item_id`` say ``quantity``.

    Creation folds ``-k``/``-s`` into attachment rows, so an edit of those
    fields must rewrite the matching row (create it when missing, delete it at
    zero) — the row is what actually gets sent.
    """

    row = next(
        (
            attachment
            for attachment in scheduled_mail.attachments
            if attachment.item_id == item_id
            and not attachment.scope_type
            and not attachment.scope_id
        ),
        None,
    )
    if quantity > 0:
        if row is None:
            session.add(
                ScheduledMailAttachment(
                    scheduled_mail_id=scheduled_mail.id,
                    item_id=item_id,
                    quantity=quantity,
                    scope_type="",
                    scope_id="",
                )
            )
        else:
            row.quantity = quantity
    elif row is not None:
        session.delete(row)


def _scheduled_attachments(scheduled_mail: ScheduledMail) -> list[ItemAmount]:
    """The full reward list of a scheduled mail, each item exactly once.

    The attachment rows are the source of truth — creation normalizes the
    ``-k``/``-s`` shortcuts into rows, merged per item. The star columns are
    only the fallback for legacy rows created before attachments existed.
    ``process_due_mails`` must send THIS list alone and never re-pass the star
    columns, which is exactly the double-append that shipped duplicate
    ``MailAttachment`` rows to production.
    """

    if scheduled_mail.attachments:
        return [
            ItemAmount(
                item_id=attachment.item_id,
                quantity=attachment.quantity,
                scope_type=attachment.scope_type or None,
                scope_id=attachment.scope_id or None,
            )
            for attachment in scheduled_mail.attachments
        ]
    return _normalize_attachments(
        scheduled_mail.star_kakeras,
        scheduled_mail.star_stickers,
        attachments=None,
    )
