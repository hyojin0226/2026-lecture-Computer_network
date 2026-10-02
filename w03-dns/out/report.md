# DNS steering measurement

Measurement timestamp (UTC): 2026-10-02T06:44:23Z.
Primary vantage: 학교 Wi-Fi; recorded vantages: 학교 Wi-Fi, 휴대폰 테더링.
Resolvers queried: 학교 Wi-Fi: system=163.152.213.9, google=8.8.8.8, quad9=9.9.9.9; 휴대폰 테더링: system=unavailable, google=8.8.8.8, quad9=9.9.9.9.

## Method and limits

The collector sends DNS A queries directly to each listed recursive resolver and follows returned CNAME records. The system resolver's CNAME chain is used for the table. The initial heuristic calls a CNAME to a different registrable domain a third-party handoff. This is only a clue: the same organization can own both DNS domains. The registrable-zone helper handles common multi-label suffixes but is not a full Public Suffix List.

Resolver locations are not necessarily user locations (anycast and ECS can also affect answers), so differing answers do not prove that DNS selected the geographically nearest replica. Empty result sets/errors mean the resolver was unreachable and are excluded from the comparison. The steering denominator counts CDN candidates for which at least two resolver/network answer sets were available.

## Results

| Site | CNAME hops | Final zone | Third-party evidence? | Rule verdict |
|---|---:|---|---|---|
| `www.microsoft.com` | 2 | `akamaiedge.net` | yes | third party |
| `www.netflix.com` | 1 | `netflix.com` | no | not demonstrated |
| `www.adobe.com` | 2 | `akamai.net` | yes | third party |
| `www.cnn.com` | 1 | `fastly.net` | yes | third party |
| `www.apple.com` | 3 | `akamaiedge.net` | yes | third party |
| `www.korea.ac.kr` | 0 | `korea.ac.kr` | no | not demonstrated |
| `www.stanford.edu` | 1 | `netlifyglobalcdn.com` | yes | third party |
| `www.bbc.co.uk` | 2 | `fastly.net` | yes | third party |
| `www.spotify.com` | 1 | `fastly.net` | yes | third party |
| `www.github.com` | 1 | `github.com` | no | not demonstrated |
| `www.wikipedia.org` | 1 | `wikimedia.org` | no | false positive: same operator (Wikimedia CDN) |
| `www.nytimes.com` | 3 | `fastly.net` | yes | third party |

**Resolver/network steering:** 8 of 11 CDN candidates with at least two successful answer sets returned different address sets. **Same-resolver network comparison (학교 Wi-Fi vs 휴대폰 테더링):** 3 of 10 comparable CDN candidates differed.

## Classification caveat

**False positive confirmed by the 학교 Wi-Fi measurement:** `www.wikipedia.org` aliases `dyna.wikimedia.org`. A last-two-label or registrable-domain rule calls that third party because `wikipedia.org` and `wikimedia.org` differ, but Wikimedia operates its own CDN. Its engineering documentation describes the alias and its own multi-site CDN ([Wikimedia DNS/anycast note](https://phabricator.wikimedia.org/phame/post/view/190/internal_anycast/), [Wikimedia CDN](https://wikitech.wikimedia.org/wiki/CDN)); domain boundaries do not establish organizational ownership.
