# evpn-mv-underlay-demo (underlay only) config for PC2 (linux). Runs inside node netns (nsenter).
# Group2 tenant host (将来 VLAN20/VNI10020, leaf2 1/1/3)。overlay 未投入のため PC4 とは不通 (before)。
# overlay (evpn-mv-underlay-demo-answerkey.md) 投入後に PC2<->PC4 が疎通する。
ip addr add 10.10.20.12/24 dev eth1
ip link set eth1 up
