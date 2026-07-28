"""Boot the real bot against the Satori simulator and drive a scenario.

This is the sandbox harness: real ``bot.py`` subprocess, real plugin loading,
real databases (fresh, isolated), real Satori protocol over localhost — the
only fake thing is the chat platform on the other side.

Usage:
    uv run python scripts/sandbox/run_sandbox.py [--scenario smoke|full]
        [--open-season] [--keep]

- ``--open-season`` temporarily rewrites seasons.json so season 1 is running
  (start date moved to yesterday), restoring the file on exit. This is how an
  operator would run an early season; it is config, not code.
- Outputs land in ``.cache/sandbox/run-<timestamp>/``: bot log, transcript
  (markdown), every image reply decoded to PNG.
"""

import os
import re
import sys
import json
import time
import base64
import signal
import asyncio
import argparse
import datetime
import subprocess
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "sandbox"))

from aiohttp import web  # noqa: E402
from satori_sim import SatoriSim  # noqa: E402
from satori_sim import build_app  # noqa: E402

SIM_PORT = 5140
ADMIN = {"user_id": "9001", "nickname": "管理员"}
PLAYER = {"user_id": "1001", "nickname": "香澄"}
PLAYER2 = {"user_id": "1002", "nickname": "有咲"}

DATA_URI = re.compile(r'src="data:(image/[a-z]+);base64,([A-Za-z0-9+/=]+)"')


class Sandbox:
    def __init__(self, run_dir: Path, *, open_season: bool) -> None:
        self.run_dir = run_dir
        self.images_dir = run_dir / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.bot_log = (run_dir / "bot.log").open("w", encoding="utf-8")
        self.transcript: list[str] = []
        self.outbox_cursor = 0
        self.image_count = 0
        self.open_season = open_season
        self.seasons_backup: str | None = None
        self.bot: subprocess.Popen | None = None
        self.sim = SatoriSim()
        self.runner: web.AppRunner | None = None
        self.findings: list[str] = []

    # ------------------------------------------------------------------
    async def start(self) -> None:
        if self.open_season:
            self._open_season()

        self.runner = web.AppRunner(build_app(self.sim))
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", SIM_PORT)
        await site.start()

        env = os.environ.copy()
        sandbox_data = self.run_dir / "data"
        self._seed_assets(sandbox_data)
        env.update(
            {
                "ENVIRONMENT": "prod",
                "DRIVER": "~httpx+~websockets",
                "HOST": "127.0.0.1",
                "PORT": "7141",
                "LOG_LEVEL": "INFO",
                "COMMAND_START": '["/", ".", ""]',
                "SATORI_CLIENTS": json.dumps(
                    [{"host": "127.0.0.1", "port": str(SIM_PORT), "path": "", "token": "sandbox"}]
                ),
                "LOCALSTORE_DATA_DIR": str(sandbox_data),
                "LOCALSTORE_CACHE_DIR": str(ROOT / ".cache"),
                "LOCALSTORE_CONFIG_DIR": str(self.run_dir / "config"),
                "SUPERUSERS": json.dumps([ADMIN["user_id"]]),
                "WHITELIST": "[]",
                "BESTDORI_PROXY": "null",
                "ENABLE_GUESS_CHART": "true",
                "ENABLE_CCK": "true",
                "ENABLE_BANG_AVATAR": "true",
                "QQ_BOT_APP_ID": "123456789",
            }
        )
        self.bot = subprocess.Popen(
            ["uv", "run", "python", "bot.py"],
            cwd=ROOT,
            env=env,
            stdout=self.bot_log,
            stderr=subprocess.STDOUT,
        )

    def _seed_assets(self, sandbox_data: Path) -> None:
        """Symlink pure-asset stores into the sandbox; databases stay fresh.

        cck's card art library (~2GB) and bang_avatar's source images are
        static downloads — re-fetching them per sandbox run is pointless and
        made the first boot exceed the ready timeout. Anything with a ``.db``
        stays out so game/economy state is always a clean first boot.
        """

        real_root = ROOT / ".data" / "kasumi-data"
        for name in ("cck", "bang_avatar"):
            source = real_root / name
            if not source.exists():
                continue
            if list(source.rglob("*.db")):
                self.log(f"! refusing to seed {name}: contains databases")
                continue
            target = sandbox_data / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.symlink_to(source, target_is_directory=True)
                self.log(f"> seeded assets: {name} -> {source}")

    def _open_season(self) -> None:
        path = ROOT / "plugins/inventory/seasons.json"
        self.seasons_backup = path.read_text(encoding="utf-8")
        config = json.loads(self.seasons_backup)
        yesterday = (
            datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
            - datetime.timedelta(days=1)
        ).strftime("%Y-%m-%dT00:00:00+08:00")
        config["seasons"][0]["starts_at"] = yesterday
        path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.log(f"> season opened for sandbox: starts_at={yesterday}")

    def restore_season(self) -> None:
        if self.seasons_backup is not None:
            (ROOT / "plugins/inventory/seasons.json").write_text(
                self.seasons_backup, encoding="utf-8"
            )
            self.seasons_backup = None

    # ------------------------------------------------------------------
    async def wait_ready(self, timeout: float = 600.0) -> None:
        deadline = time.time() + timeout
        async with aiohttp.ClientSession() as http:
            while time.time() < deadline:
                if self.bot and self.bot.poll() is not None:
                    raise RuntimeError(
                        f"bot exited early with {self.bot.returncode}; see bot.log"
                    )
                try:
                    async with http.get(
                        f"http://127.0.0.1:{SIM_PORT}/_sandbox/status"
                    ) as resp:
                        status = await resp.json()
                    if status["ready"]:
                        self.log("> bot connected and authenticated")
                        return
                except aiohttp.ClientError:
                    pass
                await asyncio.sleep(1.0)
        raise TimeoutError("bot never connected; see bot.log")

    # ------------------------------------------------------------------
    async def say(
        self,
        who: dict,
        content: str,
        *,
        quiet_ms: int = 1500,
        timeout: float = 45.0,
        label: str | None = None,
    ) -> list[dict]:
        """Send a message as ``who`` and collect the bot's replies."""

        self.log(f"\n### {label or content}")
        self.log(f"**{who['nickname']}**: `{content}`")
        async with aiohttp.ClientSession() as http:
            async with http.post(
                f"http://127.0.0.1:{SIM_PORT}/_sandbox/send",
                json={**who, "content": content},
            ) as resp:
                if resp.status != 200:
                    self.log(f"! send failed: {await resp.text()}")
                    self.findings.append(f"send failed for {content!r}")
                    return []

            deadline = time.time() + timeout
            last_change = time.time()
            replies: list[dict] = []
            while time.time() < deadline:
                async with http.get(
                    f"http://127.0.0.1:{SIM_PORT}/_sandbox/outbox",
                    params={"since": self.outbox_cursor},
                ) as resp:
                    fresh = (await resp.json())["calls"]
                if fresh:
                    self.outbox_cursor = fresh[-1]["seq"] + 1
                    replies.extend(fresh)
                    last_change = time.time()
                if replies and (time.time() - last_change) * 1000 >= quiet_ms:
                    break
                await asyncio.sleep(0.25)

        for call in replies:
            self._record_reply(call)
        if not replies:
            self.log("_(no reply)_")
        return replies

    def _record_reply(self, call: dict) -> None:
        content = call["body"].get("content", "")
        text = DATA_URI.sub("", content)
        text = re.sub(r"<[^>]+>", "", text).strip()
        images = []
        for mime, blob in DATA_URI.findall(content):
            self.image_count += 1
            suffix = mime.split("/")[-1]
            name = f"reply-{self.image_count:03d}.{suffix}"
            (self.images_dir / name).write_bytes(base64.b64decode(blob))
            images.append(name)
        line = f"**bot** ({call['api']}):"
        if text:
            line += f" {text}"
        if images:
            line += " " + " ".join(f"![{n}](images/{n})" for n in images)
        self.log(line)

    # ------------------------------------------------------------------
    def log(self, line: str) -> None:
        print(line)
        self.transcript.append(line)

    async def finish(self) -> None:
        async with aiohttp.ClientSession() as http:
            async with http.get(f"http://127.0.0.1:{SIM_PORT}/_sandbox/gaps") as resp:
                gaps = (await resp.json())["gaps"]
        self.log("\n## API gaps (bot called, sim stubbed)")
        self.log("\n".join(f"- {g}" for g in gaps) if gaps else "- none")

        if self.bot:
            self.bot.send_signal(signal.SIGINT)
            try:
                self.bot.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.bot.kill()
        if self.runner:
            await self.runner.cleanup()
        self.restore_season()
        self.bot_log.close()
        (self.run_dir / "transcript.md").write_text(
            "\n".join(self.transcript), encoding="utf-8"
        )
        print(f"\ntranscript: {self.run_dir / 'transcript.md'}")
        print(f"bot log:    {self.run_dir / 'bot.log'}")


# ----------------------------------------------------------------------
async def scenario_smoke(box: Sandbox) -> None:
    await box.say(PLAYER, "help", label="帮助板")
    await box.say(PLAYER, "签到", label="签到卡")
    await box.say(PLAYER, "余额", label="余额（应为文本）")


async def scenario_full(box: Sandbox) -> None:
    p, p2, admin = PLAYER, PLAYER2, ADMIN

    await box.say(p, "help", label="帮助板")
    await box.say(p, "签到", label="签到卡（首次）")
    await box.say(p, "签到", label="重复签到（应为文本）")
    await box.say(p2, "签到", label="玩家2签到")
    await box.say(p, "排行榜", label="等级排行卡")
    await box.say(p, "资料", label="玩家名片")
    await box.say(p, "邮箱", label="空收件箱卡")

    # 管理员补给（贴纸 2600 + 赛季 Pt 500 + 主题道具）-> 邮箱全流程
    await box.say(
        admin,
        "schedulemail send -r all -t 沙盒补给 -c 各位玩家请查收测试补给。 "
        "-s 2600 -k 500 -i theme_kasumi_starbeat:1",
        label="管理员发补给邮件",
        timeout=60,
    )
    await box.say(p, "邮箱", label="收件箱卡（有邮件）")
    await box.say(p, "邮件 1", label="邮件详情卡")
    await box.say(p, "邮件 领取", label="一键领取卡")
    await box.say(p2, "邮件 领取", label="玩家2领取")
    await box.say(p, "余额", label="领取后余额（文本）")

    # 游戏面板 + 结果卡
    await box.say(p, "探险 20", label="探险开局（面板+身份条）")
    await box.say(p, "3", label="探险翻格")
    await box.say(p, "收手", label="探险结算（结果卡）")
    await box.say(p, "一笔画", label="一笔画开局")
    await box.say(p, "Q", label="一笔画放弃（文本）")
    await box.say(p, "探险统计", label="探险统计卡")
    await box.say(p, "黑香澄统计", label="黑香澄统计（空状态文本）")

    # 红包：创建卡 -> 单抢文本 -> 完局卡
    await box.say(p, "发红包 60 2", label="发红包（创建卡）")
    await box.say(p2, "抢红包", label="玩家2抢（文本）")
    await box.say(p, "抢红包", label="创建者抢完（完局卡）")

    # 抽卡
    await box.say(p, "抽卡", label="卡池信息（文本）")
    await box.say(p, "抽卡 十连", label="十连揭示卡", timeout=60)
    await box.say(p, "抽卡 十连", label="第二次十连", timeout=60)

    # 主题穿戴 -> 主题在真实表面生效
    await box.say(p, "装扮", label="装扮列表")
    await box.say(p, "装扮 装备 theme_kasumi_starbeat", label="装备星之鼓动主题")
    await box.say(p, "资料", label="Kasumi 主题名片")
    await box.say(p, "探险 20", label="Kasumi 主题探险面板")
    await box.say(p, "收手", label="Kasumi 主题结果卡")

    await box.say(p, "赛季", label="赛季信息（验证时区显示）")
    await box.say(p, "赛季趋势", label="赛季趋势卡", timeout=60)


async def scenario_extra(box: Sandbox) -> None:
    """Surfaces the full scenario missed: nickname identity, blackjack, cck,
    guess_chart."""

    p, p2, admin = PLAYER, PLAYER2, ADMIN

    await box.say(p, "设置昵称 香澄", label="设置昵称")
    await box.say(p, "签到", label="签到卡（应显示昵称 香澄）")
    await box.say(
        admin,
        "schedulemail send -r all -t 补给 -c 测试补给。 -k 300",
        label="补给 Pt",
        timeout=60,
    )
    await box.say(p, "邮件 领取", label="领取")

    await box.say(p, "黑香澄 20", label="黑香澄开局（桌面）")
    await box.say(p, "停牌", label="黑香澄停牌（结算）", timeout=60)
    await box.say(p, "黑香澄统计", label="黑香澄统计卡（有数据）")

    await box.say(p, "猜卡面", label="猜卡面出题", timeout=90)
    await box.say(p2, "bzd", label="bzd 揭示卡", timeout=60)

    # 猜谱面 was the gap that let a live P0 through: with no argument the
    # difficulty defaults to normal, so the start path calls the bestdori
    # chart renderer (render_chart) — exactly the name the render/ reveal
    # subpackage shadowed. Needs bestdori network access; generous timeout.
    await box.say(p, "猜谱面", label="猜谱面出题（bestdori 谱面渲染）", timeout=180)
    await box.say(p2, "bzd", label="猜谱面 bzd 揭示卡", timeout=60)

    await box.say(p, "一笔画排行榜", label="一笔画排行榜")
    await box.say(p, "help 探险", label="帮助详情卡")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["smoke", "full", "extra"], default="smoke")
    parser.add_argument("--open-season", action="store_true")
    parser.add_argument("--keep", action="store_true", help="keep the bot running")
    args = parser.parse_args()

    run_dir = ROOT / ".cache" / "sandbox" / time.strftime("run-%Y%m%d-%H%M%S")
    box = Sandbox(run_dir, open_season=args.open_season)
    try:
        await box.start()
        await box.wait_ready()
        await asyncio.sleep(2)
        if args.scenario == "smoke":
            await scenario_smoke(box)
        elif args.scenario == "extra":
            await scenario_extra(box)
        else:
            await scenario_full(box)
        if args.keep:
            print("bot kept running; Ctrl+C to stop")
            while True:
                await asyncio.sleep(3600)
    finally:
        await box.finish()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
