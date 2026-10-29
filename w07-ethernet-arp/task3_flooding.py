#!/usr/bin/env python3
"""Week 7 · Task 3 — A switch that runs out of room.

Textbook §6.4.3.

A switch does not have room for every station on the network. Its forwarding
table sits in a fixed amount of fast memory, and when that fills, something has
to go. Whatever goes gets **flooded** the next time anyone sends to it - out of
every port, to every station that did not ask for it.

`NaiveSwitch` handles a full table the simplest way: throw out whichever entry
has been there longest. That is a perfectly reasonable first idea and it is
close to the worst thing you can do with this traffic.

    python3 bench.py
    python3 bench.py --yours

Correctness first: every frame whose destination is reachable must still reach
it. A switch that floods less because it delivers less is not a switch.
"""
from collections import OrderedDict


class NaiveSwitch:
    """Correct. Evicts the oldest entry, which is not the least useful one."""

    BROADCAST = "ff:ff:ff:ff:ff:ff"

    def __init__(self, ports, capacity):
        self.ports = ports
        self.capacity = capacity
        self.table = OrderedDict()                 # mac -> port, insertion order

    def handle(self, frame, in_port):
        src, dst, now = frame
        if src not in self.table and len(self.table) >= self.capacity:
            self.table.popitem(last=False)         # throw out the oldest arrival
        self.table[src] = in_port

        if dst == self.BROADCAST or dst not in self.table:
            return [p for p in range(self.ports) if p != in_port]
        out = self.table[dst]
        return [] if out == in_port else [out]


class YourSwitch:
    """Your switch. Same interface, same deliveries, far less flooding.

        __init__(ports, capacity)
        handle((src, dst, time), in_port) -> ports to forward out of

    `self.table` must exist and must never hold more than `capacity` entries.
    The harness checks this after every frame.

    What the baseline gets wrong: it decides what to keep by **when the entry
    arrived**, and that has nothing to do with whether it is about to be needed.
    On this trace a handful of stations carry most of the traffic, and the
    baseline keeps throwing them out to make room for stations that spoke once.

    Two questions worth separating:

      * which entry should leave when the table is full?
      * should learning a new source ever be *declined*?

    The second one is less obvious and is worth thinking about before you
    dismiss it.

    Note what you are NOT allowed to do: you cannot look at `where`, you cannot
    see the future, and you cannot hold more than `capacity` entries. Everything
    you know comes from the frames you have already handled.
    """

    BROADCAST = "ff:ff:ff:ff:ff:ff"

    def __init__(self, ports, capacity):
        if capacity < 0:
            raise ValueError("capacity must be non-negative")
        self.ports = ports
        self.capacity = capacity
        # Cached MAC -> port. A bounded count-min sketch tracks source
        # popularity, including stations that are not currently admitted.
        self.table = OrderedDict()
        self._hits = {}
        self._width = 2048
        self._depth = 4
        self._sketch = [[0] * self._width for _ in range(self._depth)]
        self._samples = 0

    def _indices(self, mac):
        # Stable per-row FNV-1a hashes avoid Python's process-randomized hash
        # seed, so repeated benchmark runs produce the same admission choices.
        data = mac.encode("ascii")
        for row in range(self._depth):
            h = (2166136261 ^ (0x9e3779b9 + row * 0x85ebca6b)) & 0xffffffff
            for byte in data:
                h = ((h ^ byte) * 0x01000193) & 0xffffffff
            yield row, h % self._width

    def _estimate(self, mac):
        return min(self._sketch[row][col] for row, col in self._indices(mac))

    def _record(self, mac):
        for row, col in self._indices(mac):
            self._sketch[row][col] += 1
        self._samples += 1
        # Periodic halving lets recent behavior outweigh ancient history.
        if self._samples >= 100_000:
            for row in self._sketch:
                for i, value in enumerate(row):
                    row[i] = value // 2
            self._samples = 50_000

    def handle(self, frame, in_port):
        src, dst, _ = frame
        self._record(src)

        if src in self.table:
            self.table[src] = in_port
            self._hits[src] = self._estimate(src)
        elif self.capacity:
            if len(self.table) < self.capacity:
                self.table[src] = in_port
                self._hits[src] = self._estimate(src)
            else:
                victim = min(self.table, key=lambda mac: self._hits[mac])
                # Admission control: a one-off source cannot displace a
                # resident with a stronger observed frequency estimate.
                if self._estimate(src) > self._hits[victim]:
                    del self.table[victim]
                    del self._hits[victim]
                    self.table[src] = in_port
                    self._hits[src] = self._estimate(src)

        if dst == self.BROADCAST or dst not in self.table:
            return [p for p in range(self.ports) if p != in_port]
        out = self.table[dst]
        return [] if out == in_port else [out]
