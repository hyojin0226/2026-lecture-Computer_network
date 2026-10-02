#!/usr/bin/env python3
"""Week 3 · Task 1 — Build your own iterative resolver.

Textbook §2.4.2 - §2.4.3.

`dig +trace` walks root -> TLD -> authoritative for you. In this task you do
that walk yourself: start at a root server, read the delegation it returns,
ask the next server, and keep going until somebody answers authoritatively.

You may shell out to `dig` for the transport, or use a DNS library
(`dnspython` is in the container). Either is fine - what matters is that
*you* follow the delegations rather than letting a tool do it.

    python3 task1_resolve.py www.korea.ac.kr
    python3 task1_resolve.py --verify        # check yourself against dig

Pass condition
--------------
`--verify` resolves five names with your resolver and with `dig`, and the
addresses must agree. A name behind a CDN may legitimately return a different
address each time; the harness compares the *set of authoritative nameservers*
you ended at for those, not the address.
"""
import argparse, random, socket, struct, subprocess, sys

# Root servers. Everything starts here; there is no earlier step.
ROOT_SERVERS = [
    "198.41.0.4",       # a.root-servers.net
    "199.9.14.201",     # b.root-servers.net
    "192.33.4.12",      # c.root-servers.net
]

# (name, kind).  "stable" names must match dig exactly.  "cdn" names are served
# from many replicas and may legitimately give you a different address than dig
# got a second earlier - for those we only require that you reached an answer.
VERIFY_NAMES = [
    ("www.korea.ac.kr", "stable"),
    ("dns.google", "stable"),
    ("en.wikipedia.org", "stable"),
    ("www.stanford.edu", "stable"),
    ("www.microsoft.com", "cdn"),
]


class Resolver:
    """Your iterative resolver.

    The whole point is that you never ask a server to recurse for you.
    You ask one server, it says "not mine, ask over there", and you go there.

    Suggested shape - but it is yours to design:

        resolve(name) -> (address, path)
            address : the A record you ended up with, as a string
            path    : the servers you asked, in order, so you can show your work

    Things you will hit, in roughly this order:

    1.  A delegation gives you NS *names*, sometimes with glue A records and
        sometimes without. No glue means you have to resolve that nameserver's
        name first - which is another walk. Decide what you do there.
    2.  A server may not answer. Try the next one rather than giving up.
    3.  CNAMEs. The answer you get back may be a different name than the one
        you asked for, and you have to start again with that name.
    4.  Loops. Cap your depth.

    If you shell out to dig, the flag you want is `+norecurse`, so that the
    server you ask replies with a delegation instead of doing the work:

        dig @198.41.0.4 www.korea.ac.kr +norecurse
    """

    TIMEOUT = 2.0
    MAX_HOPS = 32

    @staticmethod
    def _encode_name(name):
        labels = name.rstrip(".").split(".")
        if any(not label or len(label.encode("ascii")) > 63 for label in labels):
            raise ValueError(f"invalid DNS name: {name!r}")
        return b"".join(bytes((len(label),)) + label.encode("ascii") for label in labels) + b"\0"

    @staticmethod
    def _read_name(packet, offset):
        labels, jumped, seen = [], False, set()
        end = offset
        while True:
            if offset >= len(packet):
                raise ValueError("truncated DNS name")
            size = packet[offset]
            if size & 0xC0 == 0xC0:
                if offset + 1 >= len(packet):
                    raise ValueError("truncated DNS compression pointer")
                pointer = ((size & 0x3F) << 8) | packet[offset + 1]
                if pointer in seen:
                    raise ValueError("DNS compression loop")
                seen.add(pointer)
                if not jumped:
                    end = offset + 2
                    jumped = True
                offset = pointer
                continue
            if size & 0xC0:
                raise ValueError("unsupported DNS label encoding")
            offset += 1
            if size == 0:
                return ".".join(labels) + ".", (end if jumped else offset)
            if offset + size > len(packet):
                raise ValueError("truncated DNS label")
            labels.append(packet[offset:offset + size].decode("ascii"))
            offset += size

    def _query(self, server, name, recursive=False, timeout=None):
        ident = random.randrange(0, 65536)
        question = self._encode_name(name) + struct.pack("!HH", 1, 1)  # IN A
        packet = struct.pack("!HHHHHH", ident, 0x0100 if recursive else 0, 1, 0, 0, 0) + question
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(self.TIMEOUT if timeout is None else timeout)
            sock.sendto(packet, (server, 53))
            reply, _ = sock.recvfrom(65535)
        if len(reply) < 12:
            raise ValueError("short DNS response")
        rid, flags, qd, an, ns, ar = struct.unpack("!HHHHHH", reply[:12])
        if rid != ident or not flags & 0x8000:
            raise ValueError("mismatched or non-response DNS packet")
        if flags & 0x0200:
            raise ValueError("truncated UDP DNS response")
        offset = 12
        for _ in range(qd):
            _, offset = self._read_name(reply, offset)
            offset += 4
        sections = {"answer": [], "authority": [], "additional": []}
        for section, count in (("answer", an), ("authority", ns), ("additional", ar)):
            for _ in range(count):
                owner, offset = self._read_name(reply, offset)
                if offset + 10 > len(reply):
                    raise ValueError("truncated resource record")
                rtype, rclass, ttl, rdlength = struct.unpack("!HHIH", reply[offset:offset + 10])
                offset += 10
                rstart, rend = offset, offset + rdlength
                if rend > len(reply):
                    raise ValueError("truncated resource data")
                rr = {"name": owner.lower(), "type": rtype, "class": rclass, "ttl": ttl}
                if rtype == 1 and rclass == 1 and rdlength == 4:
                    rr["data"] = socket.inet_ntoa(reply[rstart:rend])
                elif rtype in (2, 5) and rclass == 1:
                    rr["data"], _ = self._read_name(reply, rstart)
                    rr["data"] = rr["data"].lower()
                sections[section].append(rr)
                offset = rend
        rcode = flags & 0x000F
        if rcode not in (0, 3):
            raise OSError(f"DNS server returned rcode {rcode}")
        return flags, sections

    def _walk(self, name, path, depth, resolving_ns):
        if depth > self.MAX_HOPS:
            raise RuntimeError("maximum delegation/CNAME depth exceeded")
        current = name.rstrip(".").lower() + "."
        visited = set()
        servers = list(ROOT_SERVERS)
        for _ in range(self.MAX_HOPS):
            zone_key = (current, tuple(servers))
            if zone_key in visited:
                raise RuntimeError(f"delegation loop while resolving {current}")
            visited.add(zone_key)
            reply = None
            for server in servers:
                path.append(server)
                try:
                    reply = self._query(server, current)
                    break
                except (OSError, ValueError, socket.timeout):
                    continue
            if reply is None:
                raise TimeoutError(f"no responding nameserver for {current}")
            _, sections = reply
            answers = sections["answer"]
            addresses = [rr["data"] for rr in answers if rr["type"] == 1 and rr["name"] == current]
            if addresses:
                return addresses[0]
            aliases = [rr["data"] for rr in answers if rr["type"] == 5 and rr["name"] == current]
            if aliases:
                target = aliases[0]
                if target == current:
                    raise RuntimeError(f"CNAME loop at {current}")
                return self._walk(target, path, depth + 1, resolving_ns)

            ns_names = [rr["data"] for rr in sections["authority"]
                        if rr["type"] == 2 and rr["class"] == 1]
            if not ns_names:
                raise LookupError(f"no answer or delegation for {current}")
            glue = {rr["name"]: rr["data"] for rr in sections["additional"]
                    if rr["type"] == 1}
            next_servers = [glue[ns] for ns in ns_names if ns in glue]
            if not next_servers:
                next_servers = []
                for ns in ns_names:
                    if ns in resolving_ns:
                        continue
                    try:
                        ip = self._walk(ns, path, depth + 1, resolving_ns | {ns})
                        if ip not in next_servers:
                            next_servers.append(ip)
                    except (OSError, LookupError, RuntimeError, TimeoutError):
                        continue
            if not next_servers:
                raise LookupError(f"no usable glue or nameserver address for {current}")
            servers = next_servers
        raise RuntimeError("maximum delegation depth exceeded")

    def resolve(self, name):
        path = []
        address = self._walk(name, path, 0, set())
        return address, path


# ------------------------------------------------------------------- harness
def dig_answer(name):
    """Return A answers from dig, falling back to the OS resolver."""
    try:
        out = subprocess.run(["dig", "+short", name, "A"],
                             capture_output=True, text=True, timeout=5).stdout
        answers = [line for line in out.split() if line and line[0].isdigit()]
        if answers:
            return answers
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        return list(dict.fromkeys(
            result[4][0] for result in socket.getaddrinfo(
                name, None, socket.AF_INET, socket.SOCK_STREAM
            )
        ))
    except socket.gaierror:
        return []


def verify():
    r, failures, checked, skipped = Resolver(), 0, 0, 0
    for name, kind in VERIFY_NAMES:
        try:
            addr, path = r.resolve(name)
        except NotImplementedError:
            print("Nothing implemented yet - write Resolver.resolve first.")
            return 1
        except TimeoutError as e:
            print(f"  SKIP  {name:<22} direct DNS unreachable: {e}; use path B")
            skipped += 1
            continue
        except Exception as e:
            print(f"  FAIL  {name:<22} your resolver raised {e!r}")
            failures += 1
            continue
        expected = dig_answer(name)
        if not expected:
            print(f"  SKIP  {name:<22} reference dig unavailable; use the supplied DNS trace (path B)")
            skipped += 1
            continue
        checked += 1
        if addr in expected:
            note = ""
        elif kind == "cdn":
            note = "  <- differs, but this name is CDN-hosted. Explain it."
        else:
            note = "  <- should have matched"
            failures += 1
        print(f"  {'FAIL' if note.endswith('matched') else 'ok  '}  {name:<22} "
              f"you={addr:<16} dig={','.join(expected) or '-'}   "
              f"hops={len(path)}{note}")
    print(f"\n  {checked - failures}/{checked} checked ok; {skipped} skipped")
    return 1 if failures else 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("name", nargs="?", default="www.korea.ac.kr")
    p.add_argument("--verify", action="store_true")
    a = p.parse_args()

    if a.verify:
        sys.exit(verify())

    addr, path = Resolver().resolve(a.name)
    for i, server in enumerate(path, 1):
        print(f"  {i}. asked {server}")
    print(f"\n  {a.name} -> {addr}")


if __name__ == "__main__":
    main()
