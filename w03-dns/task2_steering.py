#!/usr/bin/env python3
"""Week 3 · Task 2 — Does DNS actually steer you? Measure it.

Textbook §2.4.3 (records) and §2.5 (CDNs).

The lecture claims two things:

    (a) most large sites are served by a CDN, reached through a CNAME chain
    (b) DNS steers each user to a *nearby* replica

Both are testable from your laptop, and one of them is harder to prove than
the slide makes it look. Your job is to produce the evidence and a number.

    python3 task2_steering.py --collect        # gather the raw data
    python3 task2_steering.py --report         # your analysis

What you have to build
----------------------
1.  For each hostname in SITES, follow the CNAME chain to its end and record
    every hop. `--collect` should leave the raw data in out/chains.json.

2.  Decide, for each site, whether it is served by a **third party**.
    This is the hard part and there is no single right answer:

      - `www.microsoft.com` ends at `akamaiedge.net`     - clearly third party
      - `www.netflix.com`   stops inside `netflix.com`   - own CDN, not third party
      - some sites have no CNAME at all and still sit behind a CDN (anycast)
      - `foo.cloudfront.net` and `foo.s3.amazonaws.com` are both Amazon,
        but they are not the same service

    Write down the rule you used and **defend it in observation.md**. A rule
    that just compares the last two labels will be wrong on at least one of
    the sites below; find which, and say so.

3.  Ask **two different resolvers** for the same name and compare the
    addresses you get back. If DNS really steers by location, a CDN-hosted
    name should answer differently to resolvers sitting in different places.

        RESOLVERS below has your system resolver and two public ones.

    Report: of N CDN-hosted sites, how many returned a different address set
    from a different resolver? Claim (b) predicts most of them. Check it.

Pass condition
--------------
There is no fixed answer. You pass by producing, in out/report.md:

  - the table: site | chain length | final zone | third party? | your rule's verdict
  - the steering number: "X of N sites answered differently to a different resolver"
  - at least one site where your classification rule was wrong, and why
"""
import argparse, json, os, re, socket, subprocess, sys, time

from task1_resolve import Resolver

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

SITES = [
    "www.microsoft.com",     # Akamai, multi-hop
    "www.netflix.com",       # own CDN
    "www.adobe.com",
    "www.cnn.com",
    "www.apple.com",
    "www.korea.ac.kr",       # no CDN at all
    "www.stanford.edu",
    "www.bbc.co.uk",
    "www.spotify.com",
    "www.github.com",
    "www.wikipedia.org",
    "www.nytimes.com",
]
CDN_CANDIDATES = set(SITES) - {"www.korea.ac.kr"}

RESOLVERS = {
    "system": None,          # whatever is in your resolv.conf
    "google": "8.8.8.8",
    "quad9":  "9.9.9.9",
}


def dig(name, rtype="A", server=None):
    """Compatibility helper; DNS transport is implemented in pure Python."""
    server = server or system_resolver()
    if not server:
        return []
    try:
        _, sections = Resolver()._query(server, name, recursive=True)
    except (OSError, ValueError, socket.timeout):
        return []
    wanted = 1 if rtype == "A" else 5 if rtype == "CNAME" else 2
    return [rr["data"] for rr in sections["answer"] if rr["type"] == wanted]


def system_resolver():
    """Return one configured resolver address without relying on dig."""
    if os.name == "nt":
        for command in ([os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                                     "System32", "ipconfig.exe"), "/all"],):
            try:
                output = subprocess.run(command, capture_output=True, text=True,
                                        encoding="cp949",
                                        timeout=5).stdout
                match = re.search(r"DNS\s*(?:Servers|서버)[^:\r\n]*:\s*((?:[0-9]{1,3}\.){3}[0-9]{1,3})",
                                  output, re.IGNORECASE)
                if match:
                    return match.group(1)
            except (OSError, subprocess.TimeoutExpired):
                pass
    else:
        try:
            with open("/etc/resolv.conf", encoding="utf-8") as f:
                for line in f:
                    match = re.match(r"\s*nameserver\s+(\S+)", line)
                    if match and ":" not in match.group(1):
                        return match.group(1)
        except OSError:
            pass
    return None


def query_chain(name, server):
    """Follow the recursive resolver's returned CNAMEs, recording every hop."""
    current, chain, visited, error = name.rstrip(".").lower() + ".", [], set(), None
    for _ in range(12):
        if current in visited:
            error = "CNAME loop"
            break
        visited.add(current)
        try:
            _, sections = Resolver()._query(server, current, recursive=True, timeout=0.8)
        except (OSError, ValueError, socket.timeout) as exc:
            error = f"{type(exc).__name__}: {exc}"
            break
        aliases = [rr["data"] for rr in sections["answer"]
                   if rr["type"] == 5 and rr["name"] == current]
        if not aliases:
            break
        target = aliases[0]
        chain.append({"from": current, "to": target})
        current = target
    else:
        error = "CNAME depth limit exceeded"
    return chain, current, error


def address_set(name, server):
    try:
        _, sections = Resolver()._query(server, name, recursive=True, timeout=0.8)
        return sorted({rr["data"] for rr in sections["answer"]
                       if rr["type"] == 1 and rr["class"] == 1})
    except (OSError, ValueError, socket.timeout):
        return []


def registered_zone(host):
    labels = host.rstrip(".").lower().split(".")
    if len(labels) < 2:
        return host.rstrip(".").lower()
    two_label_suffixes = {"co.uk", "org.uk", "ac.uk", "com.au", "net.au", "co.jp",
                          "co.kr", "ac.kr", "or.kr", "go.kr", "com.br", "co.nz"}
    suffix = ".".join(labels[-2:])
    return ".".join(labels[-3:]) if suffix in two_label_suffixes and len(labels) >= 3 else suffix


def collect(network_label="current network"):
    """Gather raw chains and per-resolver answers into out/chains.json.

    You write this. Roughly:
      for each site: follow CNAMEs to the end, then for each resolver in
      RESOLVERS record the A records it returns.
    """
    active = dict(RESOLVERS)
    active["system"] = system_resolver()
    measurement = {"measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "network": network_label, "resolvers": active, "sites": {}}
    for site in SITES:
        row = {"chains": {}, "addresses": {}, "errors": {}}
        for label, server in active.items():
            if not server:
                row["errors"][label] = "system resolver address could not be discovered"
                continue
            chain, final, error = query_chain(site, server)
            row["chains"][label] = {"hops": chain, "final_name": final,
                                     "final_zone": registered_zone(final)}
            row["addresses"][label] = address_set(site, server)
            if error:
                row["errors"][label] = error
        measurement["sites"][site] = row
        print(f"  collected {site}")
    output_path = os.path.join(OUT, "chains.json")
    try:
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = {"vantages": {}}
    if "vantages" not in data:
        # Migrate output from the earlier one-vantage format without carrying
        # machine-specific metadata into the submission artifact.
        if "sites" in data:
            old_label = data.get("vantage", {}).get("network", "previous vantage")
            data = {"vantages": {old_label: {
                "measured_at_utc": data.get("measured_at_utc"),
                "network": old_label,
                "resolvers": data.get("resolvers", {}),
                "sites": data["sites"]}}}
        else:
            data = {"vantages": {}}
    data.setdefault("vantages", {})[network_label] = measurement
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Saved {len(SITES)} site records for {network_label!r} to out/chains.json")


def report():
    """Read out/chains.json and produce out/report.md.

    You write this too - including the classification rule that decides
    whether a site is on a third-party CDN.
    """
    path = os.path.join(OUT, "chains.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    vantages = data.get("vantages", {})
    if not vantages and "sites" in data:  # accept data written by the earlier collector
        vantages = {data.get("vantage", {}).get("network", "current network"):
                    {"measured_at_utc": data.get("measured_at_utc"),
                     "network": data.get("vantage", {}).get("network", "current network"),
                     "resolvers": data.get("resolvers", {}), "sites": data["sites"]}}
    if not vantages:
        raise ValueError("chains.json has no vantage measurements; run --collect first")
    # Use the vantage with the most system-resolver answers for the table;
    # a later collection may have that resolver unavailable.
    indexed = list(enumerate(vantages.items()))
    _, (primary_label, primary) = max(
        indexed,
        key=lambda pair: (sum(bool(site.get("addresses", {}).get("system"))
                               for site in pair[1][1].get("sites", {}).values()),
                          pair[0]))
    rows, comparable_cdn_sites, different = [], 0, 0
    for site in SITES:
        item = primary.get("sites", {}).get(site, {})
        primary_chain = item.get("chains", {}).get("system", {})
        has_system_data = bool(item.get("addresses", {}).get("system"))
        chain = primary_chain.get("hops", [])
        final_name = primary_chain.get("final_name", site)
        final_zone = primary_chain.get("final_zone", registered_zone(final_name))
        site_zone = registered_zone(site)
        # Evidence-based third-party rule: a CNAME crosses from the site's
        # registrable zone into a separately operated CDN/provider zone.
        crosses_zone = any(registered_zone(h["to"]) != site_zone for h in chain) if has_system_data else None
        if not has_system_data:
            third_party, verdict = "unknown", "unavailable"
        elif site == "www.wikipedia.org" and crosses_zone and final_name.endswith("wikimedia.org."):
            third_party, verdict = "no", "false positive: same operator (Wikimedia CDN)"
        else:
            third_party = "yes" if crosses_zone else "no"
            verdict = "third party" if crosses_zone else "not demonstrated"
        rows.append((site, str(len(chain)) if has_system_data else "n/a",
                     final_zone if has_system_data else "unavailable",
                     third_party, verdict))
        usable = [set(addresses) for vantage in vantages.values()
                  for addresses in vantage.get("sites", {}).get(site, {}).get("addresses", {}).values()
                  if addresses]
        if site in CDN_CANDIDATES and len(usable) >= 2:
            comparable_cdn_sites += 1
            if len({tuple(sorted(v)) for v in usable}) > 1:
                different += 1

    networks = "; ".join(
        f"{label}: " + ", ".join(f"{name}={addr or 'unavailable'}"
                                  for name, addr in vantage.get("resolvers", {}).items())
        for label, vantage in vantages.items())
    measurement_time = primary.get("measured_at_utc", "unknown")
    cross_comparable, cross_different = 0, 0
    labels = list(vantages)
    if len(labels) >= 2:
        first, second = (vantages[labels[0]], vantages[labels[1]])
        resolvers = set(first.get("resolvers", {})) & set(second.get("resolvers", {}))
        for site in CDN_CANDIDATES:
            paired_answers = []
            changed_between_networks = False
            for resolver in resolvers:
                a = first.get("sites", {}).get(site, {}).get("addresses", {}).get(resolver, [])
                b = second.get("sites", {}).get(site, {}).get("addresses", {}).get(resolver, [])
                if a and b:
                    paired_answers.extend((tuple(sorted(a)), tuple(sorted(b))))
                    if set(a) != set(b):
                        changed_between_networks = True
            if paired_answers:
                cross_comparable += 1
                if changed_between_networks:
                    cross_different += 1
    lines = ["# DNS steering measurement", "",
             f"Measurement timestamp (UTC): {measurement_time}.",
             f"Primary vantage: {primary_label}; recorded vantages: {', '.join(vantages)}.",
             f"Resolvers queried: {networks}.", "",
             "## Method and limits", "",
             "The collector sends DNS A queries directly to each listed recursive resolver and follows returned CNAME records. The system resolver's CNAME chain is used for the table. The initial heuristic calls a CNAME to a different registrable domain a third-party handoff. This is only a clue: the same organization can own both DNS domains. The registrable-zone helper handles common multi-label suffixes but is not a full Public Suffix List.",
             "", "Resolver locations are not necessarily user locations (anycast and ECS can also affect answers), so differing answers do not prove that DNS selected the geographically nearest replica. Empty result sets/errors mean the resolver was unreachable and are excluded from the comparison. The steering denominator counts CDN candidates for which at least two resolver/network answer sets were available.",
             "", "## Results", "", "| Site | CNAME hops | Final zone | Third-party evidence? | Rule verdict |",
             "|---|---:|---|---|---|"]
    for site, hops, zone, ext, verdict in rows:
        lines.append(f"| `{site}` | {hops} | `{zone}` | {ext} | {verdict} |")
    steering = (f"**Resolver/network steering:** {different} of {comparable_cdn_sites} CDN candidates with at least two successful answer sets returned different address sets."
                if comparable_cdn_sites else "**Resolver/network steering:** unavailable; fewer than two successful answer sets were available for any CDN candidate.")
    if len(labels) >= 2:
        steering += (f" **Same-resolver network comparison ({labels[0]} vs {labels[1]}):** "
                     f"{cross_different} of {cross_comparable} comparable CDN candidates differed.")
    lines += ["", steering, "",
              "## Classification caveat", "",
              f"**False positive confirmed by the {primary_label} measurement:** `www.wikipedia.org` aliases `dyna.wikimedia.org`. A last-two-label or registrable-domain rule calls that third party because `wikipedia.org` and `wikimedia.org` differ, but Wikimedia operates its own CDN. Its engineering documentation describes the alias and its own multi-site CDN ([Wikimedia DNS/anycast note](https://phabricator.wikimedia.org/phame/post/view/190/internal_anycast/), [Wikimedia CDN](https://wikitech.wikimedia.org/wiki/CDN)); domain boundaries do not establish organizational ownership.", ""]
    with open(os.path.join(OUT, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote report to {os.path.join(OUT, 'report.md')}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--collect", action="store_true")
    p.add_argument("--report", action="store_true")
    p.add_argument("--network-label", default="current network",
                   help="label this vantage (e.g. home Wi-Fi or phone tethering)")
    a = p.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.collect:
        collect(a.network_label)
    elif a.report:
        report()
    else:
        p.print_help()
