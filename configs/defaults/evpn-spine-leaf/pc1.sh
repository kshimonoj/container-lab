# evpn-spine-leaf (L1) default config for PC1 (linux). Runs inside node netns (nsenter).
# L1 is underlay-only: PCs just bring eth1 up and wait. The IP is a future tenant
# host address (same /24 used in L3) but PC<->PC traffic does NOT pass in L1.
ip addr add 10.10.10.11/24 dev eth1
ip link set eth1 up
