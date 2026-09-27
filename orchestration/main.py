#!/usr/bin/env python3
"""
Точка входу контейнера `scheduler` (docker-compose.yml): піднімає
APScheduler і тримає процес живим. Розклад — schedule.py, що саме
виконати — jobs.py. Сам нічого не вирішує (orchestration/CLAUDE.md).

Використання:
    python orchestration/main.py
"""

import logging
import sys
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jobs import JOBS  # noqa: E402
from runner import run_job  # noqa: E402
from schedule import SCHEDULE, TIMEZONE  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone=TIMEZONE)
    for job_name, cfg in SCHEDULE.items():
        if job_name not in JOBS:
            raise KeyError(f"schedule.py має джобу {job_name!r}, якої немає в jobs.py:JOBS")
        trigger = CronTrigger(**cfg["trigger"], timezone=TIMEZONE)
        scheduler.add_job(
            run_job,
            trigger=trigger,
            args=[job_name],
            id=job_name,
            max_instances=1,
            misfire_grace_time=300,
        )
        logger.info("Зареєстровано джобу %s: %s (%s)", job_name, cfg["trigger"], cfg["why"])
    return scheduler


def main() -> None:
    load_dotenv()
    logger.info("Часовий пояс планувальника: %s", TIMEZONE)
    scheduler = build_scheduler()
    logger.info("Стартую APScheduler з %d джобами", len(SCHEDULE))
    scheduler.start()


if __name__ == "__main__":
    main()
