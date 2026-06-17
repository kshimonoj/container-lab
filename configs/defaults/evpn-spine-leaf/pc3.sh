# evpn-spine-leaf (L1) default config for PC3 (linux). Runs inside node netns (nsenter).
# L1 is underlay-only: eth1 up + future tenant IP. PC<->PC does NOT pass in L1.
ip addr add 10.10.10.13/24 dev eth1
ip link set eth1 up
