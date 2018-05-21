#!/bin/bash

# Script to start OpenVPN, a wireless access point, and tunnel traffic from the
# AP over the VPN. 
#
# The starting point for this script was this article/code by Jared Haight
# (accessed May 2017):
# https://www.psattack.com/articles/20160410/setting-up-a-wireless-access-point-in-kali/ 

# This has to be run as root
if [ "$EUID" -ne 0 ]
    then echo "Please run as root"
    exit
fi


AP_DEVICE=wlan0
INET_DEVICE=tun0

HOSTNAME=`hostname`
BASE_PATH=/home/$HOSTNAME/vpn
RESOLV_CONF_BAK=$BASE_PATH/resolv.conf.bak
AZURE_DNS_SERVER="168.63.129.16"
LOG_OF_THIS_SCRIPT=$BASE_PATH/log/pqap.log

OPENVPN=$BASE_PATH/openvpn
OPENVPN_CONFIG=$BASE_PATH/client.ovpn
OPENVPN_LOG=$BASE_PATH/log/openvpn.log
OPENVPN_CACERT=$BASE_PATH/creds/ca.crt
OPENVPN_TIMEOUT=10

DNSMASQ_CONFIG=$BASE_PATH/dnsmasq.conf
DNSMASQ_HOSTS=$BASE_PATH/hosts.conf
DNSMASQ_LOG=$BASE_PATH/log/dnsmasq.log
HOSTAPD_CONFIG=$BASE_PATH/hostapd.conf
HOSTAPD_LOG=$BASE_PATH/log/ap.log

OPENSSL_LIB_PATH=/opt/openssl/lib/

exec 2> $LOG_OF_THIS_SCRIPT    # log stderr to file
exec 1>&2                      # send stdout to the same log file
set -x                         # tell bash to display commands before execution, for logging 

# Catch ctrl c so we can exit cleanly
trap pqap_stop INT

function pqap_stop(){
    echo Killing dnsmasq, hostapd and openvpn processes..
    killall dnsmasq
    killall hostapd
    killall openvpn

    chattr -i /etc/resolv.conf
    if [ -e "$RESOLV_CONF_BAK" ] ; then 
        cp $RESOLV_CONF_BAK /etc/resolv.conf
	rm $RESOLV_CONF_BAK
    fi
}

# Exit if the specified interface is not present
function ensure_interface_up(){

    ifconfig $1 up

    local output=`ifconfig |grep -o $1`;
    if [ "$output" == "$1" ] ; then
	    echo "Interface $1 is up";
    else
	    echo "Interface $1 not found";
        exit
    fi
}

# Return 1 if the interface is present, 0 otherwise
function is_interface_up(){

    local output=`ifconfig |grep -o $1`;
    if [ "$output" == "$1" ] ; then
	    echo 1; 
    else
        echo 0;
    fi
}


function start_openvpn(){

    echo "Starting OpenVPN"
    $OPENVPN --daemon --log $OPENVPN_LOG --ca $OPENVPN_CACERT --config $OPENVPN_CONFIG

    if ! (pgrep -x "openvpn" > /dev/null) ; then
	    echo "openvpn failed to start -- see $OPENVPN_LOG" 
    fi 

    local count=0 
    while ! [ "`ifconfig |grep -o tun0`" == "tun0" ]  
    do
        echo "."
        sleep 1;
	    count=$(($count+1))
	    if [ $count == $OPENVPN_TIMEOUT ] ; then
		    echo "OpenVPN failed to create tun0 interface, is the server up?";
            return;
	    fi
    done

    echo "OpenVPN started"
}


function pqap_restart(){
    pqap_stop
    pqap_start
}

function check_deps(){
    if [ ! -e "$OPENSSL_LIB_PATH/libssl.so" ] ; then
        echo "Missing $OPENSSL_LIB_PATH/libssl.so, is it installed?"
        exit
    fi
    if [ ! -e "$OPENSSL_LIB_PATH/libcrypto.so" ] ; then
        echo "Missing $OPENSSL_LIB_PATH/libcrypto.so, is it installed?"
        exit
    fi

    if [ ! -e "$BASE_PATH/log/openvpn.log" ] ; then 
        # Run ldconfig on first boot to make sure the OQS fork of OpenSSL is
        # by OpenVPN
        ldconfig $OPENSSL_LIB_PATH
    fi

    # Make sure the system's instance of dnsmasq is not running; otherwise we
    # can't start ours
    systemctl stop dnsmasq
    sleep 2
}

function pqap_start(){

    check_deps

    # We'll try to start openvpn, if we have internet it should connect
    # If not, we'll just start the AP, so the user can configure the internet
    start_openvpn


    # If the tunnel is up, we'll route traffic too
    have_tunnel=$(is_interface_up $INET_DEVICE)

    # make sure iptables is not fowarding
    iptables --flush
    sysctl -w net.ipv4.ip_forward=0

    ifconfig $AP_DEVICE 10.0.0.1/24 up

    # (Re)Start dnsmasq
    killall dnsmasq
    dnsmasq -C $DNSMASQ_CONFIG -H $DNSMASQ_HOSTS --log-facility=$DNSMASQ_LOG
   
    # Start hostapd
    # Only start hostapd if it's not already running; we don't want to 
    # disconnect anyone that might be using the web UI
    if ! (pgrep -x "hostapd" > /dev/null) ; then
        # We need the AP device to start the hotspot 
        ensure_interface_up $AP_DEVICE
        hostapd $HOSTAPD_CONFIG -B -f $HOSTAPD_LOG 
    fi
    # Note if hostapd is already started, and changes to the interface are made,
    # the AP can dissapear. The process runs but no AP is there. 
    # For now we mainly call this script with restart to work around this. 

    if [ "1" == "$have_tunnel" ] ; then 

        echo 'Configuring IP tables to forward traffic from the access point to the VPN'
        sysctl -w net.ipv4.ip_forward=1
        iptables -P FORWARD ACCEPT
        iptables --table nat -A POSTROUTING -o $INET_DEVICE -j MASQUERADE

        # once the tunnel is up, change the DNS server
        cp /etc/resolv.conf $RESOLV_CONF_BAK
        echo "nameserver $AZURE_DNS_SERVER" >/etc/resolv.conf

        # Make resolv.conf RO to prevent dhcpd or network manager from updating it
        # e.g., if the lease on the uplink interface expires and dhcpd renews it
        chattr +i /etc/resolv.conf
    fi
}


#### main() ####

cd /home/$HOSTNAME/vpn/

if [ "$1" = "stop" ] ; then
    pqap_stop
    exit

elif [ "$1" = "start" ] ; then

    pqap_start

elif [ "$1" = "restart" ] ; then
    pqap_restart
    exit

else
    echo "Start up an access point that tunnels traffic over a VPN"
    echo "Usage:"
    echo "    $0 start|stop|restart"
fi




