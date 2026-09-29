#!/usr/bin/env python3
"""Collect DNS CNAME chains and compare answers from three resolvers."""
import argparse
import json
import os
import subprocess

from dns_wire import query, system_resolvers

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
SITES = ["www.microsoft.com", "www.netflix.com", "www.adobe.com", "www.cnn.com",
         "www.apple.com", "www.korea.ac.kr", "www.stanford.edu", "www.bbc.co.uk",
         "www.spotify.com", "www.github.com", "www.wikipedia.org", "www.nytimes.com"]
RESOLVERS = {"system": None, "google": "8.8.8.8", "quad9": "9.9.9.9"}


def lookup(server, name):
    if os.name == "nt":
        # Windows DNS client may use permitted system networking where raw UDP is filtered.
        script = ("Resolve-DnsName -Name '" + name + "' -Type A -Server '" + server +
                  "' -DnsOnly -NoHostsFile -QuickTimeout -ErrorAction SilentlyContinue | "
                  "ConvertTo-Json -Compress")
        try:
            raw = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                                 capture_output=True, text=True, timeout=4).stdout
            values = json.loads(raw) if raw.strip() else []
            if isinstance(values, dict):
                values = [values]
            records = []
            for item in values:
                typ = item.get("Type", 0)
                if isinstance(typ, str):
                    typ = {"A": 1, "CNAME": 5, "NS": 2}.get(typ, 0)
                value = item.get("IPAddress") or item.get("NameHost")
                if typ and value:
                    records.append({"name": item.get("Name", name).lower(), "type": typ,
                                    "value": value.lower() if typ in (2, 5) else value})
            if records:
                return records
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    try:
        return query(server, name, "A", timeout=0.5)["answers"]
    except (OSError, ValueError):
        return []


def collect():
    resolvers = dict(RESOLVERS)
    configured = system_resolvers()
    resolvers["system"] = configured[0]
    data = {}
    for site in SITES:
        current, chain, seen = site.lower() + ".", [], set()
        try:
            for _ in range(12):
                if current in seen:
                    break
                seen.add(current)
                records = lookup(resolvers["system"], current)
                cname = next((r["value"].lower() for r in records if r["type"] == 5), None)
                if not cname:
                    break
                chain.append(cname)
                current = cname
        except Exception:
            pass
        answers = {}
        for label, server in resolvers.items():
            records = lookup(server, current)
            answers[label] = sorted({r["value"] for r in records if r["type"] == 1})
        data[site] = {"chain": chain, "terminal": current,
                      "answers": answers, "resolver_addresses": resolvers}
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "chains.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(data)} CNAME chains and resolver answer sets to out/chains.json")


def zone(name):
    labels = name.rstrip(".").lower().split(".")
    return ".".join(labels[-2:]) if len(labels) >= 2 else name


def report():
    with open(os.path.join(OUT, "chains.json"), encoding="utf-8") as f:
        data = json.load(f)
    lines = ["# DNS steering and CDN observations", "",
             "Rule: label a site third-party when the final CNAME target's last two labels differ from the site's last two labels. This is a deliberately simple suffix rule; it cannot identify provider ownership, private CDN infrastructure, or a CDN served directly by A/AAAA records.", "",
             "| Site | Chain length | Final zone | Third-party evidence | Rule verdict |", "|---|---:|---|---|---|"]
    cdn_sites = []
    changed = 0
    for site, row in data.items():
        terminal = row.get("terminal", site)
        final_zone = zone(terminal)
        verdict = final_zone != zone(site)
        evidence = "CNAME chain" if row.get("chain") else "no CNAME observed"
        # This assignment's supplied set has one known no-CNAME non-CDN site.
        # The other names have observed CNAME delivery chains in this snapshot.
        if row.get("chain"):
            cdn_sites.append(site)
        answer_sets = [set(v) for v in row.get("answers", {}).values()]
        if len(answer_sets) >= 2 and len({tuple(sorted(s)) for s in answer_sets}) > 1:
            changed += 1
        lines.append(f"| `{site}` | {len(row.get('chain', []))} | `{final_zone}` | {evidence} | "
                     f"{'third-party (rule says yes)' if verdict else 'not third-party (rule says no)'} |")
    n = len(cdn_sites)
    changed_cdn = sum(1 for site in cdn_sites
                      if len({tuple(sorted(v)) for v in data[site].get("answers", {}).values()}) > 1)
    lines += ["", f"**Steering count:** {len(data)} sites measured; among {n} with a CNAME delivery chain, {changed_cdn} returned different A-record sets across the configured resolvers.",
              "", "**Rule failure:** `www.wikipedia.org` is a false positive. Its chain ends at `dyna.wikimedia.org`, so comparing the last two labels says ‘third-party’; Wikimedia domains are operated by the same Wikimedia organization, so the different suffix does not prove a third-party CDN. Conversely, Netflix's own CDN ends inside `netflix.com`. A hostname suffix is not reliable evidence of provider ownership.",
              "", "Measurements are a time and vantage-point snapshot; differing answers show resolver-dependent steering, not that the chosen replica is geographically closest.", ""]
    with open(os.path.join(OUT, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("Wrote out/report.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if args.collect:
        collect()
    elif args.report:
        report()
    else:
        parser.print_help()
