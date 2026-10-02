# Observations

## Task 1
The root referral (ID 59142) returned six .kr NS records without an A answer; the next referral (ID 25274) delegated korea.ac.kr, whose authoritative server returned 163.152.6.10 (ID 47395). I did not observe a no-glue delegation in my capture, so the resolver handles one by resolving the NS hostname from the root first. Microsoft initially failed because a .net response was truncated over UDP; retrying over TCP fixed it, and `--verify` now matches all five names.

## Task 2
My suffix rule calls a CNAME crossing registrable domains third-party evidence, but the measured www.wikipedia.org to dyna.wikimedia.org chain is a false positive because Wikimedia operates its own CDN. Across resolver/network answer sets, 8 of 11 CDN candidates differed; with the same resolver compared across school Wi-Fi and tethering, 3 of 10 comparable candidates differed, which still does not prove DNS selected the nearest replica.

## Task 3
The baseline discards the authoritative TTL and uses a fixed 60-second lifetime, causing stale answers and unnecessary refreshes; its list scan also makes lookup linear. The correct-cache floor for this fixed workload is 275 upstream queries: each first lookup and each first lookup after TTL expiry must fetch a fresh answer, and YourCache makes exactly those queries.
