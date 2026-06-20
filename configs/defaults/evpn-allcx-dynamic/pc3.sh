# All-CX EVPN/VXLAN demo config for PC3 (linux). Runs inside node netns (nsenter).
# Group1 tenant host on VLAN10/VNI10010 (leaf3 1/1/3 access). Same VNI/subnet as PC1,
# so PC1<->PC3 reach each other across the VXLAN fabric (leaf1<->leaf3 VTEPs).
ip addr add 10.10.10.13/24 dev eth1
ip link set eth1 up
