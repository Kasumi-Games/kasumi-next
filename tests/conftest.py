from __future__ import annotations

import os
import sys
import tempfile
import importlib
from typing import Any
from pathlib import Path
from datetime import datetime
from collections.abc import Callable

import pytest
import nonebot
from nonebug import NONEBOT_INIT_KWARGS
from nonebug import NONEBOT_START_LIFESPAN
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from nonebot.adapters.satori import Adapter as SatoriAdapter
from nonebot.adapters.satori import Message
from nonebot.adapters.satori.event import User
from nonebot.adapters.satori.event import Guild
from nonebot.adapters.satori.event import Login
from nonebot.adapters.satori.event import Member
from nonebot.adapters.satori.event import Channel
from nonebot.adapters.satori.event import MessageCreatedEvent
from nonebot.adapters.satori.models import LoginStatus
from nonebot.adapters.satori.models import MessageObject

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_LOCALSTORE_ROOT = Path(tempfile.mkdtemp(prefix="kasumi-next-tests-"))
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("COMMAND_START", '["/"]')
os.environ.setdefault("SUPERUSERS", '["admin"]')
os.environ.setdefault("LOCALSTORE_CACHE_DIR", str(_LOCALSTORE_ROOT / "cache"))
os.environ.setdefault("LOCALSTORE_CONFIG_DIR", str(_LOCALSTORE_ROOT / "config"))
os.environ.setdefault("LOCALSTORE_DATA_DIR", str(_LOCALSTORE_ROOT / "data"))
for _path in (
    os.environ["LOCALSTORE_CACHE_DIR"],
    os.environ["LOCALSTORE_CONFIG_DIR"],
    os.environ["LOCALSTORE_DATA_DIR"],
):
    Path(_path).mkdir(parents=True, exist_ok=True)

nonebot.init(command_start={"/"}, superusers={"admin"})

_ORIGINAL_REQUIRE = nonebot.require
_LOCAL_PLUGIN_REQUIRE_NAMES = {"cck", "daily_task", "mailbox"}


def _require_with_local_plugin_names(name: str):
    if name in _LOCAL_PLUGIN_REQUIRE_NAMES:
        return importlib.import_module(f"plugins.{name}")
    return _ORIGINAL_REQUIRE(name)


nonebot.require = _require_with_local_plugin_names


def pytest_configure(config: pytest.Config) -> None:
    os.environ.setdefault("ENVIRONMENT", "test")
    os.environ.setdefault("COMMAND_START", '["/"]')
    os.environ.setdefault("SUPERUSERS", '["admin"]')
    config.stash[NONEBOT_INIT_KWARGS] = {
        "driver": "~fastapi",
        "command_start": {"/"},
        "superusers": {"admin"},
    }
    config.stash[NONEBOT_START_LIFESPAN] = False


@pytest.fixture(scope="session", autouse=True)
async def register_satori_adapter(after_nonebot_init: None) -> None:
    nonebot.get_driver().register_adapter(SatoriAdapter)


@pytest.fixture(autouse=True)
def isolated_localstore(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in ("CACHE", "CONFIG", "DATA"):
        target = tmp_path / name.lower()
        target.mkdir()
        monkeypatch.setenv(f"LOCALSTORE_{name}_DIR", str(target))
    return tmp_path


@pytest.fixture
def sqlite_session(monkeypatch: pytest.MonkeyPatch):
    patched: list[tuple[Any, str]] = []

    def factory(database_module: Any, base: Any):
        engine = create_engine("sqlite:///:memory:")
        base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        monkeypatch.setattr(database_module, "session", session, raising=False)
        patched.append((database_module, "session"))
        return session

    yield factory

    for database_module, attr in patched:
        session = getattr(database_module, attr, None)
        if session is not None:
            session.close()
        setattr(database_module, attr, None)


@pytest.fixture
def make_satori_event() -> Callable[..., MessageCreatedEvent]:
    def factory(
        text: str = "/help",
        *,
        user_id: str = "user",
        channel_id: str = "channel",
        guild_id: str = "guild",
        message_id: str = "message",
        to_me: bool = True,
    ) -> MessageCreatedEvent:
        user = User(id=user_id, name=user_id)
        channel = Channel(id=channel_id, name=channel_id)
        guild = Guild(id=guild_id, name=guild_id)
        member = Member(user=user, nick=user_id)
        now = datetime.fromtimestamp(1_700_000_000)
        return MessageCreatedEvent(
            type="message-created",
            timestamp=now,
            login=Login(
                sn=0,
                status=LoginStatus.ONLINE,
                adapter="satori",
                platform="test",
                user=User(id="bot", name="bot"),
            ).model_dump(),
            channel=channel,
            guild=guild,
            member=member,
            message=MessageObject(
                id=message_id,
                content=str(Message(text)),
                channel=channel,
                guild=guild,
                member=member,
                user=user,
                created_at=now,
            ).model_dump(),
            user=user,
            to_me=to_me,
        )

    return factory
