# telegram_notify.py
import requests
import time

BOT_TOKEN = "8229778196:AAEnT5NiWR6iDBpVLqgVCSTVYrO9jkdhb40"
CHAT_ID = "7085487410"

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Mỗi loại cảnh báo chỉ gửi 1 lần / 60 giây
_last_sent = {}

def can_send(key, cooldown=10):
    now = time.time()
    last = _last_sent.get(key, 0)
    if now - last >= cooldown:
        _last_sent[key] = now
        return True
    return False

def send_text(message):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    requests.post(url, json=payload, timeout=5)

def send_photo(image_path, caption=None):
    url = f"{TELEGRAM_API}/sendPhoto"
    with open(image_path, "rb") as f:
        files = {"photo": f}
        data = {
            "chat_id": CHAT_ID,
            "caption": caption or ""
        }
        requests.post(url, data=data, files=files, timeout=10)
