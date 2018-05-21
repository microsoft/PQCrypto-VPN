#!/bin/bash

# After unpacking staged tarball, do a couple of setup steps to start
# and stop OpenVPN automatically. This script must be run as root, so
# run it with sudo.

if [ ! -f /usr/local/openvpn/etc/server.ovpn ]; then
  cat << EOF

/usr/local/openvpn/etc/server.ovpn is not found! Please create this
configuration file and any required certs/keys referenced by it before
calling this script.

Aborting.

EOF
  exit 1
fi

# systemctl should display useful error messages on failure, so we can just
# abort the script when it does

systemctl daemon-reload || exit 1
systemctl enable pq-openvpn || exit 1
systemctl start pq-openvpn || exit 1

cat << EOF

Automatic startup has been configured. OpenVPN server has also been started.
If it's not running, check the log file for reasons startup may have failed.
You can manually attempt to restart as root with:

systemctl start pq-openvpn

EOF




