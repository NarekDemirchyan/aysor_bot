import os, sys, time, datetime, requests

TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
CHANNEL = os.environ.get("CHANNEL", "@patmutyun_aysor")
TEST    = os.environ.get("TEST", "1") == "1"
TZ      = datetime.timezone(datetime.timedelta(hours=4))

MONTHS = ["հունվարի","փետրվարի","մարտի","ապրիլի","մայիսի","հունիսի",
          "հուլիսի","օգոստոսի","սեպտեմբերի","հոկտեմբերի","նոյեմբերի","դեկտեմբերի"]

def get(lang, kind, m, d):
    url = (f"https://api.wikimedia.org/feed/v1/wikipedia/{lang}"
           f"/onthisday/{kind}/{m}/{d}")
    try:
        r = requests.get(url, headers={"User-Agent": "aysor-bot/1.0"}, timeout=30)
        if r.status_code != 200:
            return []
        return r.json().get(kind) or []
    except Exception as e:
        print("feed error:", e)
        return []

def pick(items, n):
    items = [e for e in items if (e.get("text") or "").strip()]
    items.sort(key=lambda e: len(e.get("pages") or []), reverse=True)
    return items[:n]

def fmt(e):
    y = e.get("year")
    if isinstance(y, int):
        y = f"մ.թ.ա. {abs(y)}" if y < 0 else str(y)
    else:
        y = ""
    return f"• {y} — {e['text'].strip()}"

def block(title, items, m):
    lines = [f"<b>{title}</b> — {m} {MONTHS[m-1]}", ""]
    lines += [fmt(e) for e in items]
    lines += ["", f"📓 https://t.me/{CHANNEL.lstrip('@')}"]
    return "\n".join(lines)

def send(text):
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      json={"chat_id": CHANNEL, "text": text,
                            "parse_mode": "HTML",
                            "disable_web_page_preview": True},
                      timeout=30)
    print("telegram:", r.status_code, r.text[:200])
    return r.ok

def main():
    now = datetime.datetime.now(TZ)
    m, d = now.month, now.day
    lang = "hy"

    events = pick(get(lang, "selected", m, d), 5)
    births = pick(get(lang, "births", m, d), 3)
    deaths = pick(get(lang, "deaths", m, d), 3)

    if not events:
        lang = "ru"
        events = pick(get(lang, "selected", m, d), 5)
        births = pick(get(lang, "births", m, d), 3)
        deaths = pick(get(lang, "deaths", m, d), 3)

    if not events:
        print("Ֆիդը դատարկ է, ոչինչ չուղարկվեց")
        sys.exit(1)

    parts = [block("Իրադարձություններ", events, m)]
    if births: parts.append(block("Ծնունդներ", births, m))
    if deaths: parts.append(block("Մահեր", deaths, m))

    for i, text in enumerate(parts):
        if TEST:
            print("--- TEST, չուղարկվեց ---")
            print(text, "\n")
        else:
            send(text)
            if i < len(parts) - 1:
                time.sleep(300)

if __name__ == "__main__":
    main()
