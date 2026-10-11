import os, sys, re, html, time, datetime, requests

TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
CHANNEL = os.environ.get("CHANNEL", "@patmutyun_aysor")
PREVIEW = os.environ.get("PREVIEW_CHAT", "")
TEST    = os.environ.get("TEST", "1")
TZ      = datetime.timezone(datetime.timedelta(hours=4))

TITLE  = "Այս օրը պատմության մեջ"
HANDLE = "@" + CHANNEL.lstrip("@")
MONTHS = ["հունվարի", "փետրվարի", "մարտի", "ապրիլի", "մայիսի", "հունիսի",
          "հուլիսի", "օգոստոսի", "սեպտեմբերի", "հոկտեմբերի", "նոյեմբերի", "դեկտեմբերի"]

WIKI  = "https://hy.wikipedia.org/w/api.php"
HEADS = {"Դեպքեր": "Իրադարձություններ", "Ծնունդներ": "Ծնունդներ",
         "Մահեր": "Մահեր", "Տոներ": "Տոներ"}

def wikitext(title):
    try:
        r = requests.get(WIKI, params={"action": "parse", "page": title,
                                       "prop": "wikitext", "format": "json",
                                       "formatversion": "2"},
                         headers={"User-Agent": "aysor-bot/1.0"}, timeout=30)
        if r.status_code != 200:
            return ""
        return (r.json().get("parse") or {}).get("wikitext") or ""
    except Exception as e:
        print("wiki error:", e)
        return ""

def clean(s):
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"<ref.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"'''?", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s[–-]\s", " — ", s, count=1)
    return html.escape(s)

def parse_sections(text):
    out, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"^\s*==+\s*([^=]+?)\s*==+\s*$", line)
        if m:
            cur = HEADS.get(m.group(1).strip())
            if cur:
                out.setdefault(cur, [])
            continue
        if cur and line.strip().startswith("*"):
            item = clean(line.strip().lstrip("*").strip())
            if item:
                out[cur].append(item)
    return out

def feed(lang, kind, m, d):
    url = (f"https://api.wikimedia.org/feed/v1/wikipedia/{lang}"
           f"/onthisday/{kind}/{m}/{d}")
    try:
        r = requests.get(url, headers={"User-Agent": "aysor-bot/1.0"}, timeout=30)
        if r.status_code != 200:
            return []
        items = r.json().get(kind) or []
    except Exception as e:
        print("feed error:", e)
        return []
    items = [e for e in items if (e.get("text") or "").strip()]
    items.sort(key=lambda e: len(e.get("pages") or []), reverse=True)
    return items[:6]

def tr(text):
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

def events_from_feed(m, d):
    out = []
    for e in feed("ru", "selected", m, d):
        txt = clean(tr((e.get("text") or "").strip()))
        y = e.get("year")
        if isinstance(y, int):
            y = f"մ.թ.ա. {abs(y)}" if y < 0 else str(y)
            out.append(f"{y} — {txt}")
        else:
            out.append(txt)
    return out

def pack(head, blocks, limit=4000):
    msgs, cur = [], head + "\n\n"
    for name, items in blocks:
        for ln in [f"<b>{name}</b>"] + [f"• {i}" for i in items]:
            if len(cur) + len(ln) + 1 > limit:
                msgs.append(cur.strip())
                cur = ""
            cur += ln + "\n"
        cur += "\n"
    if cur.strip():
        msgs.append(cur.strip())
    if not msgs:
        return []
    if len(msgs[-1]) + len(HANDLE) + 2 <= limit:
        msgs[-1] += "\n\n" + HANDLE
    else:
        msgs.append(HANDLE)
    return msgs

def send(text, chat):
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      json={"chat_id": chat, "text": text, "parse_mode": "HTML",
                            "disable_web_page_preview": True}, timeout=30)
    print("telegram:", r.status_code, r.text[:200])
    return r.ok

def main():
    now = datetime.datetime.now(TZ)
    m, d = now.month, now.day

    sec = parse_sections(wikitext(f"Հոկտեմբերի {d}"))
    ev = events_from_feed(m, d)

    blocks = []
    if ev:
        blocks.append(("Իրադարձություններ", ev))
    for name in ("Ծնունդներ", "Մահեր", "Տոներ"):
        if sec.get(name):
            blocks.append((name, sec[name]))

    if not blocks:
        print("Տվյալ չկա")
        sys.exit(1)

    yday  = now.timetuple().tm_yday
    total = datetime.date(now.year, 12, 31).timetuple().tm_yday
    head  = (f"<b>{TITLE}</b>\n"
             f"{d} {MONTHS[m-1]} — տարվա {yday}-րդ օրն է։\n"
             f"Տարվա ավարտին մնում է {total - yday} օր։")

    msgs = pack(head, blocks)
    print("հաղորդագրությունների քանակը:", len(msgs))

    if TEST == "0":
        for i, text in enumerate(msgs):
            send(text, CHANNEL)
            if i < len(msgs) - 1:
                time.sleep(3)
    elif TEST == "2" and PREVIEW:
        for i, text in enumerate(msgs):
            send(text, PREVIEW)
            if i < len(msgs) - 1:
                time.sleep(3)
    else:
        for text in msgs:
            print("--- TEST ---")
            print(text, "\n")

if __name__ == "__main__":
    main()
