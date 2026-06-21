# evpn-mv-underlay-demo (underlay only) config for PC4 (linux). Runs inside node netns (nsenter).
# Group2 tenant host (将来 VLAN20/VNI10020, leaf3 1/1/4)。同 VNI/サブネットの PC2 と将来疎通。
# overlay 未投入のため現状は PC2 と不通 (before)。overlay 投入後に PC2<->PC4 が疎通する。
ip addr add 10.10.20.14/24 dev eth1
ip link set eth1 up
