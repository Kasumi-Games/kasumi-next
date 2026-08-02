from typing import Any
from typing import Dict
from typing import List

import bestdori.songs as songs
from bestdori.bands import get_all_async as get_bands_all_async

from .utils import filter_song_data


class DataStore:
    def __init__(self) -> None:
        self.data: Dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def get(self, key: str) -> Any:
        return self.data.get(key)


class SongStore(DataStore):
    def __init__(self) -> None:
        super().__init__()

    async def update(self) -> None:
        self.set("songs", await songs.get_all_async())

    def get(self) -> Dict[str, Dict[str, Any]]:
        return filter_song_data(self.data.get("songs", {}))

    def get_raw(self) -> Dict[str, Dict[str, Any]]:
        return self.data.get("songs", {})


class BandStore(DataStore):
    def __init__(self) -> None:
        super().__init__()

    async def update(self) -> None:
        self.set("bands", await get_bands_all_async())

    def get(self) -> Dict[str, Dict[str, Any]]:
        return self.data.get("bands", {})


class GamersStore(DataStore):
    def __init__(self) -> None:
        super().__init__()
        self._sessions: Dict[str, object] = {}

    def get(self) -> List[str]:
        return self.data.get("gamers", [])

    def add(self, gamer: str) -> object:
        gamers = self.get()
        if gamer not in gamers:
            gamers.append(gamer)
        self.set("gamers", gamers)
        session = object()
        self._sessions[gamer] = session
        return session

    def remove(self, gamer: str) -> None:
        gamers = self.get()
        if gamer in gamers:
            gamers.remove(gamer)
        self.set("gamers", gamers)
        self._sessions.pop(gamer, None)

    def is_current(self, gamer: str, session: object) -> bool:
        return self._sessions.get(gamer) is session
