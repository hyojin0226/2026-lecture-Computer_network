#!/usr/bin/env python3
"""TTL-correct DNS cache for the deterministic cache benchmark."""


class BaselineCache:
    FIXED_LIFETIME = 60

    def __init__(self, upstream):
        self.upstream = upstream
        self.entries = []

    def lookup(self, name, now):
        for entry in self.entries:
            if entry[0] == name:
                if now - entry[2] < self.FIXED_LIFETIME:
                    return entry[1]
                self.entries.remove(entry)
                break
        address, ttl = self.upstream(name)
        self.entries.append([name, address, now])
        return address

    def stats(self):
        return {"entries": len(self.entries)}


class YourCache:
    """Dictionary-backed cache that expires each answer at its actual TTL."""

    def __init__(self, upstream):
        self.upstream = upstream
        self.entries = {}  # name -> (address, expiration time)

    def lookup(self, name, now):
        cached = self.entries.get(name)
        if cached is not None:
            address, expires_at = cached
            if now < expires_at:
                return address
            del self.entries[name]
        address, ttl = self.upstream(name)
        self.entries[name] = (address, now + max(0, ttl))
        return address

    def stats(self):
        return {"entries": len(self.entries)}
