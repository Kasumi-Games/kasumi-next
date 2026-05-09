import nonebot
from typing import Optional
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.message import run_postprocessor
from nonebot.adapters.satori import Adapter as Adapter
from nonebot.exception import MatcherException, IgnoredException

from utils.error_handler import setup_logging, generate_error_code, log_error


nonebot.init()

setup_logging()

driver = nonebot.get_driver()
driver.register_adapter(Adapter)

nonebot.load_plugins("plugins")
nonebot.load_plugin("nonebot_plugin_manosaba_memes")


@run_postprocessor
async def global_error_safety_net(
    matcher: Matcher,
    exception: Optional[Exception] = None,
):
    """Log any unhandled exception with an error code.

    Runs after every matcher handler.  If the handler raised an exception
    that was not caught, this postprocessor logs it with a generated error
    code so operators can find the traceback in the log file.

    The user is NOT notified here — the handler already crashed without
    sending a response, and the postprocessor cannot safely reply.
    """
    if exception is None:
        return
    if isinstance(exception, (MatcherException, IgnoredException)):
        return

    error_code = generate_error_code()
    log_error(error_code, exception, context=f"unhandled:{matcher.plugin_name}")
    logger.warning(
        "Unhandled exception [{}] in plugin '{}'. User was NOT notified.",
        error_code,
        matcher.plugin_name,
    )


if __name__ == "__main__":
    nonebot.run()
