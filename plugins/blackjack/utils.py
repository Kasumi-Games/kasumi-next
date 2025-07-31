from typing import Optional


def get_action(msg: str) -> Optional[str]:
    msg = msg.strip().lower()
    if msg in ["h", "hit", "补牌", "补"]:
        return "h"
    elif msg in ["s", "stand", "停牌", "停"]:
        return "s"
    elif msg in ["d", "double", "双倍", "双"]:
        return "d"
    else:
        return None
