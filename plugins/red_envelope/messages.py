class Messages:
    NOT_IN_CHANNEL = "只能在群聊中使用红包功能哦"
    CREATE_USAGE = (
        "格式错误！用法：发红包 [标题] <金额> <份数>".replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    INVALID_AMOUNT = "红包金额必须是正整数"
    INVALID_COUNT = "红包份数必须是正整数"
    AMOUNT_TOO_SMALL = "红包总金额必须不少于份数（每份至少 1 个星之碎片）"
    INSUFFICIENT_BALANCE = "余额不足！你当前有 {balance} 个星之碎片"
    CREATE_FAILED = "创建红包失败，请稍后再试"
    CREATE_SUCCESS = "红包已创建！ID: {envelope_id}，标题: {title}，金额: {amount}，份数: {count}，有效期 24 小时"
    LIST_EMPTY = "当前群聊中没有可领取的红包"
    LIST_HEADER = "当前群聊中红包列表（{count} 个）:"
    LIST_ITEM = (
        "{id}. {title} | 碎片 {remaining_amount}/{total_amount} | "
        "份数 {remaining_count}/{total_count}"
    )
    CLAIM_USAGE = "格式错误！用法：抢红包 [ID]"
    CLAIM_NOT_FOUND = "未找到该红包"
    CLAIM_NO_ACTIVE = "当前群聊中没有可领取的红包"
    CLAIM_ALREADY = "你已经领过这个红包了"
    CLAIM_EMPTY = "这个红包已经被领完了"
    CLAIM_EXPIRED = "这个红包已经过期了，未领取部分已退还"
    CLAIM_FAILED = "抢红包失败，请稍后再试"
    CLAIM_SUCCESS = "恭喜你抢到 {amount} 个星之碎片！"
    CLAIM_COMPLETE = "{creator}的红包在{duration}内被抢完，{lucky_king}是手气王（{lucky_amount} 个星之碎片）！"
