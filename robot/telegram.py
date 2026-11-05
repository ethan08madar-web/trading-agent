"""Telegram alerts. A failed send is logged and ignored: the notebook is the record (spec §5)."""
import urllib.parse
import urllib.request


def send(token, chat_id, text):
    if not token or not chat_id:
        print("telegram not configured:", text)
        return False
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=15)
        return True
    except Exception as e:  # never crash the Robot over an alert
        print("telegram failed:", type(e).__name__, "|", text)
        return False
