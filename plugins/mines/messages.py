class Messages:
    BET_PROMPT = "要下注多少星之碎片呢？"
    BET_TIMEOUT = "等太久啦，Kasumi 先回地下室继续找碎片了"
    BET_INVALID = "输入的金额不是数字，请重新输入"
    BET_TOO_SMALL = "下注碎片不能少于 1 个哦"
    BET_NOT_ENOUGH = "你只有 {amount} 个星之碎片，不够下注哦~"
    ALREADY_IN_GAME = "你已经在地下室寻宝了，先把这局玩完吧~"

    MINES_INVALID = (
        "格式错误，请使用“/探险 <下注碎片> <雷的数量>”".replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    MINES_TOO_SMALL = "雷的数量至少要有 1 个哦"
    MINES_TOO_LARGE = "雷太多啦，地下室快没有落脚点了（最多 24 个）"

    START = (
        "Kasumi 偷偷潜入到 Arisa 的地下室，开始搜刮星之碎片！\n"
        "但要小心被 {number} 个埋伏在地下室里的 Arisa 发现哦\n"
        "从左到右、从上到下编号 1-25，输入数字翻开格子。\n"
        "也可以输入“收手”带着战利品离开。"
    )
    PROMPT = "请选择 1-25，或输入“收手”结算"
    INPUT_INVALID = "听不懂喵，请输入 1-25 的数字，或“收手”"
    ALREADY_REVEALED = "这个位置已经被翻开过了，换一个吧"

    SAFE_REVEAL = "安全！Kasumi 捡到了碎片"
    HIT_MINE = "糟糕！被 Arisa 发现了，碎片全都被没收了"
    CASHOUT = "Kasumi 抱着碎片撤退啦！"
    TIMEOUT = "太久没动静了，Kasumi 先离开地下室了"

    STATS_EMPTY = "你还没有玩过地下室探险哦，快来试试吧！"
    STATS_TEXT = (
        "地下室探险统计\n"
        "局数 {total_games} | 胜 {wins} 负 {losses}\n"
        "总下注 {total_wagered} | 总赢 {total_won} | 总输 {total_lost} | 净收益 {net_profit:+d}\n"
        "平均下注 {avg_bet:.1f} | 最大赢 {biggest_win} | 最大输 {biggest_loss}"
    )

    ERROR = "发生意外错误了，已退还下注碎片，稍后再试试吧"

    HELP = (
        "【Arisa 的仓库探险指南】\n"
        "Arisa 的仓库里藏着许多珍贵的星之碎片，但她本人也在仓库里巡逻哦！\n"
        "帮助 Kasumi 避开 Arisa，尽可能多地搜刮碎片吧！\n\n"
        "基础指令：\n"
        "• 探险 [下注金额] [Arisa数量]\n"
        "  例如：探险 100 5\n"
        "  (默认 5 个 Arisa，最多 24 个)\n"
        "• 探险统计\n"
        "  查看你的探险战绩\n\n"
        "游戏操作：\n"
        "• 发送 1-25 的数字翻开箱子\n"
        "• 发送“收手/结算/s”带着战利品逃跑\n\n"
        "奖励规则：\n"
        "• 翻开的安全箱子越多，倍率越高\n"
        "• 巡逻的 Arisa 数量越多，倍率越高\n"
        "• 若翻到 Arisa，不仅不仅没收本次投入，还会被赶出去哦！"
    )
