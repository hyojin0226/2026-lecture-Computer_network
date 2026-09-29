#!/usr/bin/env python3
"""Task 1: follow DNS delegations yourself, starting at a root server."""
import argparse
import socket
import subprocess
import sys

from dns_wire import query

ROOT_SERVERS = ["198.41.0.4", "199.9.14.201", "192.33.4.12"]
VERIFY_NAMES = [("www.korea.ac.kr", "stable"), ("dns.google", "stable"),
                ("en.wikipedia.org", "stable"), ("www.stanford.edu", "stable"),
                ("www.microsoft.com", "cdn")]


class Resolver:
    def __init__(self, max_depth=16, timeout=2.0):
        self.max_depth, self.timeout = max_depth, timeout

    def _lookup(self, name, depth, visited):
        if depth > self.max_depth:
            raise RuntimeError("delegation/CNAME depth limit reached")
        name = name.rstrip(".").lower()
        if name in visited:
            raise RuntimeError("DNS delegation or CNAME loop")
        visited.add(name)
        servers, path = ROOT_SERVERS[:], []
        for _ in range(self.max_depth):
            referral = None
            for server in servers:
                try:
                    response = query(server, name, "A", self.timeout, recursive=False)
                    path.append(server)
                    if response["answers"]:
                        answers = response["answers"]
                        cnames = [r["value"] for r in answers if r["type"] == 5]
                        addresses = [r["value"] for r in answers if r["type"] == 1]
                        if addresses:
                            return addresses[0], path
                        if cnames:
                            address, tail = self._lookup(cnames[0], depth + 1, visited)
                            return address, path + tail
                    ns_names = [r["value"] for r in response["authority"] if r["type"] == 2]
                    if ns_names:
                        glue = {r["name"]: r["value"] for r in response["additional"]
                                if r["type"] == 1}
                        next_servers = [glue[n.lower()] for n in ns_names if n.lower() in glue]
                        if not next_servers:
                            for ns in ns_names:
                                try:
                                    ip, _ = self._lookup(ns, depth + 1, visited.copy())
                                    next_servers.append(ip)
                                except (OSError, RuntimeError, ValueError):
                                    continue
                        if next_servers:
                            referral = next_servers
                            break
                except (OSError, RuntimeError, ValueError, struct_error()):
                    continue
            if not referral:
                raise RuntimeError(f"no reachable delegation/answer for {name}")
            servers = referral
        raise RuntimeError(f"too many referrals for {name}")

    def resolve(self, name):
        return self._lookup(name, 0, set())


def struct_error():
    # Avoid importing struct solely for a common malformed/network timeout path.
    import struct
    return struct.error


def dig_answer(name):
    if shutil_which("dig"):
        out = subprocess.run(["dig", "+short", "+time=2", "+tries=1", name, "A"],
                             capture_output=True, text=True).stdout
        return [line.strip() for line in out.splitlines()
                if line.strip() and line.strip()[0].isdigit()]
    try:
        return sorted({item[4][0] for item in socket.getaddrinfo(name, None,
                      socket.AF_INET, socket.SOCK_STREAM)})
    except OSError:
        return []


def shutil_which(program):
    import shutil
    return shutil.which(program)


def verify():
    failures = 0
    for name, kind in VERIFY_NAMES:
        try:
            addr, path = Resolver().resolve(name)
            expected = dig_answer(name)
            ok = addr in expected or kind == "cdn"
            print(f"  {'ok  ' if ok else 'FAIL'}  {name:<22} you={addr:<16} "
                  f"dig={','.join(expected) or '-'} hops={len(path)}" +
                  (" <- CDN answer can vary" if addr not in expected and kind == "cdn" else ""))
            failures += not ok
        except Exception as exc:
            print(f"  FAIL  {name:<22} {exc!r}")
            failures += 1
    print(f"\n  {len(VERIFY_NAMES)-failures}/{len(VERIFY_NAMES)} ok")
    return int(bool(failures))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name", nargs="?", default="www.korea.ac.kr")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        sys.exit(verify())
    address, path = Resolver().resolve(args.name)
    for i, server in enumerate(path, 1):
        print(f"  {i}. asked {server}")
    print(f"\n  {args.name} -> {address}")


if __name__ == "__main__":
    main()
