"""Text kept for prompts, refusals and graceful fallbacks."""

from __future__ import annotations

from .models import CardType
from .models import TourOutcome
from .models import TourSnapshot


class Messages:
    START = "巡演开始！管理体力、乐器和食物，完成 26 场演出即可通关。"
    ALREADY_IN_GAME = "你已经在进行巡演了，先把这一局完成吧。"
    GIVE_UP = "已放弃本局巡演。"
    TIMEOUT = "巡演超时（10 分钟未操作），本局已结束。"
    INVALID_INPUT = "输入无效，请发送 1-4、0-4 连续数字，或 q。"
    ERROR = "巡演发生意外，本局已结束；没有产生任何奖励。"
    HELP = (
        "【巡演】\n"
        "目标：完成 26 场演出。每天最多选择 3 次行动。\n"
        "巡演牌消耗体力；装备乐器可按底力减少消耗；食物每天第一张才恢复体力。\n"
        "发送 5 休息会把当天手牌排到日程末尾，但不能连续休息两天。\n"
        "支持 0-4 连续输入；超级难度：0 丢弃乐器；其他难度："
        "已装备时 0 卸下装备，未装备时 0 穿上装备。\n"
        "指令：巡演 [初级|中级|高级|超级]，巡演 -f 强制退出。\n"
        "显示模式：巡演 模式 [图片|文本]。\n"
        "赛季竞速榜：巡演排行榜。"
    )

    @staticmethod
    def instrument_action(snapshot: TourSnapshot) -> str | None:
        if snapshot.difficulty == "超级":
            return "0 丢弃乐器"
        if snapshot.instrument is None:
            return None
        if snapshot.instrument_equipped:
            return "0 卸下装备"
        return "0 穿上装备"

    @staticmethod
    def prompt(snapshot: TourSnapshot) -> str:
        actions = ["1-4 选择手牌"]
        instrument_action = Messages.instrument_action(snapshot)
        if instrument_action is not None:
            actions.append(instrument_action)
        actions.extend(["5 休息", "q 退出"])
        return "请输入 " + "，".join(actions[:-1]) + "，或 " + actions[-1] + "。"

    @staticmethod
    def compact_prompt(snapshot: TourSnapshot) -> str:
        actions = ["1-4 选择手牌"]
        instrument_action = Messages.instrument_action(snapshot)
        if instrument_action is not None:
            actions.append(instrument_action)
        actions.extend(["5 休息", "q 退出"])
        return " · ".join(actions)

    @staticmethod
    def status_text(snapshot: TourSnapshot) -> str:
        lines = [
            f"巡演第{snapshot.day}天 · 已完成 {snapshot.tour_played_count}/26 场",
            f"体力：{snapshot.stamina}/{snapshot.max_stamina} · 今日行动：{snapshot.selection_count}/3",
            f"牌库剩余：{snapshot.deck_size} 张",
        ]
        for index, card in enumerate(snapshot.hand, start=1):
            if card is None:
                lines.append(f"[{index}] 空槽")
                continue
            if card.type is CardType.TOUR:
                label = "难度"
            elif card.type is CardType.INSTRUMENT:
                label = "底力"
            else:
                label = "体力"
            lines.append(f"[{index}] {card.name}（{label}+{card.value}）")
        if snapshot.instrument is None:
            lines.append("当前乐器：无")
        else:
            equipped = "已装备" if snapshot.instrument_equipped else "未装备"
            lines.append(
                f"当前乐器：{snapshot.instrument.name}"
                f"（底力+{snapshot.instrument.value}，{equipped}）"
            )
            if snapshot.last_performance is not None:
                lines.append(f"契合度：下一场难度必须低于 {snapshot.last_performance}")
        return "\n".join(lines)

    @staticmethod
    def invalid_reason(
        reason: str,
        step: int | None = None,
        *,
        can_discard: bool = False,
    ) -> str:
        prefix = f"第 {step} 步：" if step else ""
        if reason == "low_compatibility":
            action = "丢弃" if can_discard else "卸下"
            return prefix + f"当前乐器契合度不足，请先{action}当前乐器后再演出。"
        return {
            "empty_slot": prefix + "这个手牌槽为空，请重新选择。",
            "no_instrument": "当前没有可操作的乐器。",
            "rest_consecutive": "前一天已经休息过，今天不能连续休息。",
            "rest_after_action": "今天已经选择过其他行动，不能再休息。",
            "game_over": "游戏已结束。",
            "invalid_input": Messages.INVALID_INPUT,
        }.get(reason, prefix + "当前行动无效。")

    @staticmethod
    def result_text(data) -> str:
        snapshot = data.snapshot
        outcome_headline = {
            TourOutcome.WIN: "恭喜完成巡演！",
            TourOutcome.STAMINA: "巡演失败：体力耗尽。",
            TourOutcome.QUIT: "已退出巡演。",
            TourOutcome.TIMEOUT: "巡演失败：操作超时。",
        }.get(data.outcome, "巡演失败。")
        lines = [
            outcome_headline,
            f"完成场数：{snapshot.tour_played_count}/26，耗时：{data.elapsed_seconds:.0f} 秒。",
            f"剩余体力：{snapshot.stamina}/{snapshot.max_stamina}。",
            f"获得 Pt：{data.reward_pt}，当前余额：{data.balance} Pt。",
        ]
        base_reward = (
            data.reward_pt
            if data.base_reward_pt is None
            else data.base_reward_pt
        )
        if data.reward_pt and data.multiplier > 1 and data.birthday_names:
            lines.insert(
                4,
                f"基础奖励：{base_reward} Pt，生日加成 x{data.multiplier}（{'和'.join(data.birthday_names)}）。",
            )
        if data.task_name:
            lines.append(
                f"每日任务【{data.task_name}】完成，获得 {data.task_reward} 张星星贴纸。"
            )
        if data.old_level is not None and data.new_level is not None:
            lines.append(
                f"等级提升：Lv.{data.old_level} → Lv.{data.new_level}，"
                f"获得 {data.level_stickers} 张星星贴纸。"
            )
        return "\n".join(lines)
