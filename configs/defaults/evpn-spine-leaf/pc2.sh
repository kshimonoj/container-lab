# evpn-spine-leaf (L3) default config for PC2 (linux). Runs inside node netns (nsenter).
# Group2 tenant host on VLAN20/VNI10020 (leaf2 1/1/3 access). Different VNI AND subnet
# from Group1 (PC1/PC3), so PC2 is fully isolated: ping to 10.10.10.x must fail.
ip addr add 10.10.20.12/24 dev eth1
ip link set eth1 up
