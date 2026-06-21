# evpn-mv-underlay-demo (underlay only) config for PC1 (linux). Runs inside node netns (nsenter).
# Group1 tenant host (将来 VLAN10/VNI10010, leaf1 1/1/3)。overlay 未投入のため PC3 とは不通 (before)。
# overlay (evpn-mv-underlay-demo-answerkey.md) 投入後に PC1<->PC3 が疎通する。
ip addr add 10.10.10.11/24 dev eth1
ip link set eth1 up
