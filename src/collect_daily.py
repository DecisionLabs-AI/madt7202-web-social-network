"""Daily re-pull of the 11 Oct 2026 keyword set, to test whether the result holds over time.

Same 40 keywords (data/keywords.json, fixed), same settings as src/collect.py:
regionCode=TH, relevanceLanguage=th, type=video, order=relevance, top 50,
videos published in the 90 days before the pull. No trending pull (keywords stay fixed).

Writes data/daily/YYYY-MM-DD/{search_results,videos,channels}.json (Bangkok date).
Idempotent: if today's folder is complete, it exits without calling the API,
so cron can try every hour and only the first successful run of the day counts.
Cost: about 4,100 API units per day.

Run: python3 src/collect_daily.py
Key: YOUTUBE_API_KEY env var, or .env at the repo root, or the trend-monitor .env next to this repo.
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BKK = dt.timezone(dt.timedelta(hours=7))
TODAY = dt.datetime.now(BKK).date().isoformat()
OUT = ROOT / "data" / "daily" / TODAY
FILES = ("search_results.json", "videos.json", "channels.json")


def log(msg):
    print(f"[{dt.datetime.now(BKK):%Y-%m-%d %H:%M}] {msg}", flush=True)


if all((OUT / f).exists() for f in FILES):
    log(f"{TODAY} already collected, skipping")
    sys.exit(0)


def find_key():
    if os.environ.get("YOUTUBE_API_KEY"):
        return os.environ["YOUTUBE_API_KEY"]
    for env in (ROOT / ".env", ROOT.parent / "scrape-web" / "youtube-content-trend-monitor" / ".env"):
        if env.exists():
            for line in env.read_text().splitlines():
                if line.strip().startswith("YOUTUBE_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("YOUTUBE_API_KEY not found")


KEY = find_key()
BASE = "https://www.googleapis.com/youtube/v3/"


def api(endpoint, **params):
    params["key"] = KEY
    url = BASE + endpoint + "?" + urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="ignore")[:300]
            if e.code == 403:  # quota or key problem: stop, cron will retry next hour
                log(f"403 from API, stopping: {body}")
                sys.exit(1)
            if e.code in (400, 404):
                return {"_error": e.code}
        except Exception as e:  # network blip (e.g. Mac just woke up)
            log(f"network error: {e}")
        time.sleep(5 * (attempt + 1))
    log("API unreachable, stopping; cron will retry next hour")
    sys.exit(1)


keywords = json.load(open(ROOT / "data" / "keywords.json"))["selected"]
now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
after = (now - dt.timedelta(days=90)).isoformat().replace("+00:00", "Z")
before = now.isoformat().replace("+00:00", "Z")

log(f"collecting {len(keywords)} keywords for {TODAY}")
rows = []
for kw in keywords:
    r = api("search", part="snippet", q=kw, type="video", regionCode="TH", relevanceLanguage="th",
            publishedAfter=after, publishedBefore=before, order="relevance", maxResults=50)
    for rank, it in enumerate(r.get("items", []), 1):
        rows.append({"keyword": kw, "rank": rank, "videoId": it["id"].get("videoId"),
                     "channelId": it["snippet"]["channelId"], "channelTitle": it["snippet"]["channelTitle"],
                     "publishedAt": it["snippet"]["publishedAt"], "title": it["snippet"]["title"]})

vids = sorted({x["videoId"] for x in rows if x["videoId"]})
videos = []
for i in range(0, len(vids), 50):
    videos += api("videos", part="snippet,statistics,contentDetails", id=",".join(vids[i:i + 50])).get("items", [])
chans = sorted({x["channelId"] for x in rows})
channels = []
for i in range(0, len(chans), 50):
    channels += api("channels", part="snippet,statistics", id=",".join(chans[i:i + 50])).get("items", [])

if len(rows) < 1000:  # incomplete pull: do not write, retry next hour
    log(f"only {len(rows)} rows, not saving")
    sys.exit(1)

OUT.mkdir(parents=True, exist_ok=True)
json.dump({"published_after": after, "published_before": before, "collected_at": before, "rows": rows},
          open(OUT / "search_results.json", "w"), ensure_ascii=False, indent=1)
json.dump(videos, open(OUT / "videos.json", "w"), ensure_ascii=False)
json.dump(channels, open(OUT / "channels.json", "w"), ensure_ascii=False)
log(f"done: {len(rows)} rows, {len(videos)} videos, {len(channels)} channels -> {OUT}")
