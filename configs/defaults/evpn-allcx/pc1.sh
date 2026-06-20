# evpn-allcx default config for PC1 (linux). Runs inside node netns (nsenter).
# Group1 tenant host on VLAN10/VNI10010 (leaf1 1/1/3 access). Same VNI/subnet as PC3,
# so PC1<->PC3 reach each other across the EVPN-VXLAN fabric (leaf1<->leaf3 VTEPs).
ip addr add 10.10.10.11/24 dev eth1
ip link set eth1 up
