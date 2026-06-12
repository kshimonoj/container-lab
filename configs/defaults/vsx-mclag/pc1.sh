# vsx-mclag default config for PC (linux). Lines run inside the node netns (nsenter).
# Role: host in VLAN 10, default gateway = VSX active-gateway 10.1.10.1
ip addr add 10.1.10.20/24 dev eth1
ip link set eth1 up
ip route replace default via 10.1.10.1
