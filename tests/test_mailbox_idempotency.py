"""Mailbox delivery idempotency used by cross-database outboxes."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from plugins.mailbox import database
from plugins.mailbox.models import Base
from plugins.mailbox.models import Mail
from plugins.mailbox.service import MailService
from plugins.mailbox.database import migrate_mailbox_schema


def test_external_key_returns_the_existing_mail(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    monkeypatch.setattr(database, "session", session)

    service = MailService()
    first = service.send_mail(
        "u1",
        "赛季奖励",
        "第一次发送",
        external_key="season_reward:1:u1",
    )
    second = service.send_mail(
        "u1",
        "赛季奖励",
        "重试不应新建",
        external_key="season_reward:1:u1",
    )

    assert first == second
    assert session.query(Mail).count() == 1


def test_schema_migration_adds_external_key_to_an_existing_mailbox():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE mails (id INTEGER PRIMARY KEY, title VARCHAR NOT NULL)"
        )

    migrate_mailbox_schema(engine)

    with engine.connect() as connection:
        columns = {
            row[1]
            for row in connection.exec_driver_sql(
                "PRAGMA table_info(mails)"
            ).fetchall()
        }
        indexes = {
            row[1]
            for row in connection.exec_driver_sql(
                "PRAGMA index_list(mails)"
            ).fetchall()
        }
    assert "external_key" in columns
    assert "uq_mails_external_key" in indexes
