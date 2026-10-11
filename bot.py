import os, sys, html, datetime, requests

TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
CHANNEL = os.environ.get("CHANNEL", "@patmutyun_aysor")
PREVIEW = os.environ.get("PREVIEW_CHAT", "")
TEST    = os.environ.get("TEST", "1")
TZ      = datetime.timezone(datetime.timedelta(hours=4))

TITLE  = "Այս օրը պատմության մեջ"
HANDLE = "@" + CHANNEL.lstrip("@")
MONTHS = ["հունվարի", "փետրվարի", "մարտի", "ապրիլի", "մայիսի", "հունիսի",
          "հուլիսի", "օգոստոսի", "սեպտեմբերի", "հոկտեմբերի", "նոյեմբերի", "դեկտեմբերի"]

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
    txt = html.escape(tr((e.get("text") or "").strip(), lang))
    y = e.get("year")
    if isinstance(y, int):
        y = f"մ.թ.ա. {abs(y)}" if y < 0 else str(y)
        return f"• {y} — {txt}"
    return f"• {txt}"

def section(name, items, lang):
    return [f"<b>{name}</b>"] + [fmt(e, lang) for e in items]

def render(head, blocks):
    lines = list(head)
    for b in blocks:
        lines += ["", *b]
    lines += ["", HANDLE]
    return "\n".join(lines)

def fit(head, blocks, limit=1024):
    while True:
        live = [b for b in blocks if len(b) > 1]
        text = render(head, live)
        if len(text) <= limit:
            return text
        cut = False
        for b in reversed(live):
            if len(b) > 1:
                b.pop()
                cut = True
                break
        if not cut:
            return text

def image_of(data):
    for kind in ("selected", "births", "deaths"):
        for e in data.get(kind, []):
            for p in (e.get("pages") or []):
                src = (p.get("thumbnail") or {}).get("source") or ""
                if src and not src.lower().endswith(".svg"):
                    return src
    return None

def send(text, photo, chat):
    if photo:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
                          json={"chat_id": chat, "photo": photo, "caption": text,
                                "parse_mode": "HTML"}, timeout=60)
        if r.ok:
            print("photo: ok")
            return True
        print("photo fail:", r.text[:200])
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      json={"chat_id": chat, "text": text, "parse_mode": "HTML",
                            "disable_web_page_preview": True}, timeout=30)
    print("telegram:", r.status_code, r.text[:200])
    return r.ok

def main():
    now = datetime.datetime.now(TZ)
    m, d = now.month, now.day
    plan = (("selected", 4), ("births", 2), ("deaths", 2), ("holidays", 2))

    lang = "hy"
    data = {k: pick(get(lang, k, m, d), n) for k, n in plan}
    if not data["selected"]:
        lang = "ru"
        data = {k: pick(get(lang, k, m, d), n) for k, n in plan}
    if not data["selected"]:
        print("Ֆիդը դատարկ է")
        sys.exit(1)

    head = [f"<b>{TITLE}</b>", f"{d} {MONTHS[m-1]}"]
    blocks = []
    if data["selected"]:
        blocks.append(section("Իրադարձություններ", data["selected"], lang))
    if data["births"]:
        blocks.append(section("Ծնունդներ", data["births"], lang))
    if data["deaths"]:
        blocks.append(section("Մահեր", data["deaths"], lang))
    if data["holidays"]:
        blocks.append(section("Տոներ", data["holidays"], lang))

    text = fit(head, blocks)
    photo = image_of(data)

    if TEST == "0":
        send(text, photo, CHANNEL)
    elif TEST == "2" and PREVIEW:
        send(text, photo, PREVIEW)
    else:
        print("--- TEST ---")
        print(text)
        print("photo:", photo)

if __name__ == "__main__":
    main()
