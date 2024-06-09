from typing import Any, Dict
import bestdori.songs as songs
from bestdori.utils import get_bands_all_async

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
        self.set("songs", filter_song_data(await songs.get_all_async()))

    def get(self) -> Dict[str, Dict[str, Any]]:
        return self.data.get("songs", {})


class BandStore(DataStore):
    def __init__(self) -> None:
        super().__init__()

    async def update(self) -> None:
        self.set("bands", await get_bands_all_async())

    def get(self) -> Dict[str, Dict[str, Any]]:
        return self.data.get("bands", {})