# auth-verify-radius default config for RADIUS (linux). Lines run inside node netns (nsenter).
# Role: FreeRADIUS server on service VLAN 99. clients/authorize come from mounted templates.
ip addr add 10.1.99.10/24 dev eth1
ip link set eth1 up
