#!/usr/bin/env python3
"""Week 3 assignment checks; capture parsing is skipped without tshark."""
import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
sys.path.insert(0, HERE)
PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results = []


def record(task, name, status, detail=""):
    results.append((task, name, status, detail))
    print(f"  {status:<4} [{task}] {name}" + (f" - {detail}" if detail else ""))


def test_task1():
    if not shutil.which("dig"):
        record(1, "resolver vs dig", SKIP, "dig not installed; network verification unavailable")
    else:
        m = importlib.import_module("task1_resolve")
        for name, kind in m.VERIFY_NAMES:
            try:
                addr, path = m.Resolver().resolve(name)
                expected = m.dig_answer(name)
                ok = addr in expected or kind == "cdn"
                record(1, f"resolve {name}", PASS if ok else FAIL,
                       f"{addr} via {len(path)} hops; dig={','.join(expected) or '-'}")
            except Exception as exc:
                record(1, f"resolve {name}", FAIL, repr(exc))


def test_task2():
    cap = os.path.join(OUT, "dns.pcapng")
    if not os.path.exists(cap):
        record(2, "out/dns.pcapng exists", FAIL, "a genuine Wireshark DNS capture is required")
    elif not shutil.which("tshark"):
        record(2, "capture parses", SKIP, "tshark not installed")
    chains = os.path.join(OUT, "chains.json")
    try:
        data = json.load(open(chains, encoding="utf-8"))
        record(2, "out/chains.json parses", PASS, f"{len(data)} sites")
    except Exception as exc:
        record(2, "out/chains.json parses", FAIL, repr(exc))
    rep = os.path.join(OUT, "report.md")
    try:
        text = open(rep, encoding="utf-8").read().lower()
        for need, label in [("|", "table"), ("third", "third-party verdict"),
                            ("resolver", "steering number")]:
            record(2, f"report mentions {label}", PASS if need in text else FAIL)
    except OSError as exc:
        record(2, "out/report.md exists", FAIL, str(exc))


def test_task3():
    bench = importlib.import_module("bench")
    cache = importlib.import_module("task3_cache")
    base = bench.run(cache.BaselineCache, "baseline")
    mine = bench.run(cache.YourCache, "yours")
    record(3, "zero stale answers", PASS if mine["stale"] == 0 else FAIL,
           f"{mine['stale']} stale")
    record(3, "no more upstream than baseline",
           PASS if mine["upstream"] <= base["upstream"] else FAIL,
           f"{mine['upstream']} vs {base['upstream']}")
    record(3, "floor argument", SKIP, "human-reviewed in observation.md")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", type=int, choices=[1, 2, 3])
    args = parser.parse_args()
    os.makedirs(OUT, exist_ok=True)
    for n, fn in ((1, test_task1), (2, test_task2), (3, test_task3)):
        if args.task in (None, n):
            print(f"\n=== Task {n}")
            fn()
    failed = sum(item[2] == FAIL for item in results)
    skipped = sum(item[2] == SKIP for item in results)
    print(f"\n{len(results)-failed-skipped} passed, {failed} failed, {skipped} skipped")
    sys.exit(bool(failed))


if __name__ == "__main__":
    main()
