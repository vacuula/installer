#!/bin/sh
export PATH=/sbin:/bin:/usr/sbin:/usr/bin

sleep 60

chmod 1777 /tmp/vacuula-logs

/bin/journalctl -b -eu tron.service > /tmp/vacuula-logs/tron.log &
/bin/journalctl -b -eu robot.service > /tmp/vacuula-logs/robot.log &
/bin/journalctl -b -eu wpa_supplicant@wlan0.service > /tmp/vacuula-logs/wifi.log &
/bin/dmesg > /tmp/vacuula-logs/kernel.log &
/bin/systemctl > /tmp/vacuula-logs/systemctl.log &
/sbin/ip a > /tmp/vacuula-logs/ip.log &
/bin/ls -lahR /user > /tmp/vacuula-logs/user-tree.log &

# change to cyan to signal "vacuula logs"
/usr/local/bin/roboctrl -l a:1:t:0:g:255:255:1000:0:0+b:255:255:1000:0:0

/bin/tar -czf /tmp/vacuula-logs/vacuula.logs -C /tmp/vacuula-logs .
rm -f /tmp/vacuula-logs/*.log

sleep 300
rm -f /tmp/vacuula-logs/*
