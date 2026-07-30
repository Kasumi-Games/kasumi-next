from __future__ import annotations

import pytest

from utils.content_safety import ContentSafetyError
from utils.content_safety import SensitiveTextPolicy
from utils.content_safety import ensure_safe_text
from utils.content_safety import safe_display_text


def test_default_policy_loads_the_vendored_lexicon() -> None:
    policy = SensitiveTextPolicy.default()

    assert len(policy.terms) >= 800
    assert policy.contains(next(iter(policy.terms)))


def test_policy_normalizes_width_case_and_separators() -> None:
    policy = SensitiveTextPolicy.from_terms(("alpha",))

    assert policy.contains("Ａ l-P_h.a")


def test_safe_text_is_accepted() -> None:
    ensure_safe_text("今天一起玩邦邦吧")


def test_sensitive_text_raises_a_generic_message() -> None:
    policy = SensitiveTextPolicy.from_terms(("blocked",))

    with pytest.raises(ContentSafetyError, match="不符合平台规范") as exc_info:
        ensure_safe_text("b l o c k e d", policy=policy)

    assert "blocked" not in str(exc_info.value)


def test_existing_unsafe_content_is_hidden_at_display_time() -> None:
    unsafe_text = next(iter(SensitiveTextPolicy.default().terms))

    assert safe_display_text(unsafe_text, fallback="已隐藏") == "已隐藏"


def test_startup_nickname_cleanup_removes_only_policy_matches(sqlite_session) -> None:
    from plugins.nickname import data_source as nickname_data

    session = sqlite_session(nickname_data, nickname_data.Base)
    session.add_all(
        [
            nickname_data.Nickname(user_id="unsafe", nickname="b l o c k e d"),
            nickname_data.Nickname(user_id="safe", nickname="Kasumi"),
        ]
    )
    session.commit()

    removed = nickname_data.purge_unsafe_nicknames(
        policy=SensitiveTextPolicy.from_terms(("blocked",))
    )

    assert removed == 1
    assert nickname_data.get("unsafe") is None
    assert nickname_data.get("safe") == "Kasumi"
