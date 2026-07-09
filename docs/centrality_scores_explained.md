# What each centrality score means (a friendly guide)

Every stop in the network gets seven scores. Each one answers a different
question about how "important" the stop is. This guide explains each score in
plain language, with tiny examples you can follow by hand.

All the examples use this mini network of 7 stops, where a line ( `—` )
means two stops are directly connected (they are consecutive stops on some
transit line, or a short walk apart):

```
   A — B — C — D — E
           |
           F
           |
           G
```

Think of it as one east–west route `A B C D E` crossing one north–south
route `C F G` at stop **C**.

---

## degree — "how many direct neighbours do I have?"

**Question it answers:** from this stop, how many other stops can I reach in
a single hop, without passing any stop in between?

Count the lines touching each letter:

| stop | neighbours | degree |
|---|---|---|
| A | B | 1 |
| B | A, C | 2 |
| **C** | **B, D, F** | **3** |
| F | C, G | 2 |

**How to read it:** a high degree means the stop is a local junction — many
different directions branch out from it. A stop in the middle of a straight
route always has degree 2 (the previous stop and the next one), so anything
above 2 means routes meet or cross there.

**What it does NOT tell you:** whether those neighbours matter. A stop can
touch five dead-end branches and still be unimportant for the network as a
whole. That's what the other measures are for.

---

## n_lines — "how many transit lines stop here?"

**Question it answers:** how much service does this stop get?

This one isn't about the network shape at all — it just counts the lines
serving the stop. If the red LRT, the blue BRT and three rail lines all call
at stop C, then C has `n_lines = 5`.

**How to read it:** high `n_lines` marks a *service-rich* stop — a natural
transfer point where you can switch between many lines without walking.
In our data the biggest hubs (e.g. stop 400080) are served by 28 lines.

**Degree vs n_lines:** degree counts *neighbouring stops*, n_lines counts
*lines*. Ten lines that all drive down the same street give a stop a high
`n_lines` but still only degree 2 (everything comes from one side and leaves
by the other).

---

## betweenness — "how often am I on the way?"

**Question it answers:** if every passenger in the network travelled between
every pair of stops by the shortest route, what share of those trips would
pass through this stop?

Look at the mini network again:

```
   A — B — C — D — E
           |
           F
           |
           G
```

Anyone travelling from the east–west route (`A, B`) to the north–south
branch (`F, G`) **must** pass through C. So must anyone going from `A` to
`E`. Count all shortest paths between all pairs, and C sits on far more of
them than anyone else — C has by far the highest betweenness. Stop B has
some (trips from A to everywhere pass it); stops A, E, G have zero (no trip
*through* a dead end).

**How to read it:** betweenness finds **bridges and bottlenecks**. A high
score means "if you removed this stop, lots of journeys would need long
detours — or become impossible." The score is a fraction between 0 and 1
(share of all shortest paths), so 0.38 — the score of stop 31603 in our
level-1 analysis — means roughly 38% of all shortest journeys in the
network pass through that one stop. That's a critical link.

**Fine print for our project:** "shortest" is measured in metres along the
network, and in the mode-weighted scenarios (levels 2–4) each metre on an
attractive mode counts for less (a HighSpeed Rail metre costs ⅛ of a walking
metre), so paths — and therefore betweenness — shift toward the attractive
modes.

---

## closeness — "how quickly can I reach everyone else?"

**Question it answers:** starting from this stop, how short is the trip to
*everybody else*, on average?

In the mini network, C's average distance to the other six stops is the
smallest (it's in the middle of everything), so C has the highest closeness.
A and G are the far corners: their average trip is the longest, so their
closeness is the lowest.

The formula is simply:

```
closeness = 1 / (average shortest distance to every other stop)
```

Because it's "1 divided by," **bigger = better connected**: half the average
distance to everyone means double the closeness.

**How to read it:** closeness finds the **geographic centre of gravity** of
the network. In our results, stops on the national rail backbone dominate
closeness — rail edges span whole regions, so from a rail stop *everything*
is nearby in network terms. In our tables closeness is expressed in 1/km
(e.g. 0.02 means the average stop is about 50 km of network away).

**Betweenness vs closeness:** a stop can be *close to everything* without
being *on the way* between things (a stop hanging one hop off the central
station), and vice versa (a lonely bridge in the far north that everything
northern must cross). The two scores catch different kinds of importance.

---

## pagerank — "am I recommended by busy places?"

**Question it answers:** imagine a passenger who rides forever, at each stop
picking a random connecting line (preferring the connections with more
service). What fraction of all eternity do they spend at this stop?

This is the algorithm Google originally used to rank web pages: a page (or
stop) is important **if important pages link to it**. Being pointed at by
one huge hub is worth more than being pointed at by five dead ends.

Tiny example: two stops both have degree 2.

```
  X's neighbours:  two quiet suburban stops
  Y's neighbours:  the two biggest interchanges in the city
```

Degree says X and Y are equal. PageRank says Y is far more important,
because the random passenger constantly flows *through* the big
interchanges and therefore keeps arriving at Y.

**How to read it:** PageRank is a **flow-based** importance score — it
rewards stops that sit next to heavy traffic, weighted in our project by
how many lines (and, in weighted scenarios, how attractive those lines are)
run along each connection. The scores of all stops add up to 1, so read a
stop's value as its share of the endless journey: 0.0013 means the random
passenger spends 0.13% of all time at that stop — about 2× what an average
stop would get in a 1,593-stop network (1/1593 ≈ 0.0006).

---

## eigenvector — "are my friends popular?"

**Question it answers:** how well connected am I *to well-connected stops*?

It sounds circular — "you're important if your neighbours are important,
and they're important if *their* neighbours are important..." — but the
mathematics settles into a stable answer (it's the same idea as PageRank
without the random-hop correction).

Example:

```
  P — Q     P's only neighbour Q is itself well connected:  P scores high.
  R — S     R's only neighbour S is a dead end:             R scores low.
```

Both P and R have degree 1. Eigenvector centrality tells them apart.

**How to read it:** eigenvector centrality highlights stops embedded in the
**dense core** of the network — the neighbourhood where everything is
connected to everything. Stops on remote branches score near zero even if
they're locally busy. In our results it lights up the Tel Aviv core, where
the most interconnected cluster of lines lives.

**PageRank vs eigenvector:** close cousins. PageRank handles quiet corners
and line weights more gracefully; eigenvector is the purer "quality of your
neighbourhood" measure. When they disagree, ask: is this stop important
because of *through-traffic* (PageRank) or because of *its address in the
dense core* (eigenvector)?

---

## hub_score — "all of the above, on one scale"

**Question it answers:** taking every kind of importance into account, how
much of a hub is this stop overall?

Each of the measures above lives on its own scale (degree is 1–11,
betweenness 0–0.45, PageRank 0–0.0013...). To combine them:

1. **Normalise** each measure to 0–1: the best stop in the network gets 1,
   the worst gets 0, everyone else lands proportionally in between.
2. **Average** the normalised values.

So a hub score of 0.69 means: "averaged across every centrality measure,
this stop sits at 69% of the way to being the best in the network at
everything simultaneously." Nobody scores 1.0 — that would require being
the single best stop on *every* measure at once.

In the **mode-weighted scenarios** (levels 2–4) the attractiveness score of
the best mode serving the stop (HighSpeed Rail 8 ... Funicular 2) is added
to the mix as a seventh ingredient, so a stop served by better modes gets a
deliberate push — that's what "HighSpeed Rail nodes are the most important"
means in level 2.

**How to read it:** use `hub_score` for ranking ("what are the top 20
hubs?"), then look at the individual scores to understand *why* a stop
ranks — is it a bridge (betweenness), a service magnet (n_lines), central
(closeness), or in the thick of it (eigenvector)?

---

## Cheat sheet

| score | one-liner | high value means |
|---|---|---|
| degree | direct neighbours | routes branch/cross here |
| n_lines | lines stopping here | rich service, easy transfers |
| betweenness | share of shortest paths through me | bridge/bottleneck — removal hurts |
| closeness | 1 / average distance to everyone | geographically central, everything nearby |
| pagerank | share of an endless random ride | heavy traffic flows past |
| eigenvector | popularity of my neighbours | sits in the dense core |
| hub_score | average of all (normalised) | strong all-round hub |
