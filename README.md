# Which external creators should TrueID pilot to test comedy and movie-recap expansion?

MADT 7202 Web and Social Network Analytics · Mid-term applied case (NIDA)

The report is [`report/MADT7202_Midterm_TrueID_Creators.pdf`](report/). This repository holds the data and code
that produce every number, table and the figure in it.

## Question

Which two YouTube creators from outside the True group should TrueID bring into a six-week pilot?
A view ranking scores creators one by one; the question is which creators rank in search-intent
neighbourhoods adjacent to those where True-owned channels are visible, which only a graph shows.

## Data

| | |
|---|---|
| Source | YouTube Data API v3 (official, Terms of Service). Public video and channel metadata only; no comments, personal data or TrueID internal data |
| Keywords | 40 tags used by ≥ 3 distinct channels on Thailand trending (overall and every category), self-brand tags and platform words removed. Rule fixed before seeing results |
| Search | Each keyword: `regionCode=TH`, `relevanceLanguage=th`, top 50, videos published 13 Jul – 11 Oct 2026 |
| Snapshot | Collected 11 Oct 2026: 2,000 search rows, 1,697 videos, 1,294 channels (`data/`) |

Daily re-pulls of the same 40 keywords (`src/collect_daily.py`, 11–14 Oct) are in `data/daily/` and test
whether the result holds over time. Search rankings change daily, so the analysis runs on saved snapshots. `src/collect.py` shows how it was
collected; a fresh pull writes to `data/fresh/` and will not reproduce the report exactly.

## Method

1. Keep Thai-title results in each keyword's top 25; drop keywords with < 10 such results → 34 keywords, 836 slots.
2. **Base graph:** keyword nodes; an edge means two keywords share top-25 channels, weighted by the Jaccard
   index of their channel sets (raw shared counts over-weight generic keywords such as "สนุก").
   Louvain communities, seed 1.
3. **Bridge creators:** rank in ≥ 1 keyword where a True-owned channel ranks and ≥ 1 where none does;
   ordered by keywords, True-visible keywords, communities (all descending). easy boy's two channels are
   merged (easy boy X2 describes itself as the side channel); broadcasters and rival platforms are excluded.
4. **Robustness:** re-uploads deduplicated, without "สนุก", ≥ 2 and ≥ 3 videos per creator–keyword edge,
   leave-one-video-out, anchor removal (each True-owned result, then both uploads of the True4U film),
   and top-10 / top-50 windows against the top-25 base.
6. **Stability over time:** the whole graph and bridge ranking re-run on every daily snapshot
   (`results/daily_stability.csv`). The ≥ 80%-of-snapshots bar, the anchor, window and channel-merge tests,
   and the exclusion of TVB Thailand (a broadcaster that surfaced on 13 Oct) were added after first results.
5. **Scenarios:** Baseline counts True-owned channels only; Scenario A also counts OSx Network creators
   zbing z. and SpriteDer SPD, whose channel descriptions list True Digital / Online Station contacts.

## Run

```bash
pip install -r requirements.txt
python src/pipeline.py        # ~1 min; writes results/ and figures/network.png
```

The figure needs a Thai-capable font (Thonburi on macOS, or Loma / Noto Sans Thai on Linux).

## Where each number in the report comes from

| Report | File |
|---|---|
| 34 keywords, 105 edges, 836 slots, 8 communities, Q = 0.577 | `results/summary.json` |
| True-owned 5 of 836 slots; 77 with zbing z. and SPD | `results/summary.json` |
| Comedy–movie recap Jaccard 0.57; News–Storytelling 0.33 | `results/summary.json` |
| "สนุก" centrality, raw count vs Jaccard | `results/weighting_raw_vs_jaccard.csv` |
| Community sizes and views (figure labels) | `results/communities.csv` |
| Top five creators by views, OSx flag | `results/top5_by_views.csv` |
| Bridge ranking and every robustness test (incl. anchor removal, windows), Baseline and A | `results/robustness.csv`, `results/bridges_baseline.csv` |
| Keywords and communities of easy boy, Nof studio, เรียงเรื่องลั่น, พ่อลูกเล่นเกม | `results/shortlist_detail.csv` |
| Daily stability: easy boy #1 in 4/5 snapshots (5/5 with OSx), Nof studio a bridge in 3/5 | `results/daily_stability.csv`, `results/summary.json` |
| Section 5 figure | `figures/network.png` |

## Layout

```
data/        11 Oct 2026 API snapshot (JSON); data/daily/ daily re-pulls
src/         collect.py, collect_daily.py (data pulls), pipeline.py (analysis), figure.py (section 5 figure)
scripts/     install_daily_cron.py
results/     CSV and JSON outputs of pipeline.py
figures/     network.png
report/      the one-page report (PDF)
```

## Limitations

Search results only (not Home or Recommended feeds); a one-day ranking that favours recent uploads; co-ranking
is not a shared audience; group affiliation is read from public channel descriptions, so private MCN contracts
are not observed.
