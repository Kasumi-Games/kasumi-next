import nonebot
from nonebot.adapters.satori import Adapter as Adapter

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(Adapter)

nonebot.load_plugins("plugins")
nonebot.load_plugin("nonebot_plugin_manosaba_memes")

if __name__ == "__main__":
    nonebot.run()
