# cx-junos-ospf-pc-demo default config for PC1 (linux). Runs inside node netns (nsenter).
# Host in 10.0.1.0/24 behind sw01 (eth1 = data link; eth0 is clab mgmt).
# Default route via sw01 (10.0.1.1) ONLY — PC1 has no path to PC2's subnet
# (10.0.2.0/24) until OSPF installs the route on the routers. The ping test
# always targets data-plane IPs, never the clab mgmt subnet.
ip link set eth1 up
ip addr add 10.0.1.10/24 dev eth1
ip route replace default via 10.0.1.1
