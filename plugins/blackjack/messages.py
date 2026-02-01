from __future__ import annotations


class Messages:
    BET_PROMPT = "你要下注多少碎片呢？"
    BET_TIMEOUT = "时间到了哦，黑香澄流程已结束"
    BET_INVALID = "输入的金额不是数字，请重新输入"
    BET_TOO_SMALL = "下注碎片不能少于 1 个哦，请重新输入"
    BET_NOT_ENOUGH = "你只有 {amount} 个碎片，不够下注哦~"
    ALREADY_IN_GAME = "你已经开始了一局黑香澄，先把这局打完再来吧~"
    RESHUFFLE = "牌靴中的牌数太少啦，Kasumi 重新洗下牌哦~"

    DEALER_TURN = "到 Kasumi 的回合啦！"
    DEALER_DRAWN = "Kasumi 一共补了 {count} 张牌"
    DEALER_STAND = "Kasumi 的点数已经大于等于 17，不需要补牌"

    ACTION_PROMPT = '请从"补牌"(h)，"停牌"(s)，"双倍"(d)或者"投降"(q)中选择一项操作哦'
    ACTION_PROMPT_SPLIT = '{hand_name}\n你要"补牌"(h)，"停牌"(s)还是"投降"(q)呢？'
    ACTION_INVALID_SPLIT = '请从"补牌"(h)，"停牌"(s)或"投降"(q)中选择一项操作哦'
    ACTION_INVALID = (
        '请从"补牌"(h)，"停牌"(s){double_part}或者"投降"(q)中选择一项操作哦'
    )
    ACTION_HIT_PROMPT = '请从"补牌"(h)，"停牌"(s)或"投降"(q)中选择一项操作哦'

    DOUBLE_AFTER_SPLIT = "分牌之后不能双倍下注哦~请重新选择"
    DOUBLE_NOT_FIRST = "不能在非第一轮使用双倍下注哦~请重新选择"
    DOUBLE_NOT_ENOUGH = "你只有 {amount} 个碎片，不够双倍下注哦~请重新选择"

    TIMEOUT_LOSE = "时间到了哦，游戏自动结束。下注的碎片已没收哦~\n"

    BUST_LOSE = "你爆牌啦，Kasumi 获胜！输掉了 {amount} 个碎片"
    DEALER_BUST_WIN = "Kasumi 爆牌，你获胜啦！赢得了 {amount} 个碎片"
    DEALER_BUST_WIN_BONUS = "Kasumi 爆牌，你获胜啦！今日首局双倍加成，赢得了 {original} × 2 = {amount} 个碎片"
    RESULT_WIN = "{player} > {dealer}，你获胜啦！赢得了 {amount} 个碎片"
    RESULT_WIN_BONUS = "{player} > {dealer}，你获胜啦！今日首局双倍加成，赢得了 {original} × 2 = {amount} 个碎片"
    RESULT_LOSE = "{player} < {dealer}，Kasumi 获胜！输掉了 {amount} 个碎片"
    RESULT_PUSH = "{player} = {dealer}，平局！下注金额返还"

    SURRENDER_LOSE = "你投降啦，Kasumi 获胜！损失了 {amount} 个碎片"

    BLACKJACK_PUSH = "平局！虽然是 BlackKasumi，但是没有奖励哦~\n"
    BLACKJACK_WIN = "BlackKasumi！你赢得了 1.5 × {bet} = {amount} 个碎片！\n"
    BLACKJACK_WIN_BONUS = (
        "BlackKasumi！今日首局双倍加成，你赢得了 1.5 × {bet} × 2 = {amount} 个碎片！\n"
    )

    SPLIT_PROMPT = "你有一对相同点数的牌，是否要分牌？\n"
    SPLIT_CHOICE = "请从“是”或“否”中选择一项哦"
    SPLIT_TIMEOUT = "让 Kasumi 等这么久，不许分牌了！"
    SPLIT_INVALID = "听不懂喵，就当你不想分牌了吧~"
    SPLIT_NOT_ENOUGH = (
        "你只有 {amount} 个碎片，不够分牌的额外下注哦~接下来将按照不分牌处理"
    )
    SPLIT_TOTAL_BONUS = "今日首局双倍加成，总计赢得 {original} × 2 = {amount} 个碎片\n"
