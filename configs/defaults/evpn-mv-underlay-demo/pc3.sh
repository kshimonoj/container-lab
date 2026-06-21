# evpn-mv-underlay-demo (underlay only) config for PC3 (linux). Runs inside node netns (nsenter).
# Group1 tenant host (将来 VLAN10/VNI10010, leaf3 1/1/3)。同 VNI/サブネットの PC1 と将来疎通。
# overlay 未投入のため現状は PC1 と不通 (before)。overlay 投入後に PC1<->PC3 が疎通する。
ip addr add 10.10.10.13/24 dev eth1
ip link set eth1 up
