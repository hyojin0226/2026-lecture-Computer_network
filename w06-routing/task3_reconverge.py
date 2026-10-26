#!/usr/bin/env python3
"""Week 6 · Task 3 — Reconverge without recomputing the world.

Textbook §5.2.1, §5.3.

A link flaps. Every router in the area has to decide what changed. `FullRecompute`
does the honest thing: throw the table away and run Dijkstra again, from scratch,
for every event. It is correct and it is what the first implementations did.

It is also why a single flapping link in a large area used to melt the CPU of
every router that could see it.

Beat it:

    python3 bench.py
    python3 bench.py --yours

Correctness first. `bench.py` compares your table against a full recompute after
**every single event**. A router that is fast and wrong black-holes traffic.
"""
import heapq

# The harness counts how many times you run a full SPF. This is the score:
# wall-clock time in Python says more about dictionary overhead than about
# routing, but "how many times did the CPU have to recompute the world" is
# exactly what melted real routers.
SPF_RUNS = 0


def dijkstra_table(graph, source, state=None):
    """Reference shortest-path-first. Returns {destination: first_hop}.

    Use THIS function whenever you need a full recompute. Rolling your own to
    dodge the counter is not an optimisation, it is cheating the meter.
    """
    global SPF_RUNS
    SPF_RUNS += 1
    best = {source: (0, None)}
    parent = {}
    pq, done = [(0, source, None)], set()
    while pq:
        cost, node, first_hop = heapq.heappop(pq)
        if node in done:
            continue
        done.add(node)
        best[node] = (cost, first_hop)
        for nbr, w in sorted(graph[node].items()):
            if nbr in done:
                continue
            hop = nbr if node == source else first_hop
            if cost + w < best.get(nbr, (float("inf"), None))[0]:
                best[nbr] = (cost + w, hop)
                parent[nbr] = node
                heapq.heappush(pq, (cost + w, nbr, hop))
    if state is not None:
        state["distances"] = {d: c for d, (c, _) in best.items()}
        state["parent"] = parent
    return {d: h for d, (_, h) in best.items() if d != source and h}


class FullRecompute:
    """On every event, forget everything and run SPF again."""

    def __init__(self, graph, source):
        self.graph = {n: dict(e) for n, e in graph.items()}
        self.source = source
        self.table = dijkstra_table(self.graph, source)

    def link_change(self, a, b, cost):
        """cost=None means the link went down."""
        if cost is None:
            self.graph[a].pop(b, None)
            self.graph[b].pop(a, None)
        else:
            self.graph[a][b] = cost
            self.graph[b][a] = cost
        self.table = dijkstra_table(self.graph, self.source)


class YourRouter:
    """Your router. Same two methods, same table, less work per event.

    What is actually true after one link changes:

      * most destinations are not affected at all
      * a link that is not on any of your shortest paths, going *up*, can only
        matter if it creates something shorter
      * a link going *down* only matters if you were using it

    Deciding which of those applies, cheaply, without getting it wrong, is the
    task. Getting it wrong is worse than being slow - the harness will catch it
    on the event where it happens.
    """

    def __init__(self, graph, source):
        self.graph = {n: dict(edges) for n, edges in graph.items()}
        self.source = source
        self._state = {}
        self.table = dijkstra_table(self.graph, source, self._state)

    def link_change(self, a, b, cost):
        old_cost = self.graph.get(a, {}).get(b)
        # A no-op cannot change the forwarding table.
        if old_cost == cost:
            return

        selected_tree_edge = (
            self._state.get("parent", {}).get(a) == b
            or self._state.get("parent", {}).get(b) == a
        )
        self._apply_link(a, b, cost)

        # Removing or raising a link can only matter when that link carries
        # one of this router's selected shortest paths. Other routes remain
        # valid and no cheaper path can be created by an increase.
        if cost is None or (old_cost is not None and cost > old_cost):
            if selected_tree_edge:
                self.table = dijkstra_table(self.graph, self.source, self._state)
            return

        # For a new or cheaper link, test whether joining the already-known
        # shortest paths at its endpoints could improve either endpoint.
        # Strict improvement triggers SPF. For equal routes, SPF is needed
        # only if the new predecessor would be settled before the predecessor
        # that currently supplies the route; otherwise strict relaxation keeps
        # the existing first hop.
        distances = self._state.get("distances", {})
        da, db = distances.get(a, float("inf")), distances.get(b, float("inf"))
        if (da + cost < db or db + cost < da
                or (da + cost == db and self._tie_would_change(a, b))
                or (db + cost == da and self._tie_would_change(b, a))):
            self.table = dijkstra_table(self.graph, self.source, self._state)

    def _apply_link(self, a, b, cost):
        if cost is None:
            self.graph[a].pop(b, None)
            self.graph[b].pop(a, None)
        else:
            self.graph[a][b] = cost
            self.graph[b][a] = cost

    def _tie_would_change(self, predecessor, destination):
        """Whether a new equal route wins the reference's heap tie order."""
        parent = self._state.get("parent", {}).get(destination)
        if parent is None:
            return False
        dist = self._state["distances"]
        hops = self.table
        candidate_key = (dist[predecessor], predecessor,
                         hops.get(predecessor))
        current_key = (dist[parent], parent, hops.get(parent))
        return candidate_key < current_key
