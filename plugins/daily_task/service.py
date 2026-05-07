"""Daily task service: assignment, progress check, completion."""

import json
import time
import random
from pathlib import Path
from datetime import datetime
from typing import Optional

from nonebot.log import logger

from .models import DailyTask
from .database import get_session

from .. import monetary


class DailyTaskService:
    def __init__(self):
        self._session = None
        self._task_configs = None

    @property
    def session(self):
        if self._session is None:
            self._session = get_session()
        return self._session

    @property
    def task_configs(self):
        if self._task_configs is None:
            config_path = Path(__file__).parent / "tasks.json"
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._task_configs = {t["id"]: t for t in data["tasks"]}
        return self._task_configs

    def get_task_config_list(self):
        return list(self.task_configs.values())

    def ensure_daily_task(self, user_id: str) -> Optional[DailyTask]:
        """Ensure the user has a daily task for today. If not, assign one."""
        today = datetime.now().strftime("%Y-%m-%d")
        task = (
            self.session.query(DailyTask).filter_by(user_id=user_id, date=today).first()
        )
        if task:
            return task

        # Randomly assign a task
        config_list = self.get_task_config_list()
        if not config_list:
            logger.warning("No task configs available")
            return None

        cfg = random.choice(config_list)
        task = DailyTask(user_id=user_id, date=today, task_id=cfg["id"])
        self.session.add(task)
        self.session.commit()
        return task

    def get_today_task(self, user_id: str) -> Optional[DailyTask]:
        """Get the user's task for today."""
        today = datetime.now().strftime("%Y-%m-%d")
        return (
            self.session.query(DailyTask).filter_by(user_id=user_id, date=today).first()
        )

    async def check_progress(
        self,
        user_id: str,
        event_type: str,
        data: Optional[dict] = None,
    ) -> str | None:
        """Check and complete daily task if conditions are met.

        If the task matches and is not yet completed, awards stickers
        and returns a notification message.

        Returns the notification message if the task was completed, None otherwise.
        """
        task = self.get_today_task(user_id)
        if not task or task.is_completed:
            return None

        cfg = self.task_configs.get(task.task_id)
        if not cfg:
            return None

        # Match event type and conditions
        if not self._match(cfg, event_type, data or {}):
            return None

        # Mark complete
        task.is_completed = True
        task.completed_at = int(time.time())
        self.session.commit()

        # Award stickers
        monetary.add_star_stickers(user_id, cfg["reward"], f"daily_task_{task.task_id}")

        return f"每日任务【{cfg['name']}】完成！\n获得 {cfg['reward']} 张星星贴纸！"

    def _evaluate_condition(self, cond: dict, data: dict) -> bool:
        """Evaluate a single condition against data."""
        field = cond["field"]
        op = cond["op"]
        expected = cond["value"]
        actual = data.get(field)

        if actual is None:
            return False

        match op:
            case "==":
                return actual == expected
            case "!=":
                return actual != expected
            case ">":
                return actual > expected
            case ">=":
                return actual >= expected
            case "<":
                return actual < expected
            case "<=":
                return actual <= expected
            case "in":
                return actual in expected
            case _:
                return False

    def _match(self, cfg: dict, event_type: str, data: dict) -> bool:
        """Match task type and all conditions."""
        if cfg["type"] != event_type:
            return False
        conditions = cfg.get("conditions", [])
        return all(self._evaluate_condition(c, data) for c in conditions)
