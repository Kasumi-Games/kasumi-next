def is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def get_amount_for_level(level: int) -> int:
    if level <= 20:
        return 3 + level
    elif level <= 60:
        return int(25 + (level - 20) ** 1.3)
    else:
        return int(150 * 1.05 ** (level - 60))
