A VPN Device with Post-Quantum Security
---------------------------------------

Please visit our project page at: https://www.microsoft.com/en-us/research/project/post-quantum-crypto-vpn/

**These instructions have not been tested nor updated to work with PQCrypto-VPN 1.3. Contributions welcomed!**

Device Hardware
----------------
We tested with a Raspberry Pi 3 Model B (purchased in summer 2017). When the
device connection to the internet uses wireless, two wireless adapters are
required.  We tested using an Edimax N 150 USB Adapter, model number EW-7811Un.
No special configuration or drivers were required for this adapter.


Building per-device images
--------------------------
We'll need to create a custom SD card image for each VPN  device, from a
Linux PC with a SD card slot or a USB SD card adapter.  There are two steps. 

1. (Prepare Image) First we take a stock Raspbian image and make some changes
to it that are common for all users, and do not depend on the PQCrypto-VPN software.
Then copy it to an SD card, boot the image on a Pi, and install some packages,
and make some configuration changes.  Then we copy
the image back to the PC. The image will then be customized for each user
and with the PQCrypto-VPN software.
This first step is more work and slower, but it only needs to happen once per
Raspbian release.  Since most of the PQCrypto-dependent changes to the image are
made in the second step, we shouldn't have to repeat this step during PQCrypto-VPN 
development (unless, e.g., a new package is needed). 

2. (Customize Image) Customizing an image for each user/device is done entirely
by a script.  In this step the PQCrypto-VPN package is installed, along with the UI,
OQS-OpenSSL, permissions are set and other config changes are made. The image
is then copied to an SD card, and put in a Raspberry Pi.  As a final step we
have to add the user password to the VPN server.

These instructions were tested with 8GB micro SD cards.  The space requirements
are probably less than 100MB, above the size of Raspbian, which is about 2GB.


Software Package
----------------
The directory `package` contains OpenVPN and OpenSSL binarires built for the Raspberry
Pi, and configuration files to control how the device connects to the OpenVPN server.  
You must make some configuration changes, depending on how your VPN server is configured. 

1. In create_image.pl, change the line:
``
    my $VPN_SERVER_IP = "0.0.0.0";
``
to the IP address of your VPN server.

2. Review and make changes to the OpenVPN client configuration file, as needed.
E.g., ensure that the client and server both use (or don't use) compression.
This config file is `package/client.ovpn`.

3. This demo assumes the server will authenticate itself to the client with a 
certificate issued by a root certificate.  The root certificate should 
be placed in the package as `package/creds/ca.crt`.  The certificate must
be PEM encoded. 

4. In the file pqap.sh, there is a variable 
``
AZURE_DNS_SERVER="168.63.129.16"
``
The device will manually set the DNS server to this value (by changing
/etc/resolv.conf), so that all DNS queries are sent here.  This setting should
work for OpenVPN servers hosted in Azure (tested in the West US 2 data center).
For servers hosted elsewhere, the Azure DNS server will not work, we recommend
setting this value to the primary nameserver that the VPN server uses. 


Building PQ-VPN on Raspberry Pi (Optional)
------------------------------------------
We built OpenVPN and the OQS fork of OpenSSL directly on the Raspberry Pi 3.
Check out the sources and run `openvpn/build/build.py`.  The dependencies
listed in `build.py` are required, and are available from Raspbian with apt.
Once the system is built (`pq-openvpn-linux.tgz`), the openvpn binary and
OQS-OpenSSL binaries must be copied to `pqap/package`.  These are then used by
`create_image.pl` when building a VPN device image.  Note that you don't need
the `gcc-mingw-w64` and `nsis` packages for the ARM build, since they are
required only to cross compile Windows binaries. The `build.py` script will
output an error when trying to build Windows binaries, but should build the
ARM/Linux binaries (`pq-openvpn-linux.tgz`) successfully.

Prepare Image
------------
This is done once per Raspbian release, we will customize the image with some stuff that 
is not specific to any VPN users (e.g., install packages).

1. Get the Raspbian lite image, from here: https://downloads.raspberrypi.org/raspbian_lite/images/
We tested with `2017-11-29-raspbian-stretch-lite.img` ,  and use this
filename in the instructions. 

2. Run:
``
    sudo ./create_image.pl 2017-11-29-raspbian-stretch-lite.img
``
This is going to modify the image in-place so you probably want to make a copy
first.  This step will copy the contents of pqap/package to the right
place on the Pi's filesystem.

3. Copy the image to a Pi 3's SD card, (/dev/sdb in this example)
``
    dd if=2017-11-29-raspbian-stretch-lite.img  of=/dev/sdb bs=256K status=progress
``
then boot the image, with the device connected to ethernet. 
Connect via ssh (or login locally, but the device needs internet connectivity), 
``
    ssh pi@pqap-default.local
``
The password is 'raspberry'.  This step might not work if your machine doesn't
support mDNS (to resolve the .local address). You can also attach a keyboard and monitor to the Pi.  

Run the following commands:
``
sudo apt update
sudo apt upgrade
sudo apt install hostapd dnsmasq liblzo2-2 lighttpd libcgi-pm-perl libtemplate-perl libpath-tiny-perl rng-tools
sudo update-rc.d ssh enable
sudo invoke-rc.d ssh start
sudo update-rc.d rng-tools enable
sudo dpkg-reconfigure tzdata
``
The command to enable SSH is really only required when preparing debug builds
-- since we don't need this to be enabled for normal use.  Another optional
step is run `raspi-config` and set the keyboard layout to US English.  It
defaults to something else, but we don't really use the keyboard on this device
unless we connect with ssh in. 

Then run `sudo shutdown now`.   

4. Now  dd the image back off the SD card. It will be as large as the card.
(e.g., it'll be 8G for an 8G SD card, but the actual data will only be about
2G).  Use a script to resize the image
``
    resize_image.pl `pwd`/2017-11-29-raspbian-stretch-lite.img
``
This will resize the image back to about 2GB (or whatever the size of the data
is, plus a few hundred megs). Smaller is better here when experimenting and
debugging, since copying images to SD cards is very slow. 

This image file will be the base image we customize for all users. 
Making it read-only is a good idea.


Customize Image
---------------

1.  Choose a hostname for the device/user.  This will be the name of the device, and
the SSID of the AP.  E.g., `pqalice`. 
Using the image from the previous step, e.g., `2017-11-29-raspbian-stretch-lite.img`, 
run the command
``
    sudo ./create_image 2017-11-29-raspbian-stretch-lite.img pqalice
``
It will create a copy of the prepred image `pqalice.img` and a log file with configuration
information `pqalice.config`.

2. This will customize the image with a unique device password, VPN account
password and WPA2 PSK, as output by the script.  The VPN account must be
entered on the server.

3. Write the image to the SD card with `dd` as described above. 


Using the Device
----------------
On boot, the script /home/pqalice/vpn/pqap.sh is run to start OpenVPN and
the access point.  This happens via the script /etc/rc.local which gets run
first thing after boot (run as root). 

The SSID should show appear a few minutes.  Initially, the SSID may be visible, 
but devices won't be able to connect to it.  It can take a minute or so for 
the SSID to become functional. 


Troubleshooting
---------------
- Logs are stored in /home/pqalice/vpn/log. the OpenVPN log is probably
  going to be the most useful.  Also /tmp/rc.local.log contains the output
  of /etc/rc.local, which starts the AP service on boot. 
- If you have a machine on the same network as the device's ethernet connection,
and if network is working properly, you can ssh to the device, e.g., 
``
  ssh  pqalice@pqalice.local 
``
authenticate with the device password output by the customization script for
this image. 
-  From a terminal on the device, you can run the command
``
    sudo /home/pqalice/vpn/pqap.sh restart
``
to restart the VPN and AP.

- When using `dd` watch for errors in the output, e.g., 
``
    dd: error reading '/dev/sdb': Input/output error
``
the rest of the output is similar, so it's easy to miss. 

- The commnad 
`` sudo losetup -f --show -P image.img ``
will create a device (e.g., /dev/loop0) from a Raspbian image


Notes on use of rng-tools, rngd
-------------------------------
The wireless AP software hostapd uses /dev/random for entropy, that it pools, and
uses for crypto operations to secure wifi.  After booting the Pi and starting things
up, the log may show errors like the following: 
``
random: Cannot read from /dev/random: Resource temporarily unavailable
random: Only 1/20 bytes of strong random data available from /dev/random
random: Not enough entropy pool available for secure operations
WPA: Not enough entropy in random pool to proceed - reject first 4-way handshake
``
After some connections have failed and the clients retry a few times, the
entropy in /dev/random will reach that required by hostapd and things work.
There have also been reports of this causing APs to become flaky over time.
This might make sense in embedded systems, but we know that /dev/urandom will
have sufficient entropy and would like to use it rather than /dev/random + the
hostapd pool.  Android does the same.  Unfortunately this is only available as
a build-time option, and we'd have to rebuild the Raspbian version of hostapd.
Rather than do this and have to maintain our own build of hostapd, we use
rng-tools as a workaround (and security should actually improve as well). The
Pi 3 has a hardware random number generator, and `rngd` from the the
`rng-tools` package enables it to provide entropy in the kernel entropy pool,
so that reads by dnsmasq to /dev/random don't fail when
`/proc/sys/kernel/random/entropy_avail` is low (since the available entropy
should never be low).  Since the hardware random number generator should
provide better entropy than the ad-hoc methods used by the kernel security
should improve as a result of using `rngd`. Documentation on the Broadcom RNG
design (or even the SoC more generally, Broadcom BCM2837) is not available. 


Limitations and Open Issues
---------------------------
Here we document some of the limitations of this prototype and missing features
that would improve it.  

- Add support for captive portals, hidden networks. 
- Add log rotation on the device, to prevent the disk from filling up with logs.
- Add access control on the AP user interface.  Currently it is accessible to
  anyone on the wireless network. 
- The current security model doesn't assume untrusted users on the device, and
  doesn't isolate parts of the system from one another.
- Make UI improvements to support troubleshooting (access to log files, system
  info)
- Create a service for the AP and VPN so that it is kept running automatically
  by the system.
- SSH host keys are the same on each device image created from the same
  prepared image.  Not currently a concern since sshd should only be enabled
  for debugging.  If SSHD will be enabled on all devices, device will have to
  configured to re-generate keys on first boot, or new keys could be injected
  by the second step of configure_image.pl.
- Add a way to shutdown cleanly to avoid filesystem corruption.  We could also
  investigate making some parts of the FS read-only, so that maybe we never
  need to shutdown cleanly. 
- Expand the filesystem  on first boot to fill the SD card so there is plenty
  of space to store logs.

