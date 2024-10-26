import json
from typing import List
from pathlib import Path
import datetime


with open(Path(__file__).parent / "character_birthdays.json", "r", encoding="utf-8") as f:
    birthday_map = json.load(f)


def get_today_birthday() -> List[str]:
    """获取今天过生日的角色

    Returns:
        List[str]: 今天过生日的角色列表
    """
    today = datetime.date.today()
    today_str = today.strftime("%m月%d日")
    result = []
    for name, birthday in birthday_map.items():
        if birthday == today_str:
            result.append(name)
    return result
