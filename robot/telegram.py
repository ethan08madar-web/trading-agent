"""Telegram alerts. A failed send is logged and ignored: the notebook is the record (spec §5).

Messages are short cards: a bold title, a blank line, one fact per line, optional grey footer.
Routines send them with:  python -m robot.telegram "📋 Plan ready — 🟢 Green" "**2 picks:** NVDA, CRWD" "" "Why: ..."
(**text** becomes bold; an empty argument is a blank line.)"""
import html
import os
import re
import sys
import urllib.parse
import urllib.request


def card(title, lines, footer=None):
    """HTML for Telegram's parse_mode=HTML. Everything is escaped first, so no text can break the markup."""
    def fmt(s):
        return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(str(s), quote=False))
    out = [f"<b>{html.escape(str(title), quote=False)}</b>", ""] + [fmt(l) for l in lines]
    if footer:
        out += ["", f"<i>{html.escape(str(footer), quote=False)}</i>"]
    return "\n".join(out).strip()


def send(token, chat_id, text, as_html=False):
    if not token or not chat_id:
        print("telegram not configured:", text)
        return False
    fields = {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
    if as_html:
        fields["parse_mode"] = "HTML"
    data = urllib.parse.urlencode(fields).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=15)
        return True
    except Exception as e:  # never crash the Robot over an alert
        print("telegram failed:", type(e).__name__, "|", text)
        return False


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print('usage: python -m robot.telegram "Title" "line" ["line" ...]')
        sys.exit(2)
    ok = send(os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID"),
              card(sys.argv[1], sys.argv[2:]), True)
    print("sent" if ok else "NOT sent")
    sys.exit(0 if ok else 1)
