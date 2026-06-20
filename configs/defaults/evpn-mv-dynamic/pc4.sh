# evpn-mv-dynamic (vJunos RR + CX VTEP) config for PC4 (linux). Runs inside node netns (nsenter).
# Group2 tenant host on VLAN20/VNI10020 (leaf3 1/1/4 access). Same VNI/subnet as PC2,
# so PC2<->PC4 reach each other across the VXLAN fabric (leaf2<->leaf3 dynamic VTEPs).
# Different VNI/subnet from Group1 (PC1/PC3): ping to 10.10.10.x must fail.
ip addr add 10.10.20.14/24 dev eth1
ip link set eth1 up
