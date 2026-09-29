# DNS trace source and attribution

These files were extracted from the official Kurose and Ross Wireshark Labs
9th-edition archive, `wireshark-traces-9e.zip`:

- `dns-wireshark-trace1-1.pcapng` and `dns-wireshark-trace1-2.pcap`
- `dns-wireshark-trace2-1.pcapng` and `dns-wireshark-trace2-2.pcap`
- `dns-wireshark-trace3-1.pcapng` and `dns-wireshark-trace3-2.pcap`

Source: https://gaia.cs.umass.edu/kurose_ross/wireshark.php
The trace archive and lab materials are copyright J.F. Kurose and K.W. Ross.
The DNS lab identifies trace 3 as the offline trace for its `NS umass.edu`
lookup exercise. In that capture the client asks its local recursive resolver;
it is not a packet-by-packet capture of the root-to-TLD walk.
