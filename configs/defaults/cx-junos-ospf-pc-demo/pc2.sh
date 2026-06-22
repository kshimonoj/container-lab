# cx-junos-ospf-pc-demo default config for PC2 (linux). Runs inside node netns (nsenter).
# Host in 10.0.2.0/24 behind vsw1 (eth1 = data link; eth0 is clab mgmt).
# Default route via vsw1 (10.0.2.1) ONLY — PC2 has no path to PC1's subnet
# (10.0.1.0/24) until OSPF installs the route on the routers.
ip link set eth1 up
ip addr add 10.0.2.10/24 dev eth1
ip route replace default via 10.0.2.1
