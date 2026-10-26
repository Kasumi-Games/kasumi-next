from unittest.mock import Mock

import pytest
from nonebot.exception import FinishedException

from utils import response_timing


@pytest.mark.parametrize("elapsed, level", [(0.1, "DEBUG"), (11.0, "INFO")])
def test_reply_timing_includes_send_when_matcher_finish_raises(
    monkeypatch, elapsed, level
):
    # finish() raises after the adapter returns, even on success. Its duration
    # must still be reported so network delay can be separated from rendering.
    times = iter([0.0, 0.0, elapsed, elapsed])
    monkeypatch.setattr(response_timing, "perf_counter", lambda: next(times))
    log = Mock()
    monkeypatch.setattr(response_timing.logger, "log", log)

    with pytest.raises(FinishedException):
        with response_timing.ResponseTiming("profile") as timing:
            with timing.stage("send"):
                raise FinishedException

    log.assert_called_once_with(
        level,
        f"card_response command=profile total={elapsed:.3f}s send={elapsed:.3f}s",
    )
