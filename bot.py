import os, sys, re, html, time, datetime, requests

TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
CHANNEL = os.environ.get("CHANNEL", "@patmutyun_aysor")
PREVIEW = os.environ.get("PREVIEW_CHAT", "")
TEST    = os.environ.get("TEST", "0")
TZ      = datetime.timezone(datetime.timedelta(hours=4))

HANDLE = "@" + CHANNEL.lstrip("@")
MONTHS = ["հունվարի", "փետրվարի", "մարտի", "ապրիլի", "մայիսի", "հունիսի",
          "հուլիսի", "օգոստոսի", "սեպտեմբերի", "հոկտեմբերի", "նոյեմբերի", "դեկտեմբերի"]

WIKI  = "https://hy.wikipedia.org/w/api.php"
FEED  = "https://api.wikimedia.org/feed/v1/wikipedia/%s/onthisday/%s/%d/%d"
HEADS = {"Դեպքեր": "Իրադարձություններ", "Իրադարձություններ": "Իրադարձություններ",
         "Ծնունդներ": "Ծնունդներ", "Մահեր": "Մահեր", "Տոներ": "Տոներ"}
YEAR  = re.compile(r"\b(1[0-9]{3}|20[0-2][0-9])\b")
UA    = {"User-Agent": "aysor-bot/1.0"}

def wikitext(title):
    try:
        r = requests.get(WIKI, params={"action": "parse", "page": title,
                                       "prop": "wikitext", "format": "json",
                                       "formatversion": "2"},
                         headers=UA, timeout=30)
        if r.status_code != 200:
            print("wiki status:", r.status_code)
            return ""
        return (r.json().get("parse") or {}).get("wikitext") or ""
    except Exception as e:
        print("wiki error:", e)
        return ""

def clean(s):
    """Տողից դուրս է հանում հղումները, կաղապարները և ձևավորումները։

    Պատկերների հղումները դեն են նետվում ամբողջովին, որովհետև դրանց մեջ
    «thumb»-ը, չափսը («157x157px») և ներքին պարամետրեր են լինում, որոնք
    հին տարբերակում ընկնում էին տեքստի մեջ։ Կաղապարները հանվում են
    շերտ առ շերտ, որ ներդրվածներն էլ մաքրվեն, իսկ դրանց մեջ գտնված
    թվականը պահվում է, որ տողը տարեթիվ չկորցնի։
    """
    s = re.sub(r"\[\[(?:Պատկեր|Ֆայլ|File|Image)\s*:[^\]]*\]\]", "", s, flags=re.I)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"<ref.*?</ref>", "", s, flags=re.S)
    kept = []
    def drop(m):
        if not isinstance(m, str):
            y = YEAR.search(m.group(0))
            if y:
                kept.append(y.group(1))
            return ""
        return ""
    for _ in range(30):
        new = re.sub(r"\{\{[^{}]*\}\}", drop, s)
        if new == s:
            break
        s = new
    s = re.sub(r"\{\{[^{}]*$", "", s)
    s = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"'''?", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\b(?:thumb|thumbnail|mini|frame|border|right|left|center|upright|\d+\s*x\s*\d+\s*px)\b", "", s)
    s = re.sub(r"\s*\|+\s*", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" ,;|:")
    if kept and not YEAR.search(s):
        s = kept[0] + " — " + s
    s = re.sub(r"\s+[–-]\s+", " — ", s)
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
    try:
        r = requests.get(FEED % (lang, kind, m, d), headers=UA, timeout=30)
        if r.status_code != 200:
            print("feed %s %s:" % (lang, kind), r.status_code)
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

def with_year(e, txt):
    y = e.get("year")
    if isinstance(y, int):
        y = ("մ.թ.ա. %d" % abs(y)) if y < 0 else str(y)
        return "%s — %s" % (y, txt)
    return txt

def events_from_feed(m, d):
    """Պահուստային աղբյուր՝ միայն եթե հայերեն էջում իրադարձություններ չկան։

    Նախ հայերենի feed-ը՝ առանց թարգմանության, և միայն եթե այն դատարկ է՝
    ռուսերենը՝ թարգմանությամբ։
    """
    out = [with_year(e, clean((e.get("text") or "").strip()))
           for e in feed("hy", "selected", m, d)]
    if out:
        return out
    return [with_year(e, clean(tr((e.get("text") or "").strip())))
            for e in feed("ru", "selected", m, d)]

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
    ok = False
    try:
        ok = bool(r.json().get("ok"))
    except Exception:
        ok = False
    if not ok:
        print("telegram:", r.status_code, r.text[:200])
    return ok

def main():
    now = datetime.datetime.now(TZ)
    m, d = now.month, now.day

    title = f"{MONTHS[m - 1]} {d}"
    sec = parse_sections(wikitext(title))
    print("էջ:", title, "| բաժիններում տողեր:",
          {k: len(v) for k, v in sec.items()})

    ev = sec.get("Իրադարձություններ") or events_from_feed(m, d)
    print("իրադարձություններ:", "վիքիից" if sec.get("Իրադարձություններ") else "feed-ից",
          len(ev))

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
    head  = (f"{d} {MONTHS[m - 1]} — տարվա {yday}-րդ օրն է։\n"
             f"Տարվա ավարտին մնում է {total - yday} օր։")

    msgs = pack(head, blocks)
    print("հաղորդագրությունների քանակը:", len(msgs))

    sent = True
    if TEST == "0":
        for i, text in enumerate(msgs):
            sent = send(text, CHANNEL) and sent
            if i < len(msgs) - 1:
                time.sleep(3)
    elif TEST == "2" and PREVIEW:
        for i, text in enumerate(msgs):
            sent = send(text, PREVIEW) and sent
            if i < len(msgs) - 1:
                time.sleep(3)
    else:
        for text in msgs:
            print("--- TEST ---")
            print(text, "\n")

    if not sent:
        sys.exit(1)

if __name__ == "__main__":
    main()
