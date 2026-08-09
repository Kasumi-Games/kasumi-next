from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bot_import_loads_alconna_dependants() -> None:
    """Exercise the real production import order in a fresh interpreter."""

    script = """
import nonebot
import bot

required = (
    "nonebot_plugin_alconna",
    "mailbox",
    "daily",
    "nonebot_plugin_manosaba_memes",
)
missing = [name for name in required if nonebot.get_plugin(name) is None]
if missing:
    raise SystemExit(f"missing plugins: {', '.join(missing)}")
"""
    env = os.environ.copy()
    env["LOG_LEVEL"] = "WARNING"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
