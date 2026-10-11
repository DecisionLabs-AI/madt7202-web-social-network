"""MADT 7202 midterm - data collection (stdlib only, ~5,000 API units).

Step 1  Demand-side keyword set: TH mostPopular (overall + every category),
        tags used by >=3 DISTINCT channels -> top 40 (rule fixed before results).
Step 2  search.list per keyword, regionCode=TH, last ~90 days, top-50.
Step 3  videos.list + channels.list metadata.
Step 4  candidate True-family channel ids (verified manually later).
Output: data/fresh/*.json (the 11 Oct 2026 snapshot in data/ is never overwritten)
Run:    YOUTUBE_API_KEY=... python src/collect.py   (or put YOUTUBE_API_KEY=... in a .env at the repo root)
Note:   search rankings change daily, so a fresh pull will not reproduce the report's numbers;
        use data/ (the snapshot) with src/pipeline.py for that.
"""
import json, os, re, sys, time, urllib.parse, urllib.request, collections, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "fresh"; DATA.mkdir(parents=True, exist_ok=True)
ENV = ROOT / ".env"
KEY = os.environ.get("YOUTUBE_API_KEY")
if not KEY and ENV.exists():
    for line in ENV.read_text().splitlines():
        if line.strip().startswith("YOUTUBE_API_KEY="):
            KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
if not KEY:
    sys.exit("YOUTUBE_API_KEY not found")

BASE = "https://www.googleapis.com/youtube/v3/"
UNITS = 0
def api(ep, cost=1, **p):
    global UNITS
    p["key"] = KEY
    url = BASE + ep + "?" + urllib.parse.urlencode(p)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                UNITS += cost
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="ignore")[:300]
            if e.code in (400, 404):
                return {"_error": e.code, "_body": body}
            if e.code == 403:
                sys.exit(f"403 from API (quota/key?): {body}")
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return {"_error": "failed"}

def save(name, obj):
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1))

NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
AFTER = (NOW - dt.timedelta(days=90)).isoformat().replace("+00:00", "Z")
BEFORE = NOW.isoformat().replace("+00:00", "Z")

# ---------- Step 1: trending + categories ----------
print("Step 1: trending TH")
cats = api("videoCategories", part="snippet", regionCode="TH", hl="th")
save("categories.json", cats)
trending = {}
def pull_popular(cat=None):
    token, n = None, 0
    while True:
        p = dict(part="snippet,statistics", chart="mostPopular", regionCode="TH", maxResults=50)
        if cat: p["videoCategoryId"] = cat
        if token: p["pageToken"] = token
        r = api("videos", **p)
        if "_error" in r: return n
        for v in r.get("items", []):
            v["_trend_cat"] = cat or "all"
            trending.setdefault(v["id"], v); n += 1
        token = r.get("nextPageToken")
        if not token or cat: return n   # overall: up to 200; per category: top 50
pull_popular()
for c in cats.get("items", []):
    if c["snippet"].get("assignable"):
        pull_popular(c["id"])
save("trending.json", list(trending.values()))
print(f"  trending videos: {len(trending)}")

STOP = {"shorts","short","viral","trending","fyp","foryou","youtube","video","tiktok","thailand","ไทย",
        "2025","2026","new","clip","คลิป","ล่าสุด","hd","official","live","ไลฟ์","ep","full"}
def norm(t): return re.sub(r"\s+", " ", t.lower().lstrip("#").strip())
tag_channels = collections.defaultdict(set)
for v in trending.values():
    sn = v["snippet"]; ch = norm(sn.get("channelTitle", ""))
    for t in sn.get("tags", []) or []:
        t = norm(t)
        if len(t) < 2 or t in STOP or t.isdigit(): continue
        if ch and (t == ch or t in ch or ch in t): continue      # self-branding tag
        tag_channels[t].add(sn["channelId"])
ranked = sorted(((t, len(c)) for t, c in tag_channels.items() if len(c) >= 3), key=lambda x: -x[1])
keywords = [t for t, _ in ranked[:40]]
save("keywords.json", {"rule": "tags on TH mostPopular used by >=3 distinct channels, self-brand & stopwords removed, top 40 by distinct-channel count",
                       "ranked": ranked[:80], "selected": keywords})
print(f"  keywords selected: {len(keywords)} -> {keywords[:10]} ...")
if len(keywords) < 15:
    print("  WARNING: few keywords; check keywords.json")

# ---------- Step 2: search ----------
print(f"Step 2: search ({AFTER[:10]} .. {BEFORE[:10]})")
results = []
for i, kw in enumerate(keywords, 1):
    r = api("search", cost=100, part="snippet", q=kw, type="video", regionCode="TH",
            relevanceLanguage="th", publishedAfter=AFTER, publishedBefore=BEFORE,
            order="relevance", maxResults=50)
    items = r.get("items", []) if "_error" not in r else []
    for rank, it in enumerate(items, 1):
        results.append({"keyword": kw, "rank": rank, "videoId": it["id"].get("videoId"),
                        "channelId": it["snippet"]["channelId"], "channelTitle": it["snippet"]["channelTitle"],
                        "publishedAt": it["snippet"]["publishedAt"], "title": it["snippet"]["title"]})
    print(f"  [{i}/{len(keywords)}] {kw}: {len(items)}")
save("search_results.json", {"published_after": AFTER, "published_before": BEFORE, "collected_at": BEFORE, "rows": results})

# ---------- Step 3: metadata ----------
print("Step 3: video + channel metadata")
vids = sorted({r["videoId"] for r in results if r["videoId"]})
vmeta = []
for i in range(0, len(vids), 50):
    r = api("videos", part="snippet,statistics,contentDetails", id=",".join(vids[i:i+50]))
    vmeta += r.get("items", [])
save("videos.json", vmeta)
chs = sorted({r["channelId"] for r in results} | {v["snippet"]["channelId"] for v in trending.values()})
cmeta = []
for i in range(0, len(chs), 50):
    r = api("channels", part="snippet,statistics,topicDetails", id=",".join(chs[i:i+50]))
    cmeta += r.get("items", [])

# ---------- Step 4: True-family candidates ----------
print("Step 4: True-family channel candidates")
cands = []
for q in ["TrueID", "TNN Online", "True4U", "TrueVisions", "True Plookpanya", "True Music"]:
    r = api("search", cost=100, part="snippet", q=q, type="channel", regionCode="TH", maxResults=5)
    for it in r.get("items", []):
        cands.append({"query": q, "channelId": it["snippet"]["channelId"], "title": it["snippet"]["title"]})
save("true_family_candidates.json", cands)
extra = sorted({c["channelId"] for c in cands} - set(chs))
for i in range(0, len(extra), 50):
    r = api("channels", part="snippet,statistics,topicDetails", id=",".join(extra[i:i+50]))
    cmeta += r.get("items", [])
save("channels.json", cmeta)

print(f"\nDONE. rows={len(results)} videos={len(vmeta)} channels={len(cmeta)} units~{UNITS}")
print(f"Files in: {DATA}")
