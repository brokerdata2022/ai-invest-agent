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


def test_expectations_chain_second_offsets_preserve_order():
    """Регресія 2026-10-02: весь ланцюжок check_releases→update_forecasts→
    compare_expectations→synthesize_expectations→notify_expectations
    тепер щохвилини (було: зсуви в межах 15-хв вікна) — порядок у межах
    ОДНІЄЇ хвилини тепер тримається на "second", не "minute". Критично:
    update_forecasts МАЄ йти перед compare_expectations (інакше
    'detected'-рядок, який update_forecasts ще не встиг прочитати,
    стане 'processed' і зникне з вибірки НАЗАВЖДИ — не самолікується
    наступного тику, на відміну від решти пар)."""
    chain = [
        "check_releases", "update_forecasts", "compare_expectations",
        "synthesize_expectations", "notify_expectations",
    ]
    seconds = [SCHEDULE[name]["trigger"].get("second", 0) for name in chain]
    assert seconds == sorted(seconds), f"{chain} мають зростаючий 'second': {seconds}"
    assert len(set(seconds)) == len(seconds), "кожен крок ланцюжка має власний 'second', без колізій"
