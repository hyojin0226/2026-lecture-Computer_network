"""Small dependency-free DNS/UDP helpers used by the week 3 exercises."""
import random
import re
import socket
import struct
import subprocess

TYPE = {"A": 1, "NS": 2, "CNAME": 5, "SOA": 6, "AAAA": 28}


def encode_name(name):
    name = name.rstrip(".")
    if not name:
        return b"\0"
    return b"".join(bytes((len(label.encode("idna")),)) + label.encode("idna")
                     for label in name.split(".")) + b"\0"


def decode_name(packet, offset):
    labels, jumped, end, seen = [], False, offset, set()
    while True:
        if offset >= len(packet):
            raise ValueError("truncated DNS name")
        length = packet[offset]
        if length & 0xC0 == 0xC0:
            pointer = ((length & 0x3F) << 8) | packet[offset + 1]
            if pointer in seen:
                raise ValueError("DNS compression loop")
            seen.add(pointer)
            if not jumped:
                end = offset + 2
                jumped = True
            offset = pointer
            continue
        if length & 0xC0:
            raise ValueError("invalid DNS label")
        offset += 1
        if length == 0:
            return ".".join(labels) + ".", (end if jumped else offset)
        labels.append(packet[offset:offset + length].decode("idna"))
        offset += length


def query(server, name, qtype="A", timeout=2.0, recursive=True):
    """Issue one nonrecursive UDP query and return parsed sections."""
    ident = random.randrange(65536)
    question = encode_name(name) + struct.pack("!HH", TYPE[qtype], 1)
    packet = struct.pack("!HHHHHH", ident, 0x0100 if recursive else 0, 1, 0, 0, 0) + question
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(packet, (server, 53))
        data, _ = sock.recvfrom(65535)
    finally:
        sock.close()
    if len(data) < 12:
        raise ValueError("short DNS response")
    rid, flags, qd, an, ns, ar = struct.unpack("!HHHHHH", data[:12])
    if rid != ident:
        raise ValueError("DNS transaction ID mismatch")
    off = 12
    for _ in range(qd):
        _, off = decode_name(data, off)
        off += 4
    sections = []
    for count in (an, ns, ar):
        records = []
        for _ in range(count):
            owner, off = decode_name(data, off)
            rtype, rclass, ttl, rdlen = struct.unpack("!HHIH", data[off:off + 10])
            off += 10
            start, end = off, off + rdlen
            if rtype in (2, 5):
                value, _ = decode_name(data, start)
            elif rtype == 1 and rdlen == 4:
                value = socket.inet_ntoa(data[start:end])
            elif rtype == 28 and rdlen == 16:
                value = socket.inet_ntop(socket.AF_INET6, data[start:end])
            else:
                value = data[start:end].hex()
            records.append({"name": owner.lower(), "type": rtype,
                            "class": rclass, "ttl": ttl, "value": value})
            off = end
        sections.append(records)
    return {"flags": flags, "answers": sections[0],
            "authority": sections[1], "additional": sections[2]}


def system_resolvers():
    """Read configured resolvers where possible; otherwise use public defaults."""
    try:
        with open("/etc/resolv.conf", encoding="ascii") as f:
            found = [line.split()[1] for line in f if line.startswith("nameserver ")]
        if found:
            return found
    except OSError:
        pass
    if __import__("os").name == "nt":
        try:
            result = subprocess.run(["ipconfig", "/all"], capture_output=True,
                                    text=True, timeout=3)
            # Keep IPv4 resolver addresses; labels and indentation vary by locale.
            match = re.search(r"(?im)^\s*DNS Servers?[^\r\n]*:\s*([\d.]+)", result.stdout)
            addresses = [match.group(1)] if match else []
            if addresses:
                return list(dict.fromkeys(addresses))
        except (OSError, subprocess.SubprocessError):
            pass
    return ["8.8.8.8"]
