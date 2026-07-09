"""Centrality analysis of the transit stop network.

Builds the L-space graph (stops = nodes, consecutive stops on a line = edges,
plus walking-transfer edges between co-located stops of different systems) and
computes, per stop:

- degree                  direct neighbours in the network
- n_lines                 number of transit lines serving the stop
- betweenness             fraction of shortest paths (metric, by edge length)
                          passing through the stop -- the classic hub measure
- closeness               spatial reachability of every other stop (1/km)
- pagerank                random-walk importance, reinforced by line multiplicity
- eigenvector             influence via connection to other well-connected stops
- hub_score               mean of the min-max normalised metrics above

Outputs: output/node_centrality.csv, output/network_map.png, output/top_hubs.png
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

from build_network import add_transfer_edges, build_graph

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
TRANSFER_WALK_DIST = 300.0  # metres

# reference dataviz palette (light mode)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BLUE = "#2a78d6"
SEQ_BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def compute_centralities(G: nx.Graph) -> pd.DataFrame:
    print("computing centralities ...")
    metrics = {
        "degree": dict(G.degree()),
        "n_lines": {n: a["n_lines"] for n, a in G.nodes(data=True)},
        "betweenness": nx.betweenness_centrality(G, weight="length", normalized=True),
        # closeness in 1/metres, scaled to km for readability
        "closeness": {
            n: v * 1000.0
            for n, v in nx.closeness_centrality(G, distance="length").items()
        },
        "pagerank": nx.pagerank(G, weight="n_lines"),
        "eigenvector": nx.eigenvector_centrality(G, max_iter=2000),
    }
    df = pd.DataFrame(metrics)
    df.index.name = "node"
    df["x"] = [G.nodes[n]["x"] for n in df.index]
    df["y"] = [G.nodes[n]["y"] for n in df.index]
    df["lines"] = [", ".join(sorted(G.nodes[n]["lines"])) for n in df.index]

    ranked = df[["degree", "n_lines", "betweenness", "closeness", "pagerank", "eigenvector"]]
    normalised = (ranked - ranked.min()) / (ranked.max() - ranked.min())
    df["hub_score"] = normalised.mean(axis=1)
    return df.sort_values("hub_score", ascending=False)


def plot_network_map(G: nx.Graph, df: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 15), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)

    for u, v, attrs in G.edges(data=True):
        color = GRID if attrs.get("transfer") else "#c3c2b7"
        ax.plot(
            [G.nodes[u]["x"], G.nodes[v]["x"]],
            [G.nodes[u]["y"], G.nodes[v]["y"]],
            color=color,
            linewidth=0.6,
            zorder=1,
        )

    bt = df["betweenness"]
    order = bt.rank(pct=True)  # colour by percentile so the map isn't one dot of colour
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("seq_blue", SEQ_BLUES)
    ax.scatter(
        df["x"],
        df["y"],
        c=order,
        cmap=cmap,
        s=4 + 120 * (bt / bt.max()),
        linewidths=0,
        zorder=2,
    )

    top = df.nlargest(5, "betweenness")
    for node, row in top.iterrows():
        ax.annotate(
            str(node),
            (row["x"], row["y"]),
            textcoords="offset points",
            xytext=(6, 4),
            fontsize=7,
            color=INK_2,
        )

    sm = plt.cm.ScalarMappable(cmap=cmap)
    cbar = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("betweenness percentile", color=INK_2, fontsize=8)
    cbar.ax.tick_params(colors=MUTED, labelsize=7)
    cbar.outline.set_visible(False)

    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title(
        "Transit network — stop betweenness centrality\n"
        "(size and colour = betweenness; top-5 hubs labelled with node id)",
        color=INK,
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)


def plot_top_hubs(df: pd.DataFrame, path: Path, top_n: int = 15) -> None:
    top = df.head(top_n).iloc[::-1]
    labels = [f"{n}  ({r.n_lines} lines)" for n, r in top.iterrows()]

    fig, ax = plt.subplots(figsize=(8, 6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    bars = ax.barh(labels, top["hub_score"], height=0.55, color=BLUE)
    for bar, val in zip(bars, top["hub_score"]):
        ax.text(
            val + 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.2f}",
            va="center",
            fontsize=8,
            color=INK_2,
        )

    ax.set_xlim(0, 1.05)
    ax.set_xlabel("composite hub score (0–1)", color=INK_2, fontsize=9)
    ax.set_title(f"Top {top_n} hub stops by composite centrality score", color=INK, fontsize=11)
    ax.tick_params(colors=MUTED, labelsize=8)
    for lbl in ax.get_yticklabels():
        lbl.set_color(INK)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    G = build_graph()
    print(f"graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} route edges")
    n_transfer = add_transfer_edges(G, TRANSFER_WALK_DIST)
    n_comp = nx.number_connected_components(G)
    print(f"added {n_transfer} walking-transfer edges (<= {TRANSFER_WALK_DIST:.0f} m) "
          f"-> {n_comp} connected component(s)")

    df = compute_centralities(G)
    csv_path = OUTPUT_DIR / "node_centrality.csv"
    df.round(6).to_csv(csv_path)
    print(f"wrote {csv_path}")

    plot_network_map(G, df, OUTPUT_DIR / "network_map.png")
    plot_top_hubs(df, OUTPUT_DIR / "top_hubs.png")
    print(f"wrote {OUTPUT_DIR / 'network_map.png'} and {OUTPUT_DIR / 'top_hubs.png'}")

    print("\nTop 15 hubs:")
    cols = ["degree", "n_lines", "betweenness", "closeness", "pagerank", "hub_score"]
    print(df[cols].head(15).round(4).to_string())


if __name__ == "__main__":
    main()
