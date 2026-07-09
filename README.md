# HubsCentrality

Centrality analysis of a planned mass-transit network (metro, LRT, BRT and
heavy rail lines across Israel), identifying the hub stops of the system.

## Data

`data/All_nodes+lines_18062026.csv` — one row per (stop node, line) pair:
node id, `LINE_ID`, and stop coordinates in the Israel TM Grid (EPSG:2039).
5,013 rows covering **1,593 unique stops** and **220 directed lines**.

Two quirks of the file shape the methodology:

1. **Rows within a line are sorted by node id, not by position along the
   route** (verified: 162/220 lines are in strict node-id order, and
   consecutive rows are often kilometres apart while a geometric ordering of
   the same stops is not). The stop sequence of every line is therefore
   reconstructed geometrically: a greedy nearest-neighbour path seeded at the
   most peripheral stop, refined with 2-opt.
2. **Each transit system uses its own node ids**, so interchange stations
   between systems appear as separate nodes a few metres apart. Built only
   from shared node ids the network splits into 27 per-system components;
   walking-transfer edges between stops of different systems within **300 m**
   join it into a single connected network.

## Network model

L-space graph: stops are nodes; an undirected edge joins two stops that are
consecutive on at least one line (edge attributes: length in metres, set of
lines), plus the walking-transfer edges described above. Result: 1,593 nodes,
1,728 route edges, 524 transfer edges, 1 connected component.

## Centrality measures (per stop)

| measure | meaning |
|---|---|
| `degree` | directly connected neighbouring stops |
| `n_lines` | number of lines serving the stop |
| `betweenness` | share of metric shortest paths passing through the stop |
| `closeness` | spatial reachability of all other stops (1/km) |
| `pagerank` | random-walk importance, weighted by line multiplicity |
| `eigenvector` | connection to other well-connected stops |
| `hub_score` | mean of the min–max-normalised measures above |

## Running

```bash
pip install -r requirements.txt
python src/centrality_analysis.py   # CSV + static charts
python src/make_html_map.py         # interactive HTML map
```

Outputs land in `output/`:

- `node_centrality.csv` — every stop with all measures, coordinates and the
  lines serving it, sorted by hub score
- `network_map.html` — **interactive map** (open in any browser, no server
  needed): drag to pan, scroll to zoom, click a stop for its node id,
  centrality scores and the lines serving it, and switch the metric that
  drives colour and size
- `network_map.png` — the network drawn in geographic space, stops sized and
  coloured by betweenness
- `top_hubs.png` — top-15 hub stops by composite score

## Headline findings

- The strongest hubs concentrate in the Tel Aviv metropolitan core: nodes
  **400080**, **400018** and **400110** (heavy-rail/metro interchange stops
  served by 22–28 lines each) lead every measure, combining the highest line
  counts with the highest betweenness and closeness in the network.
- **31603** (Haifa area) is the top bridge outside the centre — the highest
  raw betweenness in the network (0.38), funnelling the north–centre paths.
- Stops in the national-rail backbone dominate closeness, since rail edges
  shorten metric distances between regions; purely local BRT/LRT stops rank
  high on degree but low on closeness, which the composite score balances.
