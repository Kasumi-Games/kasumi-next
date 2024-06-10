from typing import Any, Dict, List


class DataStore:
    def __init__(self) -> None:
        self.data: Dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def get(self, key: str) -> Any:
        return self.data.get(key)


class GamersStore(DataStore):
    def __init__(self) -> None:
        super().__init__()

    def get(self) -> List[str]:
        return self.data.get("gamers", [])

    def add(self, gamer: str) -> None:
        gamers = self.get()
        gamers.append(gamer)
        self.set("gamers", gamers)

    def remove(self, gamer: str) -> None:
        gamers = self.get()
        gamers.remove(gamer)
        self.set("gamers", gamers)
