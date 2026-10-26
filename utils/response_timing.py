"""Stage timings for slow card replies, including the adapter's send call."""

from time import perf_counter
from contextlib import contextmanager

from nonebot.log import logger


class ResponseTiming:
    def __init__(self, command: str):
        self.command = command
        self.stages: dict[str, float] = {}

    def __enter__(self):
        self.started = perf_counter()
        return self

    @contextmanager
    def stage(self, name: str):
        started = perf_counter()
        try:
            yield
        finally:
            self.stages[name] = perf_counter() - started

    def __exit__(self, *exc):
        # Matcher.finish raises FinishedException even on a successful send;
        # context cleanup ensures the send duration still makes it into logs.
        total = perf_counter() - self.started
        stages = " ".join(f"{name}={elapsed:.3f}s" for name, elapsed in self.stages.items())
        logger.log(
            "INFO" if total >= 2 else "DEBUG",
            f"card_response command={self.command} total={total:.3f}s {stages}",
        )
