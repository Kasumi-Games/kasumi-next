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

        # 筛选满足条件的数据
        passive_data = sorted(
            [
                data
                for data in self._data
                if data.event.channel.id == channel_id
                and data.event.timestamp + timedelta(minutes=5) > current_time
                and data.seq <= 5
            ],
            key=lambda data: data.event.timestamp.timestamp(),
        )

        if not passive_data:
            return None

        # 增加 seq
        for i, data in enumerate(self._data):
            if data.message_id == passive_data[-1].message_id:
                self._data[i].seq += 1
                break

        return passive_data[-1]

    def clear_timeout_data(self) -> None:
        current_time = datetime.now()

        self._data = [
            data
            for data in self._data
            if data.event.timestamp + timedelta(minutes=5) > current_time
        ]
