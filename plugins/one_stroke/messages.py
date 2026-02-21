class Messages:
    HELP = (
        "【一笔画玩法】\n"
        "目标：从起点出发，在一次性画完所有线段（每条边只能走一次）。\n\n"
        "指令：\n"
        "• 一笔画 [简单|普通|困难]\n"
        "  例如：一笔画 困难\n\n"
        "输入：\n"
        "• WASD 序列：移动并绘制（可一次输入多步）\n"
        "• R：重置到起点\n"
        "• Q：放弃本局"
    )

    START = "一笔画开始！\n从起点出发，画完全部线段即可获胜。画的越快奖励越多哦！"
    PROMPT = "请输入 WASD 序列，或输入 R 重置 / Q 放弃。"

    INVALID_INPUT = "输入无效，请只使用 WASD（可多字符）、R 或 Q。"
    RESET = "已重置到起点。"
    GIVE_UP = "已放弃本局。"
    TIMEOUT = "超时未操作，本局已结束。"

    MOVE_FAIL_NO_EDGE = "第 {step} 步无效：该方向没有可走的线段。"
    MOVE_FAIL_REPEAT = "第 {step} 步无效：这条线段已经走过了。"
    MOVE_FAIL_OOB = "第 {step} 步无效：超出边界。"

    WIN = "挑战成功，耗时 {elapsed_seconds} 秒！获得 {reward} 个星之碎片，现在有 {balance} 个碎片。"
    PROGRESS = "已绘制 {drawn}/{total} 条线段，继续！"
    ERROR = "发生意外错误，本局已结束，请稍后重试。"
