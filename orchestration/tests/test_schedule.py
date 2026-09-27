from apscheduler.triggers.cron import CronTrigger

from jobs import JOBS
from schedule import SCHEDULE


def test_schedule_and_jobs_names_match():
    assert set(SCHEDULE) == set(JOBS), "Кожна джоба в schedule.py має відповідник у jobs.py і навпаки"


def test_every_schedule_entry_has_trigger_and_why():
    for name, cfg in SCHEDULE.items():
        assert cfg.get("trigger"), f"{name}: відсутній trigger"
        assert cfg.get("why"), f"{name}: відсутнє пояснення 'why'"


def test_trigger_kwargs_are_valid_cron_fields():
    for name, cfg in SCHEDULE.items():
        CronTrigger(**cfg["trigger"])  # кидає виняток, якщо аргумент невалідний


def test_every_job_is_subprocess_or_callable():
    for name, spec in JOBS.items():
        assert ("subprocess" in spec) ^ ("callable" in spec), (
            f"{name}: рівно один із 'subprocess'/'callable', не обидва й не жоден"
        )
