"""Community-level view of the base graph with selected channels overlaid (report section 5)."""
import collections

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

# Thai-capable font: Loma (fonts-thai-tlwg), Thonburi (macOS) or Noto Sans Thai, whichever is installed
for f in fm.findSystemFonts():
    if any(n in f for n in ("Loma", "Thonburi", "NotoSansThai")):
        fm.fontManager.addfont(f)
_installed = {f.name for f in fm.fontManager.ttflist}
plt.rcParams["font.family"] = [n for n in ("Loma", "Thonburi", "Noto Sans Thai") if n in _installed][:1] or ["DejaVu Sans"]

COM = ["Movie recap", "Gaming & comedy", "News", "Storytelling", "Music"]
COL = {"Gaming & comedy": "#2a78d6", "Movie recap": "#1baf7a", "News": "#eda100", "Music": "#e87ba4",
       "Storytelling": "#008300"}
POS = {"Movie recap": (-1.6, 0.35), "Gaming & comedy": (1.0, 0.35), "News": (0.1, -1.25),
       "Storytelling": (-1.55, -1.15), "Music": (2.75, -0.95)}
# (channel id, label, kind, position)
CHANNELS = [
    ("UCu2sn1JnlYkN_XQCeBcKP5A", "True4U", "true", (-0.3, 1.45)),
    ("UCqUBA96OsqMgSFvTwLXY9yw", "TNN", "true", (1.25, -1.6)),
    ("UC44a12xQxumXdZnfpK_OBlA", "easy boy (2 ch.) · Ampverse", "pick", (-0.3, -0.45)),
    ("UCtpK4ekcJUReist_vAffwYQ", "Nof studio", "pick", (-2.8, 1.1)),
    ("UC0iY_2Hy50EpNDj0sTa5YlA", "iQIYI (rival OTT)", "rival", (-1.55, 1.3)),
    ("UCiHQ5AywCFKF6q-C5dIguVQ", "SpriteDer SPD (OSx)", "osx", (2.05, 1.45)),
    ("UC5zGJZpxeZPFcds5gFcDE7Q", "zbing z. (OSx)", "osx", (2.6, 0.75)),
    ("UCKkM8e__oSAZzdcRVFu3Ztw", "iboom music", "big", (3.55, 0.1)),
    ("UCtqBOzg93aIu8V-VgjRdWnA", "SERNG MUSiC", "big", (4.05, -1.5)),
    ("UCtRzHaTQnfacmDUITEQbgxQ", "แจ๊ส สปุ๊กนิคฯ", "big", (3.95, -0.85)),
]
LINE = {"true": "#1b1b1b", "pick": "#eb6834", "rival": "#8a4fd1", "big": "#9a9a9a", "osx": "#555555"}
TEXT = {"true": "#111", "pick": "#a8401a", "rival": "#5f2fa3", "big": "#666", "osx": "#333"}
MARK = {"true": dict(marker="s", color="#1b1b1b", s=170), "pick": dict(marker="D", color="#eb6834", s=190),
        "rival": dict(marker="s", color="#8a4fd1", s=150),
        "big": dict(marker="s", facecolor="white", edgecolor="#8a8a8a", s=140),
        "osx": dict(marker="s", facecolor="#9a9a9a", edgecolor="#1b1b1b", s=150)}


def draw(r, G, label, chdf, true_owned, osx, path):
    r = r.assign(comm=r.keyword.map(label))
    true_kw = set(r[r.channelId.isin(true_owned)].keyword)
    u = r.drop_duplicates(["comm", "videoId"])
    views = u.groupby("comm").views.sum() / 1e6
    nk = r.groupby("comm").keyword.nunique()
    ntrue = r[r.keyword.isin(true_kw)].groupby("comm").keyword.nunique()
    between = collections.defaultdict(float)
    for a, b, d in G.edges(data=True):
        if label[a] != label[b] and label[a] in COM and label[b] in COM:
            between[tuple(sorted((label[a], label[b])))] += d["weight"]

    fig, ax = plt.subplots(figsize=(11, 5.6), dpi=200)
    ax.set_axis_off()
    for (a, b), w in between.items():
        if w < 0.1:
            continue
        ax.plot(*zip(POS[a], POS[b]), color="#c4c8ce", lw=1 + 14 * w, zorder=1, solid_capstyle="round")
        if w > 0.3:
            m = np.mean([POS[a], POS[b]], axis=0)
            ax.text(m[0], m[1] + 0.12, f"Jaccard {w:.2f}", ha="center", fontsize=13.1, color="#666")
    for cid, name, kind, xy in CHANNELS:
        for c, k in r[r.channelId == cid].groupby("comm").keyword.nunique().items():
            if c not in POS:
                continue
            faint = kind in ("big", "osx")
            ax.plot(*zip(xy, POS[c]), color=LINE[kind], lw=1.4 if faint else 1.2 + 0.9 * k,
                    ls=(0, (2, 2)) if faint else "-", alpha=0.9, zorder=2)
            if not faint:
                m = np.array(xy) * 0.45 + np.array(POS[c]) * 0.55
                ax.text(*m, str(k), fontsize=12.5, ha="center", va="center", color=LINE[kind], fontweight="bold",
                        bbox=dict(boxstyle="circle,pad=0.18", fc="white", ec=LINE[kind], lw=0.8), zorder=5)
    offsets = {"Movie recap": (-0.3, 0.0, "right"), "Gaming & comedy": (0.33, -0.05, "left"),
               "Storytelling": (-0.25, 0.12, "right")}
    for c in COM:
        s = 300 + views[c] * 14
        ring = ntrue.get(c, 0) > 0
        ax.scatter(*POS[c], s=s, color=COL[c], edgecolor="#1b1b1b" if ring else "white",
                   linewidth=3 if ring else 1, zorder=3)
        text = f"{c}\n{nk[c]} kw · {views[c]:.0f}M views" + (f" · True in {ntrue[c]}" if ring else "")
        dx, dy, ha = offsets.get(c, (0, -0.17 - np.sqrt(s) / 300, "center"))
        ax.text(POS[c][0] + dx, POS[c][1] + dy, text, ha=ha, va="top", fontsize=13.1, color="#222", zorder=6,
                linespacing=1.15)
    for cid, name, kind, xy in CHANNELS:
        ax.scatter(*xy, zorder=4, linewidth=1.4, **MARK[kind])
        ax.text(xy[0], xy[1] + (-0.42 if name.startswith("easy boy") else 0.13), name, ha="center", fontsize=14.4,
                fontweight="bold" if kind in ("true", "pick") else "normal", color=TEXT[kind], zorder=6)
    legend = [
        Line2D([], [], marker="o", ls="", mfc="#ddd", mec="#1b1b1b", mew=2.5, ms=11,
               label="Community where a True-owned channel ranks"),
        Line2D([], [], marker="s", ls="", color="#1b1b1b", ms=9, label="True-owned channel"),
        Line2D([], [], marker="D", ls="", color="#eb6834", ms=9, label="Shortlisted creator"),
        Line2D([], [], marker="s", ls="", mfc="white", mec="#8a8a8a", ms=9, label="Top-5 creator by views"),
        Line2D([], [], marker="s", ls="", mfc="#9a9a9a", mec="#1b1b1b", ms=9, label="Top-5, OSx Network (True group)"),
        Line2D([], [], marker="s", ls="", color="#8a4fd1", ms=9, label="Rival OTT"),
    ]
    ax.legend(handles=legend, loc="upper left", bbox_to_anchor=(0.0, 0.02), ncol=3, fontsize=13.1, frameon=False,
              handletextpad=0.3, columnspacing=1.2)
    ax.set_xlim(-3.35, 4.7)
    ax.set_ylim(-2.3, 1.75)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    print(f"figure -> {path}")
