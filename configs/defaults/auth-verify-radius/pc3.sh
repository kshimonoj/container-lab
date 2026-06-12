# auth-verify-radius default config for PC3 (linux). Lines run inside node netns (nsenter).
# Role: user host on VLAN 11, default gateway = Core-1 SVI 10.1.11.1
ip addr add 10.1.11.10/24 dev eth1
ip link set eth1 up
ip route replace default via 10.1.11.1
