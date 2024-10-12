from typing import Optional, List
from sqlalchemy import create_engine
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Table, ForeignKey


Base = declarative_base()

# 关联表，用于多对多关系
channel_members = Table(
    "channel_members",
    Base.metadata,
    Column("channel_id", String, ForeignKey("channels.id"), primary_key=True),
    Column("member_id", String, ForeignKey("members.id"), primary_key=True),
)


class Member(Base):
    __tablename__ = "members"

    id = Column(String, primary_key=True)
    avatar_url = Column(String, nullable=True, default=None)

    # 定义反向关系，引用channels表
    channels: List["Channel"] = relationship(
        "Channel", secondary=channel_members, back_populates="members"
    )


class Channel(Base):
    __tablename__ = "channels"

    id = Column(String, primary_key=True)

    # 使用relationship表示多个Member对象
    members: List[Member] = relationship(
        "Member", secondary=channel_members, back_populates="channels"
    )


class ChannelMemberManager:
    def __init__(self, database_url: str):
        # 设置数据库引擎和会话
        self.engine = create_engine(database_url)
        Base.metadata.create_all(self.engine)
        self.Session = scoped_session(sessionmaker(bind=self.engine))

    def add_member_to_channel(
        self, channel_id: str, member_id: str, avatar_url: Optional[str] = None
    ) -> bool:
        """添加成员到频道

        Args:
            channel_id (str): 频道ID
            member_id (str): 成员ID
            avatar_url (Optional[str], optional): 成员头像URL. Defaults to None.

        Returns:
            bool: 是否添加成功
        """
        with self.Session() as session:
            # 查询或创建频道
            channel = session.query(Channel).filter_by(id=channel_id).first()
            if not channel:
                channel = Channel(id=channel_id)
                session.add(channel)

            # 查询或创建成员
            member = session.query(Member).filter_by(id=member_id).first()
            if not member:
                member = Member(id=member_id, avatar_url=avatar_url)
                session.add(member)

            # 添加成员到频道
            channel.members.append(member)
            session.commit()
            return True

    def remove_member_from_channel(self, channel_id: str, member_id: str) -> bool:
        """从频道移除成员

        Args:
            channel_id (str): 频道ID
            member_id (str): 成员ID

        Returns:
            bool: 是否移除成功
        """
        with self.Session() as session:
            channel = session.query(Channel).filter_by(id=channel_id).first()
            member = session.query(Member).filter_by(id=member_id).first()
            if channel and member:
                if member in channel.members:
                    channel.members.remove(member)
                    session.commit()
                    return True
            return False

    def get_channel_members(self, channel_id: str) -> List[Member]:
        """获取频道成员

        Args:
            channel_id (str): 频道ID

        Returns:
            List[Member]: 成员列表
        """
        with self.Session() as session:
            channel = session.query(Channel).filter_by(id=channel_id).first()
            if channel:
                return channel.members
            return []

    def get_member_channels(self, member_id: str) -> List[Channel]:
        """获取成员频道

        Args:
            member_id (str): 成员ID

        Returns:
            List[Channel]: 频道列表
        """
        with self.Session() as session:
            member = session.query(Member).filter_by(id=member_id).first()
            if member:
                return member.channels
            return []

    def delete_channel(self, channel_id: str) -> bool:
        """删除频道

        Args:
            channel_id (str): 频道ID

        Returns:
            bool: 是否删除成功
        """
        with self.Session() as session:
            channel = session.query(Channel).filter_by(id=channel_id).first()
            if channel:
                session.delete(channel)
                session.commit()
                return True
            return False

    def delete_member(self, member_id: str) -> bool:
        """删除成员

        Args:
            member_id (str): 成员ID

        Returns:
            bool: 是否删除成功
        """
        with self.Session() as session:
            member = session.query(Member).filter_by(id=member_id).first()
            if member:
                session.delete(member)
                session.commit()
                return True
            return False
