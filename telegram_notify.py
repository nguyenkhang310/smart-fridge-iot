# telegram_notify.py
import requests
import time

BOT_TOKEN = "8229778196:AAEnT5NiWR6iDBpVLqgVCSTVYrO9jkdhb40"
# Group chat này đã được Telegram nâng cấp lên supergroup,
# nên chat_id mới là bản migrate_to_chat_id mà API trả về.
CHAT_ID = "-1003875721326"

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
    """
    Gửi thông báo text tới Telegram.
    Có log lại status code để dễ debug khi không thấy tin nhắn.
    """
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    try:
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code != 200:
            # In ra console để người dùng kiểm tra lỗi (ví dụ: token sai, chat_id sai, bot chưa được /start)
            print(f"⚠ Telegram send_text failed: {resp.status_code} - {resp.text[:200]}")
        else:
            print("✓ Telegram text sent")
    except Exception as e:
        print(f"⚠ Telegram send_text error: {e}")

def send_photo(image_path, caption=None):
    """
    Gửi ảnh + caption tới Telegram, có log status để debug.
    """
    url = f"{TELEGRAM_API}/sendPhoto"
    try:
        with open(image_path, "rb") as f:
            files = {"photo": f}
            data = {
                "chat_id": CHAT_ID,
                "caption": caption or "",
            }
            resp = requests.post(url, data=data, files=files, timeout=10)
            if resp.status_code != 200:
                print(f"⚠ Telegram send_photo failed: {resp.status_code} - {resp.text[:200]}")
            else:
                print("✓ Telegram photo sent")
    except Exception as e:
        print(f"⚠ Telegram send_photo error: {e}")
