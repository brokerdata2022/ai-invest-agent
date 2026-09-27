"""
Telegram-алерт при провалі джоби. Використовує спільний
reporting/telegram_client.py (той самий хелпер, що telegram_notify.py/
news_notify.py) — не дублює HTTP-виклик утретє.
"""

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reporting"))
from telegram_client import send_telegram_message  # noqa: E402

logger = logging.getLogger(__name__)

_MAX_LOG_CHARS = 1500


def notify_failure(job_name: str, reason: str, log_output: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.error(
            "TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID не задані — алерт про провал %s не надіслано",
            job_name,
        )
        return

    tail = log_output.strip()[-_MAX_LOG_CHARS:] if log_output and log_output.strip() else "(немає виводу)"
    text = f"⚠️ Джоба провалилась: {job_name}\n{reason}\n\n{tail}"
    try:
        send_telegram_message(token, chat_id, text)
    except Exception:
        logger.error("Не вдалось надіслати Telegram-алерт про провал %s", job_name, exc_info=True)
