#!/bin/sh
export PATH=/sbin:/bin:/usr/sbin:/usr/bin

# Fix file permissions
chmod a+r /usr/sbin/vacuula_logs.sh
chmod a+r /lib/systemd/system/usb-gadgets.service
chmod a+r /etc/systemd/system/vacuula-logs.service
chmod a+r /etc/systemd/resolved.conf
chmod a+r /etc/systemd/network/wireless.network
chmod a+r /home/root/tron/config/vendors.ini
chmod a+r /user/tron/local.ini
chmod a+r /home/root/tron/config/ssl/vacuula.crt
chmod a+r /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
chmod a+r /etc/hosts

# Disable "orbital." prefix in server address
if [ ! -f /home/root/tron/tron/configutils.py.bak ]
then
  sed -i.bak 's/"orbital\.%s"/"%s"/g' /home/root/tron/tron/configutils.py
fi

# Get new DHCP lease
systemctl restart systemd-networkd

# Enable mDNS resolution
ln -sf ../run/systemd/resolve/stub-resolv.conf /etc/resolv.conf

# Remove arbitrary limitations from robots
# NOTE: currently we add the same limit back via the app
# Temporarly limit to what the app did until we have manually verified that the same hardware is used in all gen4 robots
# this is to avoid burning out any motors or other components. Also, we have no idea of the D800 and so, so will need to be verified after
# initial release!
rm -f /user/databases/settings_D9

# run our extra services
systemctl daemon-reload
systemctl enable vacuula-logs.service
systemctl start --no-block vacuula-logs.service