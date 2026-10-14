"""MADT 7202 mid-term: which YouTube creators should TrueID pilot?

Rebuilds every number, table and the figure in the report from data/*.json.

    python src/pipeline.py            # writes results/*.csv, results/summary.json, figures/network.png

Steps
  1. Load the 11 Oct 2026 search snapshot (top 50 per keyword) and keep Thai-title
     results in each keyword's top 25; drop keywords with < 10 Thai results.
  2. Base graph: keyword nodes, edge = the two keywords share top-25 channels,
     weight = Jaccard of their channel sets. Louvain communities (seed 1).
  3. Bridge creators: in >= 1 keyword where a True channel ranks ("True-visible")
     and >= 1 where none does ("gap"); ranked by keywords, True-visible keywords,
     communities (all descending).
  4. Robustness: re-uploads deduplicated, without the generic keyword "สนุก",
     >= 2 / >= 3 videos per creator-keyword edge, leave-one-video-out (creator videos),
     anchor removal (each True-owned result, then both True4U uploads), top-10 / top-50 windows.
  5. Scenarios: Baseline = True-owned channels; A = + OSx Network creators
     zbing z. and SpriteDer SPD (True Digital / Online Station contacts in
     their channel descriptions).
"""
import collections
import itertools
import json
import re
from pathlib import Path

import networkx as nx
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA, RES, FIG = ROOT / "data", ROOT / "results", ROOT / "figures"
RES.mkdir(exist_ok=True)
FIG.mkdir(exist_ok=True)

TOP_N = 25          # co-occurrence window: a keyword's top-25 results
MIN_THAI = 10       # keywords with fewer Thai results in the top 25 are dropped
SEED = 1            # Louvain seed

# True-owned YouTube channels, verified by hand from a channel search
TRUE_OWNED = {
    "UC_8p2lYAy-tdCMnfkRjK-6g": "TrueID", "UCqUBA96OsqMgSFvTwLXY9yw": "TNN",
    "UCu2sn1JnlYkN_XQCeBcKP5A": "True4U", "UCLFem49cKUGGzpZSUu9RhxQ": "TrueVisions",
    "UC8R6hoq-VflJAPQFmOs-hBw": "True Sport Network", "UCjj4VB9nW0zN5reBS0cIf6A": "TruePlookpanya",
    "UCqIggSCCtpJBzwazKli5lEw": "True4U News Online", "UCebZ-JjQNyMKSTfQBS8BIog": "TRUE4U Entertainment",
    "UCLC6NTxtQRyZXayGMxRrDow": "News True4U",
}
# OSx Network (Online Station, True group) creators: business contacts in channel descriptions
OSX = {"UC5zGJZpxeZPFcds5gFcDE7Q": "zbing z.", "UCiHQ5AywCFKF6q-C5dIguVQ": "SpriteDer SPD"}
# One creator, two channels (easy boy X2 describes itself as easy boy's side channel)
EASY_BOY, EASY_BOY_X2 = "UC44a12xQxumXdZnfpK_OBlA", "UCEmNyI4r-ge-YHDQ5NZrT2g"
# Broadcasters, studios and rival platforms: not partner candidates
NOT_CREATORS = {
    "เรื่องเล่าเช้านี้", "ข่าวช่อง8", "WorkpointOfficial", "AMARINTV : อมรินทร์ทีวี", "Thairath News - ข่าวไทยรัฐ",
    "Thai PBS", "ข่าวช่องวัน - one news", "ครอบครัวข่าว3", "iQIYI Movie Thai - Get the iQIYI APP",
    "พระนครฟิลม์ Phranakornfilm", "Sanook.com", "YOUKU พากย์ไทย-โหลดแอปตอนนี้",
    "TVB Thailand",  # added 14 Oct after it appeared in a daily snapshot (broadcaster)
}
COMMUNITY_NAMES = {"มายคราฟ": "Gaming & comedy", "สรุปหนัง": "Movie recap", "ข่าว": "News", "เพลงใหม่": "Music",
                   "เล่าเรื่อง": "Storytelling", "freefire": "Free Fire", "rov": "RoV", "ตกปลา": "Fishing"}
THAI = re.compile("[฀-๿]")


# ---------------------------------------------------------------- load
def load(data_dir=DATA):
    rows = pd.DataFrame(json.load(open(data_dir / "search_results.json"))["rows"])
    videos = json.load(open(data_dir / "videos.json"))
    vdf = pd.DataFrame([{"videoId": v["id"], "views": int(v["statistics"].get("viewCount", 0))} for v in videos])
    channels = json.load(open(data_dir / "channels.json"))
    chdf = pd.DataFrame([{"channelId": c["id"], "title": c["snippet"]["title"],
                          "subs": int(c["statistics"].get("subscriberCount", 0) or 0),
                          "description": c["snippet"].get("description", "")} for c in channels]
                        ).drop_duplicates("channelId").set_index("channelId")
    rows = rows.merge(vdf, on="videoId", how="left")
    rows["thai"] = rows.title.fillna("").map(lambda t: bool(THAI.search(t)))
    return rows, chdf


def corpus(rows, top=TOP_N):
    r = rows[(rows["rank"] <= top) & rows.thai]
    n = r.groupby("keyword").size()
    return r[r.keyword.isin(n[n >= MIN_THAI * top / TOP_N].index)].copy()


# ---------------------------------------------------------------- graph
def keyword_graph(r, weight="jaccard"):
    sets = r.groupby("keyword").channelId.apply(set).to_dict()
    G = nx.Graph()
    G.add_nodes_from(sets)
    for a, b in itertools.combinations(sets, 2):
        inter = len(sets[a] & sets[b])
        if inter:
            w = inter / len(sets[a] | sets[b]) if weight == "jaccard" else inter
            G.add_edge(a, b, weight=w, shared=inter)
    return G


def communities(G):
    com = nx.community.louvain_communities(G, weight="weight", seed=SEED)
    label = {}
    for c in com:
        name = next((COMMUNITY_NAMES[k] for k in COMMUNITY_NAMES if k in c), "/".join(sorted(c)))
        for k in c:
            label[k] = name
    return label, nx.community.modularity(G, com)


def between_community(G, label):
    out = collections.defaultdict(float)
    for a, b, d in G.edges(data=True):
        if label[a] != label[b]:
            out[tuple(sorted((label[a], label[b])))] += d["weight"]
    return dict(out)


# ---------------------------------------------------------------- bridges
def core_title(t):
    t = re.sub(r"[\[\(【].*?[\]\)】]", "", t or "")
    return re.sub(r"\s+", "", re.sub(r"\|.*$", "", t))


def bridges(r, chdf, true_ids, support=1, drop_kw=(), dedup=False, drop_videos=()):
    r = r[~r.keyword.isin(drop_kw) & ~r.videoId.isin(drop_videos)].copy()
    if dedup:  # same title from the same channel in the same keyword = re-upload
        r["core"] = r.title.map(core_title)
        r = r.drop_duplicates(["keyword", "channelId", "core"])
    label, _ = communities(keyword_graph(r))
    true_kw = set(r[r.channelId.isin(true_ids)].keyword)
    e = r[~r.channelId.isin(true_ids)].groupby(["channelId", "keyword"]).videoId.nunique().reset_index()
    e = e[e.videoId >= support]
    e["true_kw"] = e.keyword.isin(true_kw)
    e["comm"] = e.keyword.map(label)
    g = e.groupby("channelId")
    t = pd.DataFrame({"n_kw": g.keyword.nunique(), "true_visible_kw": g.true_kw.sum(), "n_comm": g.comm.nunique()})
    t["gap_kw"] = t.n_kw - t.true_visible_kw
    t = t.join(chdf[["title"]])
    t = t[~t.title.isin(NOT_CREATORS)]
    b = t[(t.true_visible_kw > 0) & (t.gap_kw > 0)]
    return b.sort_values(["n_kw", "true_visible_kw", "n_comm"], ascending=False), true_kw


def rank_of(b, title):
    names = list(b.title)
    return names.index(title) + 1 if title in names else None


# ---------------------------------------------------------------- stability over time
def daily_stability():
    """Re-run the base graph and bridge ranking on every snapshot: data/ plus data/daily/*/."""
    snaps = [("2026-10-11 10:10 (base)", DATA)] + [
        (p.name, p) for p in sorted((DATA / "daily").glob("*")) if (p / "search_results.json").exists()]
    out = []
    for name, path in snaps:
        rows, chdf = load(path)
        r = corpus(rows)
        r.loc[r.channelId == EASY_BOY_X2, "channelId"] = EASY_BOY
        if EASY_BOY in chdf.index:
            chdf.loc[EASY_BOY, "title"] = "easy boy (2 channels)"
        G = keyword_graph(r)
        label, Q = communities(G)
        link = max(between_community(G, label).items(), key=lambda x: x[1])
        for sname, tids in {"Baseline": TRUE_OWNED, "A (+OSx)": {**TRUE_OWNED, **OSX}}.items():
            b, _ = bridges(r, chdf, tids)
            b3, _ = bridges(r, chdf, tids, support=3)
            out.append({"snapshot": name, "scenario": sname, "keywords": G.number_of_nodes(), "edges": G.number_of_edges(),
                        "true_owned_slots": int(r.channelId.isin(TRUE_OWNED).sum()),
                        "true4u_slots": int((r.channelId == "UCu2sn1JnlYkN_XQCeBcKP5A").sum()),
                        "strongest_link": " / ".join(link[0]), "strongest_link_jaccard": round(link[1], 2),
                        "easy_boy_rank": rank_of(b, "easy boy (2 channels)"),
                        "easy_boy_rank_3videos": rank_of(b3, "easy boy (2 channels)"),
                        "nof_studio_rank": rank_of(b, "Nof studio"), "top3": ", ".join(b.title.head(3))})
    return pd.DataFrame(out)


# ---------------------------------------------------------------- main
def main():
    rows, chdf = load()
    r = corpus(rows)
    # merge easy boy's two channels into one creator
    r.loc[r.channelId == EASY_BOY_X2, "channelId"] = EASY_BOY
    chdf.loc[EASY_BOY, "title"] = "easy boy (2 channels)"

    G = keyword_graph(r)
    label, Q = communities(G)
    r["comm"] = r.keyword.map(label)
    summary = {
        "keywords": G.number_of_nodes(), "edges": G.number_of_edges(), "slots": len(r),
        "channels": int(r.channelId.nunique()), "communities": len(set(label.values())), "modularity": round(Q, 3),
        "true_owned_slots": int(r.channelId.isin(TRUE_OWNED).sum()),
        "true_group_slots_with_osx": int(r.channelId.isin({**TRUE_OWNED, **OSX}).sum()),
        "between_community_jaccard": {" / ".join(k): round(v, 2) for k, v in
                                      sorted(between_community(G, label).items(), key=lambda x: -x[1])},
    }

    # weighting: raw shared-channel count vs Jaccard
    ranks = {}
    for w in ("raw", "jaccard"):
        deg = sorted(keyword_graph(r, w).degree(weight="weight"), key=lambda x: -x[1])
        ranks[w] = {k: i + 1 for i, (k, _) in enumerate(deg)}
    pd.DataFrame(ranks).rename_axis("keyword").sort_values("raw").to_csv(RES / "weighting_raw_vs_jaccard.csv")
    summary["rank_of_สนุก"] = {w: ranks[w]["สนุก"] for w in ranks}

    # communities
    u = r.drop_duplicates(["comm", "videoId"])
    comm = pd.DataFrame({
        "keywords": r.groupby("comm").keyword.nunique(),
        "channels": r.groupby("comm").channelId.nunique(),
        "views_M": (u.groupby("comm").views.sum() / 1e6).round(1),
        "true_owned_keywords": r[r.channelId.isin(TRUE_OWNED)].groupby("comm").keyword.nunique(),
    }).fillna(0).sort_values("views_M", ascending=False)
    comm.to_csv(RES / "communities.csv")

    # top-5 creators by views (unique videos)
    v = r[~r.channelId.isin(TRUE_OWNED)].drop_duplicates(["channelId", "videoId"]).groupby("channelId").views.sum()
    top5 = v.sort_values(ascending=False).head(5).to_frame("views").join(chdf[["title"]])
    top5["osx"] = top5.index.isin(OSX)
    top5.to_csv(RES / "top5_by_views.csv")

    # robustness grid, Baseline and Scenario A
    scenarios = {"Baseline": TRUE_OWNED, "A (+OSx)": {**TRUE_OWNED, **OSX}}
    tests = {"base": {}, "re-uploads deduplicated": {"dedup": True}, "without สนุก": {"drop_kw": ["สนุก"]},
             ">=2 videos per edge": {"support": 2}, ">=3 videos per edge": {"support": 3},
             "no สนุก + dedup + >=2": {"drop_kw": ["สนุก"], "dedup": True, "support": 2}}
    grid = []
    for sname, tids in scenarios.items():
        for tname, kw in tests.items():
            b, _ = bridges(r, chdf, tids, **kw)
            grid.append({"scenario": sname, "test": tname, "bridges": len(b), "top4": ", ".join(b.title.head(4)),
                         "easy_boy_rank": rank_of(b, "easy boy (2 channels)"), "nof_studio_rank": rank_of(b, "Nof studio")})
        # leave-one-video-out for the two shortlisted creators
        for title in ("easy boy (2 channels)", "Nof studio"):
            cid = chdf.index[chdf.title == title][0]
            vids = r[r.channelId == cid].videoId.unique()
            kept = [rank_of(bridges(r, chdf, tids, drop_videos=[x])[0], title) for x in vids]
            grid.append({"scenario": sname, "test": f"leave-one-video-out: {title}",
                         "bridges": f"still a bridge in {sum(k is not None for k in kept)}/{len(vids)} runs",
                         "top4": f"worst rank {max(k or 999 for k in kept)}"})
        # anchor sensitivity: remove each True-owned result, then both uploads of the True4U film
        true_videos = list(r[r.channelId.isin(TRUE_OWNED)].videoId.unique())
        true4u = list(r[r.channelId == "UCu2sn1JnlYkN_XQCeBcKP5A"].videoId.unique())
        for name, drop in [(f"anchor removed: {x}", [x]) for x in true_videos] + [("anchor removed: both True4U uploads", true4u)]:
            b, _ = bridges(r, chdf, tids, drop_videos=drop)
            grid.append({"scenario": sname, "test": name, "bridges": len(b), "top4": ", ".join(b.title.head(4)),
                         "easy_boy_rank": rank_of(b, "easy boy (2 channels)"), "nof_studio_rank": rank_of(b, "Nof studio")})
        # co-occurrence window: top 10 / 25 / 50
        for top in (10, 50):
            rw = corpus(rows, top)
            rw.loc[rw.channelId == EASY_BOY_X2, "channelId"] = EASY_BOY
            b, _ = bridges(rw, chdf, tids)
            grid.append({"scenario": sname, "test": f"window top {top} ({rw.keyword.nunique()} keywords)", "bridges": len(b),
                         "top4": ", ".join(b.title.head(4)), "easy_boy_rank": rank_of(b, "easy boy (2 channels)"),
                         "nof_studio_rank": rank_of(b, "Nof studio")})
    pd.DataFrame(grid).to_csv(RES / "robustness.csv", index=False)
    bridges(r, chdf, TRUE_OWNED)[0].to_csv(RES / "bridges_baseline.csv")

    # creator-keyword detail for the shortlist and the higher-ranked comedy alternatives
    detail = []
    for title in ("easy boy (2 channels)", "Nof studio", "เรียงเรื่องลั่น", "พ่อลูกเล่นเกม"):
        cid = chdf.index[chdf.title == title][0]
        for k, n in r[r.channelId == cid].groupby("keyword").videoId.nunique().items():
            detail.append({"creator": title, "keyword": k, "community": label[k], "videos": n,
                           "true_visible": k in set(r[r.channelId.isin(TRUE_OWNED)].keyword)})
    pd.DataFrame(detail).to_csv(RES / "shortlist_detail.csv", index=False)

    # stability across the base snapshot and the daily re-pulls (src/collect_daily.py)
    stab = daily_stability()
    stab.to_csv(RES / "daily_stability.csv", index=False)
    summary["daily_stability"] = {
        "snapshots": len(stab) // 2,
        "easy_boy_rank1": {s: int((g.easy_boy_rank == 1).sum()) for s, g in stab.groupby("scenario")},
        "nof_studio_bridge": {s: int(g.nof_studio_rank.notna().sum()) for s, g in stab.groupby("scenario")},
        "true4u_film_present": int((stab[stab.scenario == "Baseline"].true4u_slots > 0).sum()),
    }
    print(stab.to_string())
    json.dump(summary, open(RES / "summary.json", "w"), ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(pd.DataFrame(grid).to_string())

    from figure import draw
    draw(r, G, label, chdf, TRUE_OWNED, OSX, FIG / "network.png")


if __name__ == "__main__":
    main()
