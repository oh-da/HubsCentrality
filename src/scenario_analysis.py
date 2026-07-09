"""Four-level centrality analysis of the transit network.

Level 1  all modes on the same level: every line counts equally
         (the baseline analysis).
Level 2  mode-weighted: every line carries its planned mode's attractiveness
         score (HighSpeed Rail 8 ... Funicular 2). Edge traversal cost is
         length / best mode score, so attractive modes pull shortest paths;
         PageRank flows along the summed line scores; and the composite hub
         score includes the best mode serving the stop.
Level 3  the rail modes (Suburban, Interurban, HighSpeed) removed, remaining
         modes still weighted by score.
Level 4  rail + Metro removed, remaining modes still weighted by score.

Stops served only by removed modes drop out of the network; walking-transfer
edges are rebuilt on the remaining stops.

Outputs under output/scenarios/: one centrality CSV and one interactive HTML
map per level, plus cross-level comparison charts.

Usage: python src/scenario_analysis.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

from build_network import add_transfer_edges, build_graph, load_stops
from centrality_analysis import (
    BLUE, GRID, INK, INK_2, MUTED, SEQ_BLUES, SURFACE, TRANSFER_WALK_DIST,
)
from make_html_map import render_map
from mode_mapping import MODE_SCORES, RAIL_MODES, load_line_modes

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "scenarios"

SCENARIOS = [
    ("level1_equal", "Level 1 — all modes equal", set(), False),
    ("level2_mode_weighted", "Level 2 — mode-weighted (HighSpeed Rail top)", set(), True),
    ("level3_no_rail", "Level 3 — rail removed", RAIL_MODES, True),
    ("level4_no_rail_metro", "Level 4 — rail + Metro removed", RAIL_MODES | {"Metro"}, True),
]


def build_scenario_graph(excluded_modes: set[str], modes: dict[str, str]) -> nx.Graph:
    df = load_stops()
    df = df[~df["LINE_ID"].map(modes).isin(excluded_modes)]
    G = build_graph(df)
    add_transfer_edges(G, TRANSFER_WALK_DIST)
    return G


def compute_centralities(G: nx.Graph, modes: dict[str, str], weighted: bool) -> pd.DataFrame:
    for _, _, a in G.edges(data=True):
        scores = [MODE_SCORES[modes[l]] for l in a["lines"]]
        a["cost"] = a["length"] / (max(scores) if weighted and scores else 1.0)
        a["pr_weight"] = sum(scores) if weighted else a["n_lines"]

    try:
        eig = nx.eigenvector_centrality(G, max_iter=2000)
    except nx.PowerIterationFailedConvergence:
        eig = nx.eigenvector_centrality_numpy(G)

    metrics = {
        "degree": dict(G.degree()),
        "n_lines": {n: a["n_lines"] for n, a in G.nodes(data=True)},
        "betweenness": nx.betweenness_centrality(G, weight="cost", normalized=True),
        "closeness": {
            n: v * 1000.0 for n, v in nx.closeness_centrality(G, distance="cost").items()
        },
        "pagerank": nx.pagerank(G, weight="pr_weight"),
        "eigenvector": eig,
    }
    df = pd.DataFrame(metrics)
    df.index.name = "node"
    df["x"] = [G.nodes[n]["x"] for n in df.index]
    df["y"] = [G.nodes[n]["y"] for n in df.index]
    df["lines"] = [", ".join(sorted(G.nodes[n]["lines"])) for n in df.index]
    df["modes"] = [
        ", ".join(sorted({modes[l] for l in G.nodes[n]["lines"]})) for n in df.index
    ]
    df["mode_score"] = [
        max(MODE_SCORES[modes[l]] for l in G.nodes[n]["lines"]) for n in df.index
    ]

    components = ["degree", "n_lines", "betweenness", "closeness", "pagerank", "eigenvector"]
    if weighted:
        components.append("mode_score")
    ranked = df[components]
    normalised = (ranked - ranked.min()) / (ranked.max() - ranked.min())
    df["hub_score"] = normalised.mean(axis=1)
    return df.sort_values("hub_score", ascending=False)


def plot_scenario_maps(results: dict[str, tuple], path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13, 14), facecolor=SURFACE)
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("seq_blue", SEQ_BLUES)
    for ax, (key, title, _, _) in zip(axes.flat, SCENARIOS):
        G, df = results[key]
        ax.set_facecolor(SURFACE)
        for u, v, a in G.edges(data=True):
            ax.plot(
                [G.nodes[u]["x"], G.nodes[v]["x"]],
                [G.nodes[u]["y"], G.nodes[v]["y"]],
                color=GRID if a.get("transfer") else "#c3c2b7",
                linewidth=0.4,
                zorder=1,
            )
        bt = df["betweenness"]
        pct = bt.rank(pct=True)
        ax.scatter(df["x"], df["y"], c=pct, cmap=cmap, s=2 + 50 * (bt / bt.max()),
                   linewidths=0, zorder=2)
        top = df.nlargest(3, "hub_score")
        for node, r in top.iterrows():
            ax.annotate(str(node), (r["x"], r["y"]), textcoords="offset points",
                        xytext=(5, 4), fontsize=7, color=INK_2)
        ax.set_title(f"{title}\n{len(df)} stops, {G.number_of_edges()} edges",
                     color=INK, fontsize=10)
        ax.set_aspect("equal")
        ax.set_axis_off()
    fig.suptitle("Stop betweenness by scenario (size and colour = betweenness; top-3 hubs labelled)",
                 color=INK, fontsize=12, y=0.995)
    fig.tight_layout()
    fig.savefig(path, dpi=180, facecolor=SURFACE)
    plt.close(fig)


def plot_scenario_top_hubs(results: dict[str, tuple], path: Path, top_n: int = 10) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), facecolor=SURFACE)
    for ax, (key, title, _, _) in zip(axes.flat, SCENARIOS):
        _, df = results[key]
        top = df.head(top_n).iloc[::-1]
        ax.set_facecolor(SURFACE)
        bars = ax.barh(range(len(top)), top["hub_score"], height=0.55, color=BLUE)
        ax.set_yticks(range(len(top)))
        ax.set_yticklabels([f"{n}  ·  {r['modes']}" for n, r in top.iterrows()], fontsize=7)
        for bar, val in zip(bars, top["hub_score"]):
            ax.text(val + 0.01, bar.get_y() + bar.get_height() / 2, f"{val:.2f}",
                    va="center", fontsize=7, color=INK_2)
        ax.set_xlim(0, 1.1)
        ax.set_title(title, color=INK, fontsize=10)
        ax.tick_params(colors=MUTED, labelsize=7)
        for lbl in ax.get_yticklabels():
            lbl.set_color(INK)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.spines["bottom"].set_color("#c3c2b7")
        ax.xaxis.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
    fig.suptitle(f"Top {top_n} hubs by composite hub score, per scenario", color=INK, fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=180, facecolor=SURFACE)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    modes = load_line_modes()

    results = {}
    for key, title, excluded, weighted in SCENARIOS:
        print(f"\n=== {title} ===")
        G = build_scenario_graph(excluded, modes)
        n_comp = nx.number_connected_components(G)
        print(f"{G.number_of_nodes()} stops, {G.number_of_edges()} edges, "
              f"{n_comp} component(s)")
        df = compute_centralities(G, modes, weighted)
        results[key] = (G, df)

        df.round(6).to_csv(OUTPUT_DIR / f"{key}.csv")
        render_map(OUTPUT_DIR / f"{key}_map.html", G, df,
                   title=f"Transit network centrality — {title}")
        print(df[["modes", "degree", "n_lines", "betweenness", "closeness", "hub_score"]]
              .head(10).round(4).to_string())

    plot_scenario_maps(results, OUTPUT_DIR / "scenario_maps.png")
    plot_scenario_top_hubs(results, OUTPUT_DIR / "scenario_top_hubs.png")
    print(f"\nwrote comparison charts to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
