"""Profile descriptions should fill the expanded Starbeat bio area."""

import pytest

from plugins.inventory.service import PROFILE_DESCRIPTION_MAX_LENGTH
from plugins.inventory.service import validate_profile_description


def test_profile_description_limit_matches_the_seven_line_card_budget() -> None:
    assert PROFILE_DESCRIPTION_MAX_LENGTH == 180
    assert validate_profile_description("简介" * 90) == "简介" * 90


def test_profile_description_rejects_only_after_the_expanded_limit() -> None:
    with pytest.raises(ValueError, match="最多 180 个字符"):
        validate_profile_description("介" * 181)
