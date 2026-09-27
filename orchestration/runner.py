"""
Виконання ОДНІЄЇ джоби (subprocess-скрипт або Python-функція) з логом і
Telegram-алертом при провалі. Тільки виконання — жодної бізнес-логіки
(orchestration/CLAUDE.md).
"""

import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from alerts import notify_failure  # noqa: E402
from jobs import JOBS, REPO_ROOT  # noqa: E402

logger = logging.getLogger(__name__)

LOG_DIR = REPO_ROOT / "logs"
DEFAULT_TIMEOUT_SECONDS = 1800


def _log_path(job_name: str) -> Path:
    LOG_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return LOG_DIR / f"{job_name}_{stamp}.log"


def run_job(job_name: str) -> bool:
    """Повертає True, якщо джоба виконалась успішно (subprocess exit 0
    або функція не кинула виняток)."""
    if job_name not in JOBS:
        raise KeyError(f"Невідома джоба: {job_name!r} (немає в orchestration/jobs.py:JOBS)")

    spec = JOBS[job_name]
    log_path = _log_path(job_name)
    logger.info("Старт джоби %s (лог: %s)", job_name, log_path)

    if "subprocess" in spec:
        try:
            result = subprocess.run(
                spec["subprocess"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=spec.get("timeout", DEFAULT_TIMEOUT_SECONDS),
            )
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") + (exc.stderr or "")
            log_path.write_text(output)
            logger.error("Джоба %s не завершилась за %s с — примусово зупинено", job_name, exc.timeout)
            notify_failure(job_name, f"timeout ({exc.timeout}с)", output)
            return False

        output = (result.stdout or "") + (result.stderr or "")
        log_path.write_text(output)
        if result.returncode != 0:
            logger.error("Джоба %s провалилась (exit %d)", job_name, result.returncode)
            notify_failure(job_name, f"exit code {result.returncode}", output)
            return False

        logger.info("Джоба %s завершилась успішно", job_name)
        return True

    func = spec["callable"]
    try:
        func()
    except Exception as exc:  # noqa: BLE001 — навмисно широкий catch, той самий підхід, що collect_all.py
        log_path.write_text(f"{exc!r}\n")
        logger.error("Джоба %s провалилась: %s", job_name, exc, exc_info=True)
        notify_failure(job_name, str(exc), "")
        return False

    log_path.write_text("OK\n")
    logger.info("Джоба %s завершилась успішно", job_name)
    return True
