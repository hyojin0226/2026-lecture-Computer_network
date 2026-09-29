# DNS steering and CDN observations

Rule: label a site third-party when the final CNAME target's last two labels differ from the site's last two labels. This is a deliberately simple suffix rule; it cannot identify provider ownership, private CDN infrastructure, or a CDN served directly by A/AAAA records.

| Site | Chain length | Final zone | Third-party evidence | Rule verdict |
|---|---:|---|---|---|
| `www.microsoft.com` | 2 | `akamaiedge.net` | CNAME chain | third-party (rule says yes) |
| `www.netflix.com` | 1 | `netflix.com` | CNAME chain | not third-party (rule says no) |
| `www.adobe.com` | 2 | `akamai.net` | CNAME chain | third-party (rule says yes) |
| `www.cnn.com` | 1 | `fastly.net` | CNAME chain | third-party (rule says yes) |
| `www.apple.com` | 3 | `akamaiedge.net` | CNAME chain | third-party (rule says yes) |
| `www.korea.ac.kr` | 0 | `ac.kr` | no CNAME observed | not third-party (rule says no) |
| `www.stanford.edu` | 1 | `netlifyglobalcdn.com` | CNAME chain | third-party (rule says yes) |
| `www.bbc.co.uk` | 2 | `fastly.net` | CNAME chain | third-party (rule says yes) |
| `www.spotify.com` | 1 | `fastly.net` | CNAME chain | third-party (rule says yes) |
| `www.github.com` | 1 | `github.com` | CNAME chain | not third-party (rule says no) |
| `www.wikipedia.org` | 1 | `wikimedia.org` | CNAME chain | third-party (rule says yes) |
| `www.nytimes.com` | 3 | `fastly.net` | CNAME chain | third-party (rule says yes) |

**Steering count:** 12 sites measured; among 11 with a CNAME delivery chain, 8 returned different A-record sets across the configured resolvers.

**Rule failure:** `www.wikipedia.org` is a false positive. Its chain ends at `dyna.wikimedia.org`, so comparing the last two labels says ‘third-party’; Wikimedia domains are operated by the same Wikimedia organization, so the different suffix does not prove a third-party CDN. Conversely, Netflix's own CDN ends inside `netflix.com`. A hostname suffix is not reliable evidence of provider ownership.

Measurements are a time and vantage-point snapshot; differing answers show resolver-dependent steering, not that the chosen replica is geographically closest.
