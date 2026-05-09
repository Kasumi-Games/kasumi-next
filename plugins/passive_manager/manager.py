from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from nonebot.adapters.satori import MessageEvent


@dataclass
class PassiveData:
    event: MessageEvent
    message_id: str
    seq: int


class PassiveManager:
    def __init__(self):
        self._data: List[PassiveData] = []

    async def add_event(self, event: MessageEvent) -> None:
        self._data.append(PassiveData(event=event, message_id=event.message.id, seq=0))

    def get_available_data(
        self, api_name: str, api_data: Dict[str, Any]
    ) -> Optional[PassiveData]:
        if api_name != "message_create":
            return None

        channel_id = api_data.get("channel_id")

        if channel_id is None or not isinstance(channel_id, str):
            return None

        current_time = datetime.now()

        # 筛选满足条件的数据，记录在 self._data 中的索引
        candidates = [
            (i, data)
            for i, data in enumerate(self._data)
            if data.event.channel.id == channel_id
            and data.event.timestamp + timedelta(minutes=5) > current_time
            and data.seq <= 5
        ]

        if not candidates:
            return None

        # 按时间戳排序，选最新的
        candidates.sort(key=lambda item: item[1].event.timestamp.timestamp())
        idx = candidates[-1][0]

        # 增加 seq
        self._data[idx].seq += 1

        return self._data[idx]

    def clear_timeout_data(self) -> None:
        current_time = datetime.now()

        self._data = [
            data
            for data in self._data
            if data.event.timestamp + timedelta(minutes=5) > current_time
        ]
