"""Build a transit network graph from the stops-per-line CSV.

The input file lists, for every mass-transit line, the set of stop nodes it
serves (with Israel TM Grid / EPSG:2039 coordinates). Rows within a line are
sorted by node id, NOT by position along the route, so the stop order of each
line is reconstructed geometrically: a greedy nearest-neighbour path seeded at
the most peripheral stop, refined with 2-opt until no crossing remains.

The resulting graph is the "L-space" representation: nodes are stops, and an
undirected edge connects two stops that are consecutive on at least one line.
Edge attributes carry the Euclidean length in metres and the set of lines that
traverse the edge.
"""

from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "All_nodes+lines_18062026.csv"


def load_stops(path: Path = DATA_FILE) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="cp1255")
    df.columns = ["seq", "node", "LINE_ID", "X", "Y", "geometry"]
    df = df.drop_duplicates(subset=["node", "LINE_ID"])
    return df


def node_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """One coordinate per node (a handful of nodes have tiny coordinate
    discrepancies between lines; the mean settles them)."""
    return df.groupby("node")[["X", "Y"]].mean()


def _greedy_path(points: np.ndarray) -> list[int]:
    """Order points into a path by nearest-neighbour, starting from the point
    farthest from the centroid (very likely a route terminus)."""
    n = len(points)
    dist = np.hypot(
        points[:, None, 0] - points[None, :, 0],
        points[:, None, 1] - points[None, :, 1],
    )
    start = int(np.argmax(np.hypot(*(points - points.mean(axis=0)).T)))
    order = [start]
    used = np.zeros(n, dtype=bool)
    used[start] = True
    for _ in range(n - 1):
        row = dist[order[-1]].copy()
        row[used] = np.inf
        nxt = int(np.argmin(row))
        order.append(nxt)
        used[nxt] = True
    return order


def _path_length(order: list[int], dist: np.ndarray) -> float:
    idx = np.asarray(order)
    return float(dist[idx[:-1], idx[1:]].sum())


def _two_opt(order: list[int], points: np.ndarray, max_rounds: int = 50) -> list[int]:
    """2-opt refinement for an open path: reverse segments while that shortens
    the total length. Removes the crossings greedy ordering leaves behind."""
    dist = np.hypot(
        points[:, None, 0] - points[None, :, 0],
        points[:, None, 1] - points[None, :, 1],
    )
    n = len(order)
    for _ in range(max_rounds):
        improved = False
        for i in range(n - 2):
            for j in range(i + 2, n):
                a, b = order[i], order[i + 1]
                c = order[j]
                d_old = dist[a, b] + (dist[c, order[j + 1]] if j + 1 < n else 0.0)
                d_new = dist[a, c] + (dist[b, order[j + 1]] if j + 1 < n else 0.0)
                if d_new < d_old - 1e-9:
                    order[i + 1 : j + 1] = reversed(order[i + 1 : j + 1])
                    improved = True
        if not improved:
            break
    return order


def reconstruct_route(stops: pd.DataFrame) -> list[int]:
    """Return the node ids of a line ordered along the route."""
    pts = stops[["X", "Y"]].to_numpy()
    nodes = stops["node"].to_numpy()
    if len(pts) <= 2:
        return nodes.tolist()
    order = _two_opt(_greedy_path(pts), pts)
    return nodes[order].tolist()


def build_graph(df: pd.DataFrame | None = None) -> nx.Graph:
    if df is None:
        df = load_stops()
    coords = node_coordinates(df)

    G = nx.Graph()
    for node, (x, y) in coords.iterrows():
        G.add_node(int(node), x=float(x), y=float(y), lines=set())

    for line_id, stops in df.groupby("LINE_ID"):
        route = reconstruct_route(stops)
        for node in route:
            G.nodes[node]["lines"].add(line_id)
        for u, v in zip(route[:-1], route[1:]):
            # floor at 1 m so co-located nodes never create zero-length edges,
            # which break inverse-distance centrality measures
            length = max(
                1.0,
                float(
                    np.hypot(
                        G.nodes[u]["x"] - G.nodes[v]["x"],
                        G.nodes[u]["y"] - G.nodes[v]["y"],
                    )
                ),
            )
            if G.has_edge(u, v):
                G[u][v]["lines"].add(line_id)
            else:
                G.add_edge(u, v, length=length, lines={line_id})

    for _, _, attrs in G.edges(data=True):
        attrs["n_lines"] = len(attrs["lines"])
    for _, attrs in G.nodes(data=True):
        attrs["n_lines"] = len(attrs["lines"])
    return G


def add_transfer_edges(G: nx.Graph, max_dist: float = 300.0) -> int:
    """Connect stops of different systems that are within walking distance.

    The dataset gives each system (metro, LRT, BRT, heavy rail, ...) its own
    node ids, so co-located interchange stations appear as distinct nodes a few
    metres apart. Without these edges the national network falls apart into 27
    per-system components. Returns the number of edges added.
    """
    from scipy.spatial import cKDTree

    nodes = list(G.nodes)
    pts = np.array([[G.nodes[n]["x"], G.nodes[n]["y"]] for n in nodes])
    added = 0
    for i, j in cKDTree(pts).query_pairs(r=max_dist):
        u, v = nodes[i], nodes[j]
        if not G.has_edge(u, v):
            G.add_edge(
                u,
                v,
                length=max(1.0, float(np.hypot(*(pts[i] - pts[j])))),
                lines=set(),
                n_lines=0,
                transfer=True,
            )
            added += 1
    return added


if __name__ == "__main__":
    G = build_graph()
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    print(f"nodes: {G.number_of_nodes()}  edges: {G.number_of_edges()}")
    print(f"components: {len(comps)}  largest: {len(comps[0])} nodes")
    n_added = add_transfer_edges(G)
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    print(f"transfer edges added: {n_added}  -> components: {len(comps)}")
