# Observations

## Task 1
The root referral (ID 59142) returned six .kr NS records in Authority with ANCOUNT=0; the next referral (ID 25274) delegated korea.ac.kr, and ID 47395 returned A 163.152.6.10. The largest captured response frame was 383 bytes; I did not observe a no-glue case, so the resolver resolves an NS name from the root when glue is absent. `--verify` matched 4 of 4 completed checks; the Microsoft CDN name timed out at its authoritative servers in this network.

## Task 2
My suffix rule calls a CNAME crossing registrable domains third-party evidence, but the measured www.wikipedia.org to dyna.wikimedia.org chain is a false positive because Wikimedia operates its own CDN. Across resolver/network answer sets, 8 of 11 CDN candidates differed; with the same resolver compared across school Wi-Fi and tethering, 3 of 10 comparable candidates differed, which still does not prove DNS selected the nearest replica.

## Task 3
The baseline discards the authoritative TTL and uses a fixed 60-second lifetime, causing stale answers and unnecessary refreshes; its list scan also makes lookup linear. The correct-cache floor for this fixed workload is 275 upstream queries: each first lookup and each first lookup after TTL expiry must fetch a fresh answer, and YourCache makes exactly those queries.
