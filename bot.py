import os, sys, time, html, datetime, requests

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

def tr(text, lang):
    if lang == "hy":
        return text
    try:
        r = requests.get("https://translate.googleapis.com/translate_a/single",
                         params={"client": "gtx", "sl": "ru", "tl": "hy",
                                 "dt": "t", "q": text}, timeout=20)
        if r.status_code == 200:
            out = "".join(p[0] for p in r.json()[0] if p and p[0])
            if out.strip():
                return out
    except Exception as e:
        print("translate error:", e)
    return text

def fmt(e, lang):
    y = e.get("year")
    y = (f"մ.թ.ա. {abs(y)}" if y < 0 else str(y)) if isinstance(y, int) else ""
    return f"• {y} — {html.escape(tr(e['text'].strip(), lang))}"

def block(title, items, m, d, lang):
    lines = [f"<b>{title}</b> — {d} {MONTHS[m-1]}", ""]
    lines += [fmt(e, lang) for e in items]
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
    plan = (("selected", 5), ("births", 3), ("deaths", 3))

    lang = "hy"
    data = {k: pick(get(lang, k, m, d), n) for k, n in plan}
    if not data["selected"]:
        lang = "ru"
        data = {k: pick(get(lang, k, m, d), n) for k, n in plan}

    if not data["selected"]:
        print("Ֆիդը դատարկ է, ոչինչ չուղարկվեց")
        sys.exit(1)

    parts = [block("Իրադարձություններ", data["selected"], m, d, lang)]
    if data["births"]:
        parts.append(block("Ծնունդներ", data["births"], m, d, lang))
    if data["deaths"]:
        parts.append(block("Մահեր", data["deaths"], m, d, lang))

    for i, text in enumerate(parts):
        if TEST:
            print("--- TEST ---")
            print(text, "\n")
        else:
            send(text)
            if i < len(parts) - 1:
                time.sleep(300)

if __name__ == "__main__":
    main()
