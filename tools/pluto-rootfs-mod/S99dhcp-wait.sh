#!/bin/sh
# eth0 DHCP fix: stock ifup runs "udhcpc -n", which exits before the PHY
# finishes auto-negotiation, so avahi-autoipd grabs a 169.254.x address.
# Wait for carrier, clear the fallback, then run udhcpc with retries (no -n).
case "$1" in
  start)
    (
      i=0
      while [ "$i" -lt 30 ]; do
        [ "$(cat /sys/class/net/eth0/carrier 2>/dev/null)" = "1" ] && break
        sleep 1; i=$((i+1))
      done
      killall avahi-autoipd 2>/dev/null
      killall udhcpc 2>/dev/null
      ip addr flush dev eth0 2>/dev/null
      ip link set eth0 up 2>/dev/null
      udhcpc -i eth0 -b -t 10 -T 3 -A 5 -p /var/run/udhcpc.eth0.pid
    ) &
    ;;
esac