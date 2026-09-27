"""
Спільний HTTP-хелпер для надсилання повідомлень у Telegram — виніс із
telegram_notify.py/news_notify.py (мали буквально ідентичну функцію),
щоб orchestration/alerts.py міг перевикористати той самий код замість
третьої копії.
"""

import requests

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram_message(token: str, chat_id: str, text: str) -> dict:
    url = TELEGRAM_API_URL.format(token=token)
    response = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=15)
    response.raise_for_status()
    return response.json()
