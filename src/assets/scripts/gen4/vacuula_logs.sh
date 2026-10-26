#!/bin/sh
export PATH=/sbin:/bin:/usr/sbin:/usr/bin

echo "logs script started" > /tmp/vacuula-logs/vacuula.log

sleep 60

/usr/local/bin/roboctrl -l a:1:t:0:r:0:255:1000:1000:0+g:0:100:1000:1000:0

echo "collecting logs" >> /tmp/vacuula-logs/vacuula.log

chmod 1777 /tmp/vacuula-logs

/bin/journalctl -b -eu tron.service > /tmp/vacuula-logs/tron.log
/bin/journalctl -b -eu robot.service > /tmp/vacuula-logs/robot.log
/bin/journalctl -b -eu wpa_supplicant@wlan0.service > /tmp/vacuula-logs/wifi.log
/bin/dmesg > /tmp/vacuula-logs/kernel.log
/bin/systemctl > /tmp/vacuula-logs/systemctl.log
/sbin/ip a > /tmp/vacuula-logs/ip.log
/bin/ls -lahR /user > /tmp/vacuula-logs/user-tree.log
/bin/cat /etc/hosts > /tmp/vacuula-logs/hosts.log

echo "logs collected" >> /tmp/vacuula-logs/vacuula.log

echo "trying traceroute" >> /tmp/vacuula-logs/vacuula.log
IP="$(sed -n '1p' /user/tron/vacuula.ini)"

traceroute $IP > /tmp/vacuula-logs/traceroute.log 2>&1

if ! traceroute vacuula.local >> /tmp/vacuula-logs/traceroute.log 2>&1; then
    echo "traceroute to vacuula.local failed, replacing entry in /etc/hosts" > /tmp/vacuula-logs/vacuula.log

    if [ -n "$IP" ]; then
        grep -v "vacuula.local" /etc/hosts > /tmp/hosts.new
        echo "$IP vacuula.local" >> /tmp/hosts.new

        cat /tmp/hosts.new > /etc/hosts
        rm -f /tmp/hosts.new
    fi

    echo "retry after /etc/hosts update" >> /tmp/vacuula-logs/traceroute.log
    traceroute vacuula.local >> /tmp/vacuula-logs/traceroute.log 2>&1
fi

echo "traceroute done" >> /tmp/vacuula-logs/vacuula.log

# make a tarball of logs and remove log files
/bin/tar -czf /tmp/vacuula-logs/vacuula.logs -C /tmp/vacuula-logs .
rm -f /tmp/vacuula-logs/*.log

# change to cyan to signal "vacuula logs done!"
/usr/local/bin/roboctrl -l a:1:t:0:g:255:255:1000:0:0+b:255:255:1000:0:0

sleep 300
rm -f /tmp/vacuula-logs/*
