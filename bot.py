import nonebot
from nonebot.adapters.satori import Adapter as Adapter

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(Adapter)

nonebot.load_plugins("plugins")

if __name__ == "__main__":
    nonebot.run()
