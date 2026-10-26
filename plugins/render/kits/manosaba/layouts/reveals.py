"""Facing-page answer exhibits for the two guessing-game plugins."""

from .folio import surface
from .folio import gain_rows
from ..components import ROSE
from ..components import MUTED


def _reward_receipt(f, data, x, y, width):
    if data.outcome != "win":
        return y
    y = f.person(data.winner, x, y, width)
    rows = [("答对奖励", f"+{data.final_amount} Pt")]
    if data.multiplier > 1 and data.birthday_names:
        rows.append(
            ("生日加成", f"× {data.multiplier} · {'、'.join(data.birthday_names)}")
        )
    rows += gain_rows(data)
    return f.facts(rows, x, y + 24, width)


@surface(1240, book=True)
def cck(f, data):
    from plugins.cck.render.reveal import _subtitle
    from plugins.cck.render.reveal import _pool_text
    from plugins.cck.render.reveal import _headline_text

    y = f.title("卡面答案", "CARD IDENTIFICATION", _subtitle(data))
    f.image(data.card_image, 58, y, 520, 440)
    a = f.text(data.character_name, 58, y + 468, 520, 39)
    if data.card_title:
        a = f.text(data.card_title, 58, a + 16, 520, 25)
    meta = [("卡池", _pool_text(data))]
    if data.rarity:
        meta.insert(0, ("稀有度", "★" * data.rarity))
    a = f.facts(meta, 58, a + 30, 520)
    if data.outcome == "win":
        b = f.stamp(_headline_text(data), 664, y + 12, 240)
    else:
        b = f.text(_headline_text(data), 664, y + 12, 518, 42, ROSE)
    if data.winner_attempt:
        b = f.text(f"第 {data.winner_attempt} 次答对", 664, b + 25, 518, 24, MUTED)
    b = _reward_receipt(f, data, 664, b + 36, 518)
    f.gutter(578, 664, y, max(a, b))
    f.footer("/猜卡面 开始下一次挑战", max(a, b) + 30)


@surface(1240, book=True)
def chart(f, data):
    from plugins.guess_chart.render.reveal import _subtitle
    from plugins.guess_chart.render.reveal import _stats_text
    from plugins.guess_chart.render.reveal import _headline_text
    from plugins.guess_chart.render.reveal import _difficulty_text

    y = f.title("乐曲答案", "SCORE IDENTIFICATION", _subtitle(data))
    f.image(data.jacket, 78, y + 10, 420, 420)
    a = f.text(_headline_text(data), 78, y + 466, 420, 39, ROSE)
    a = f.text(
        f"候选池 {data.pool_size} 首 · 使用 {data.hints_used} 条提示",
        78,
        a + 18,
        420,
        23,
        MUTED,
    )
    b = f.text(data.song_name, 582, y + 10, 600, 38)
    b = f.text(data.band_name, 582, b + 16, 600, 27, ROSE)
    b = f.section("谱面记录", 582, b + 32, 600)
    b = f.text(_difficulty_text(data), 582, b, 600, 28)
    stats = _stats_text(data)
    if stats:
        b = f.text(stats, 582, b + 12, 600, 23, MUTED)
    b = _reward_receipt(f, data, 582, b + 38, 600)
    f.gutter(498, 582, y, max(a, b))
    f.footer("/猜谱面 开始下一次挑战", max(a, b) + 28)
