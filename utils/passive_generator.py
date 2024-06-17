from typing import Dict
from nonebot.adapters.satori import MessageEvent, MessageSegment


class PassiveGenerator:
    def __init__(self, event: MessageEvent):
        self.event = event
        self.seq = 0

    @property
    def element(self):
        self.seq += 1
        return MessageSegment(
            type="qq:passive",
            data={"id": self.event.message.id, "seq": self.seq},
        )


generators: Dict[str, PassiveGenerator] = {}
