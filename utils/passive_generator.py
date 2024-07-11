from typing import Dict
from datetime import datetime, timedelta
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


class ExpiringDict:
    def __init__(self, expiration_minutes=5):
        self.data = {}
        self.expiration_minutes = expiration_minutes

    def _remove_expired_entries(self):
        current_time = datetime.now()
        expired_keys = [
            key
            for key, value in self.data.items()
            if value["timestamp"] + timedelta(minutes=self.expiration_minutes)
            < current_time
        ]
        for key in expired_keys:
            del self.data[key]

    def __setitem__(self, key, value):
        self._remove_expired_entries()
        self.data[key] = {"value": value, "timestamp": datetime.now()}

    def __getitem__(self, key):
        self._remove_expired_entries()
        item = self.data.get(key)
        if (
            item
            and item["timestamp"] + timedelta(minutes=self.expiration_minutes)
            > datetime.now()
        ):
            return item["value"]
        else:
            if key in self.data:
                del self.data[key]
            raise KeyError("Key has expired or does not exist")

    def __delitem__(self, key):
        self._remove_expired_entries()
        if key in self.data:
            del self.data[key]

    def __contains__(self, key):
        self._remove_expired_entries()
        if key in self.data:
            item = self.data[key]
            if (
                item["timestamp"] + timedelta(minutes=self.expiration_minutes)
                > datetime.now()
            ):
                return True
            else:
                del self.data[key]
                return False
        return False

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


generators: Dict[str, PassiveGenerator] = ExpiringDict(5)
