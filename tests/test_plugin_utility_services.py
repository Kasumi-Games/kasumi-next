from __future__ import annotations

from datetime import datetime
from datetime import timedelta

import pytest


def test_render_color_spacing_and_text_helpers(tmp_path):
    from PIL import Image

    from plugins.render.color import rgb
    from plugins.render.color import rgba
    from plugins.render.color import normalize_color
    from plugins.render.spacing import Insets
    from plugins.render.spacing import as_insets
    from plugins.render.image_cache import ImageCache

    assert rgba(999, -1, 2, 300) == (255, 0, 2, 255)
    assert rgb(1, 2, 3) == (1, 2, 3, 255)
    assert normalize_color("#01020304") == (1, 2, 3, 4)
    assert as_insets(3).horizontal == 6
    assert Insets.xy(2, 5).vertical == 10

    path = tmp_path / "img.png"
    Image.new("RGBA", (2, 2), (10, 20, 30, 255)).save(path)
    cache = ImageCache(max_items=1)
    assert cache.load(path).size == (2, 2)
    assert cache.load(path).mode == "RGBA"


def test_channels_and_nickname_data_sources(tmp_path, sqlite_session):
    from plugins.nickname import data_source as nickname_data
    from plugins.channels.data_source import ChannelMemberManager

    manager = ChannelMemberManager(f"sqlite:///{tmp_path / 'channels.db'}")
    assert manager.add_member_to_channel("c1", "u1", "avatar") is True
    assert manager.add_member_to_channel("c1", "u1", "avatar") is False
    assert [member.id for member in manager.get_channel_members("c1")] == ["u1"]
    assert manager.remove_member_from_channel("c1", "u1") is True
    assert manager.delete_channel("c1") is True

    session = sqlite_session(nickname_data, nickname_data.Base)
    session.add(nickname_data.Nickname(user_id="u1", nickname="Kasumi"))
    session.commit()
    assert nickname_data.get("u1") == "Kasumi"
    assert nickname_data.get_id("Kasumi") == "u1"


@pytest.mark.asyncio
async def test_passive_manager_tracks_recent_channel_events(make_satori_event):
    from plugins.passive_manager.manager import PassiveManager

    manager = PassiveManager()
    event = make_satori_event("hello", channel_id="c1")
    event.timestamp = datetime.now() - timedelta(minutes=1)
    await manager.add_event(event)

    data = manager.get_available_data("message_create", {"channel_id": "c1"})
    assert data.message_id == "message"
    assert data.seq == 1
    assert manager.get_available_data("message_create", {"channel_id": "other"}) is None

    event.timestamp = datetime.now() - timedelta(minutes=6)
    manager.clear_timeout_data()
    assert manager.get_available_data("message_create", {"channel_id": "c1"}) is None


@pytest.mark.asyncio
async def test_bang_avatar_vits_daily_and_whitelist_helpers(
    monkeypatch, make_satori_event
):
    import importlib

    importlib.import_module("plugins.daily_task")
    importlib.import_module("plugins.mailbox")

    from plugins.whitelist import check_blocked
    from plugins.whitelist import plugin_config as whitelist_config
    from plugins.vits.utils import match_character
    from plugins.daily.utils import is_number
    from plugins.daily.utils import get_amount_for_level
    from plugins.bang_avatar.models import Band
    from plugins.bang_avatar.models import Star
    from plugins.bang_avatar.models import WifeData
    from plugins.bang_avatar.models import Attribute

    choices = iter([Band.poppin_party, Star.five, Attribute.happy])
    monkeypatch.setattr("plugins.bang_avatar.models.random.choice", lambda values: next(choices))
    wife = WifeData(user_id="u1", lp_id="u2").generate_wife_data()
    assert wife.band == Band.poppin_party
    assert wife.star == Star.five
    assert wife.attribute == Attribute.happy

    assert match_character("香澄", {"kasumi": ["香澄"]}) == "kasumi"
    assert match_character("unknown", {"kasumi": ["香澄"]}) is None
    assert is_number("1.5") is True
    assert is_number("x") is False
    assert get_amount_for_level(1) == 4

    monkeypatch.setattr(whitelist_config, "whitelist", ["allowed-channel"])
    event = make_satori_event(user_id="allowed", channel_id="allowed-channel")
    assert await check_blocked(event) is None


@pytest.mark.asyncio
async def test_vits_api_wrappers_use_expected_payload(monkeypatch):
    from plugins.vits import utils

    class Response:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def read(self):
            return b"wav"

        async def json(self):
            return {"band": "speaker"}

        def raise_for_status(self):
            raise AssertionError("unexpected status error")

    class Session:
        def __init__(self):
            self.posts = []
            self.gets = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def post(self, url, json):
            self.posts.append((url, json))
            return Response()

        def get(self, url):
            self.gets.append(url)
            return Response()

    sessions = []

    def session_factory():
        session = Session()
        sessions.append(session)
        return session

    monkeypatch.setattr(utils.aiohttp, "ClientSession", session_factory)

    assert await utils.call_synthesize_api("hello", speaker_id=7, url="http://api/synth") == b"wav"
    assert sessions[0].posts[0][0] == "http://api/synth"
    assert sessions[0].posts[0][1]["text"] == "hello"
    assert sessions[0].posts[0][1]["speaker_id"] == 7
    assert await utils.call_speaker_api("http://api/speakers") == {"band": "speaker"}
