#!/usr/bin/perl

use strict;
use warnings;
use File::Copy;
use File::Path;
use Path::Tiny qw(path);


my $VPN_SERVER_IP = "0.0.0.0";          # IP address of the VPN server, to go in the device OpenVPN config file
my $SEED_FILE = "seed.b64";             # A seed we'll use for creating passwords, so that the same hostname always gets the same password
                                        # Created if not found

sub print_usage
{
    print "Script to copy the post-quantum VPN code to a Raspbian image, and to customize it for a specific user\n";
    print "$0 <image name> [hostname]\n";
    print "The script must run as root, and may be vulnerable to command injection -- so don't take filenames from just anywhere\n";
    print "If the hostname option is specified the image must have been prepared already, then booted and configured. \n";
    print "The hostname option will configure the image for a specfic user. \n";
    print "See the accompanying README for instructions. \n";
}

sub replace_in_file
{
    my ($filename, $oldstring, $newstring, $escape) = @_; 
 
    my $file = path($filename);
    if(!$file) {
        cleanup("Failed to open file $filename for search/replace\n");
    }
    my $data = $file->slurp_utf8;
    my $new_data = $data;
    if(defined($escape) and $escape == 1) {
        # Treat oldstring as a literal, escape regex special chars like [], *, $, etc.
        $new_data =~ s/\Q$oldstring/$newstring/mg;
    }
    else {
        $new_data =~ s/$oldstring/$newstring/mg;
    }

    $file->spew_utf8( $new_data );

    if($data eq $new_data) {
        warn "replace_in_file did not replace anything:\nfile: $filename\noldstring: $oldstring\nnewstring: $newstring\n";
    }
}


sub derive_password
{
    my ($password_length, $context) = @_;

    if(! -e $SEED_FILE) {
        print "Creating seed file $SEED_FILE\n";
        system("head -c 128 /dev/urandom | openssl base64 > $SEED_FILE");
    }

    return `echo "$context" | openssl sha256 -hmac $SEED_FILE| cut -b 10- | sed 's/[iIoO0lL/+]//g'|head -c $password_length`;
}

sub generate_password
{
    my $password_length = shift;

    return `head -c 64 /dev/urandom |openssl base64|sed 's/[iIoO0lL\/\+]//g'|head -c $password_length`;
}

sub get_password_hash
{
    my ($username, $shadow_file) = @_;

    open(my $fh, "<", $shadow_file) || die "Failed to open shadow file; $!\n";
    while(my $line = <$fh>) {
        if($line =~ m/$username:(.*?):.*/) {
            close($fh);
            return $1;
        }
    }

    close($fh);
    cleanup("Failed to get password hash for user '$username' from file '$shadow_file'\n");
    return "";

}

##########
#  main()
##########

my $hostname = undef;

if(!defined($ARGV[0])) {
    print "Provide an image name. \n\n";
    print_usage();
    die;
}
if(! -e $ARGV[0]) {
    print "Image '$ARGV[0]' not found. \n\n";
    print_usage();
    die;
}


my $img_name = $ARGV[0];

if(defined($ARGV[1])) {
    $hostname = $ARGV[1];

}

if($> != 0 ) {  # if EUID is not 0 (root)
    print "You must run this script as root\n";
    die;
}

if(defined($hostname)) {
    print("Creating a copy of $img_name ... ");
    system("cp $img_name $hostname.img") == 0 || cleanup("Failed to create a copy of the image file\n");
    print ("done\n");
    $img_name = "$hostname.img";
}


#First we mount the two partitions

my $fdisk_output = `fdisk -l $img_name`;

my $sector_size;
if($fdisk_output =~ m%Sector size \(logical/physical\): (\d+) bytes%s) {
    $sector_size = $1;
}
else {
    die "unexpected fdisk output 1: \n\n $fdisk_output";
}

my $offset;
if($fdisk_output =~ m%$img_name.* (\d+)\s+\d+\s+\d+ .* 83 Linux%s) {
    $offset = $1*$sector_size;
}
else {
    die "unexpected fdisk output 2\n\n $fdisk_output";
}

print "Image has $sector_size byte sectors\n";
print "Offset of Linux partition is $offset\n";

my $mount_point = "/tmp/raspian-image-edit-script-" . rand(1000000);
mkdir($mount_point) || die "Failed to make a temporary mount point $mount_point; $!";
print "Created temporary mount point $mount_point\n";

system("mount -o loop,offset=$offset $img_name $mount_point") == 0 || die "failed to mount image to $mount_point; $!";
print "Mounted image to $mount_point\n";

my $boot_offset;
if($fdisk_output =~ m%.* (\d+)\s+\d+\s+\d+ .* W95 FAT32.*%s) {
    $boot_offset = $1*$sector_size;
}
else {
    cleanup("unexpected fdisk output 3:\n\n$fdisk_output");
}
print "Offset of boot partition is $offset\n";

my $boot_mount_point = $mount_point . "-boot-partition";
mkdir($boot_mount_point) || die "Failed to make a temporary mount point $mount_point; $!";
print "Created temporary mount point $mount_point\n";

system("mount -o loop,offset=$boot_offset $img_name $boot_mount_point") == 0 || die "failed to mount boot image to $boot_mount_point; $!";


if(!defined($hostname)) {     # 1st step, Prepare the image

    # Enable ssh on first boot by writing an empty file 'ssh' to the boot partition
    open(my $ssh_file, ">", "$boot_mount_point/ssh") || cleanup("Failed to create ssh file on boot partition\n");
    close($ssh_file);

    #Change the hostname too -- the mdns name "raspberrypi.local" is often already in use
    replace_in_file("$mount_point/etc/hostname", "raspberrypi", "pqap-default");
    replace_in_file("$mount_point/etc/hosts", "raspberrypi", "pqap-default");

    print "Image prepared successfully\n\n";
}
else {      # 2nd step, Install pqap package and customize the image

    # We have a hostname and the image is pre-configured, customize the image to a user
    print("Customizing the image $img_name to $hostname\n");

    # Copy our openssl package to opt/openssl
    if(! -e "$mount_point/opt") {
        mkdir("$mount_point/opt") || die "Failed to create /opt; $!";
    }
    
    my $openssl_path = "$mount_point/opt/openssl";
    if(! -e $openssl_path) {
        mkdir($openssl_path) || die "Faild to create $openssl_path ; $!";
    }
    system("cp -r package/oqs-openssl/openssl/* $openssl_path") == 0 || cleanup("Failed copy openssl to $openssl_path");

    system("ldconfig -r $mount_point /opt/openssl/lib/") == 0 || cleanup("ldconfig failed");

    # Copy the pqap package
    my $pqap_path = "$mount_point/home/pi/vpn";
    mkdir($pqap_path) || die "failed to make $pqap_path; $!";

    my @package_files = qw( 
        creds/ca.crt
        openvpn
        pqap.sh
        client.ovpn
        hostapd.conf
        dnsmasq.conf
        hosts.conf
        vpn_auth.txt
        do_wlan1.pl
        do_scan.pl
    );

    my @package_dirs = qw(
        log
        interfaces
    );

    foreach my $file (@package_files) {
        copy("package/$file", "$pqap_path/") || cleanup("Failed to copy file $file");
    }   

    foreach my $dir (@package_dirs) {
        system("cp -r package/$dir $pqap_path/") == 0 || cleanup("Failed to copy directory $dir");
    }   

    # Set execute permission on openvpn and the access point script
    system("chmod 0775 $pqap_path/openvpn") == 0 || warn "Failed to set permissions on $pqap_path/openvpn";
    system("chmod 0744 $pqap_path/pqap.sh") == 0 || warn "Failed to set permissions on $pqap_path/pqap.sh";
    system("chmod 0744 $pqap_path/do_wlan1.pl") == 0 || warn "Failed to set permissions on $pqap_path/do_wlan1.pl";
    system("chmod 0744 $pqap_path/do_scan.pl") == 0 || warn "Failed to set permissions on $pqap_path/do_scan.pl";
    system("chmod 0600 $pqap_path/vpn_auth.txt") == 0 || warn "Failed to set permissions on $pqap_path/vpn_auth.txt";

    # ACL the interfaces directory
    system("chmod 0777 $pqap_path/interfaces") == 0 || warn "Failed to set permissions on $pqap_path/interfaces";

    # Setup the sudoers file
    copy("package/pqap-sudoers", "$mount_point/etc/sudoers.d/pqap-sudoers") || cleanup("Failed to copy paqap-sudoers");

    # Update the timeout in dhclient so that DHCP attempts fail faster. It
    # defaults to 60-300 seconds, and we block waiting for it. Change to 10 seconds. 
    replace_in_file("$mount_point/etc/dhcp/dhclient.conf", '#timeout \d+;', "timeout 10;");

    #Change the hostname from pqap-default to the new value
    replace_in_file("$mount_point/etc/hostname", "pqap-default", $hostname);
    replace_in_file("$mount_point/etc/hosts", "pqap-default", $hostname);
    
    # Customize hostapd.conf
    my $wpa_psk = derive_password(10, "$hostname-wpa-psk");
    replace_in_file("$mount_point/home/pi/vpn/hostapd.conf", "%%SSID%%", $hostname);
    replace_in_file("$mount_point/home/pi/vpn/hostapd.conf", "%%WPA_PSK%%", $wpa_psk);

    # Customize the openvpn client config
    replace_in_file("$mount_point/home/pi/vpn/client.ovpn", "%%VPN_SERVER_IP%%", $VPN_SERVER_IP);
    replace_in_file("$mount_point/home/pi/vpn/client.ovpn", "%%HOSTNAME%%", $hostname);

    # Set the OpenVPN username and password
    my $vpn_password = derive_password(16, "$hostname-vpn-password");
    replace_in_file("$mount_point/home/pi/vpn/vpn_auth.txt", "%%VPN_USERNAME%%", $hostname);
    replace_in_file("$mount_point/home/pi/vpn/vpn_auth.txt", "%%VPN_PASSWORD%%", $vpn_password);

    # Set a new device password
    my $device_password = generate_password(10);
    my $password_hash = `mkpasswd --method=sha-512 $device_password`;
    chomp($password_hash);
    my $old_hash = get_password_hash("pi", "$mount_point/etc/shadow");
    replace_in_file("$mount_point/etc/shadow", $old_hash, $password_hash, 1);   # The last argument will ensure we escape the special chars in $old_hash

    # Change the username
    replace_in_file("$mount_point/etc/passwd", "^pi:", "$hostname:");
    replace_in_file("$mount_point/etc/passwd", "/home/pi:", "/home/$hostname:");
    replace_in_file("$mount_point/etc/shadow", "^pi:", "$hostname:");
    replace_in_file("$mount_point/etc/group", "^pi:", "$hostname:");
    replace_in_file("$mount_point/etc/group", ':pi$', ":$hostname");
    system("mv $mount_point/home/pi $mount_point/home/$hostname");
    replace_in_file("$mount_point/etc/sudoers.d/pqap-sudoers", "pqap-default", "$hostname");

    # Set /etc/rc.local to run our script on boot
    replace_in_file("$mount_point/etc/rc.local", "^exit 0", "cd /home/`hostname`/vpn/ \nbash pqap.sh restart\n\nexit 0");
    system("chmod 0755 $mount_point/etc/rc.local") == 0 || warn "Failed to set permissions on rc.local";

    # Copy webserver config, create paths and copy UI code
    my @ui_files = qw(
        index.cgi
        configure.html.tt
        configure_result.html.tt
        connectivity_test.html.tt
        connect_result.html.tt
        dashboard.html.tt
        index.html.tt
        style.css
    );

    copy("package/lighttpd.conf", "$mount_point/etc/lighttpd/lighttpd.conf") || cleanup("Failed to copy lighttpd.conf");
    rmtree("$mount_point/var/www/html") || warn "Failed to remove /var/www/html from image";
    rmtree("$mount_point/var/www/cgi-bin")  || warn "Failed to remove /var/www/cgi-bin from image";
    foreach my $file (@ui_files) {
        copy("package/$file", "$mount_point/var/www/") || cleanup("Failed to copy file $file");
    }   

    # Log everything 
    my $config = 
    "-------------------------------\n" . 
    "Image Configuration Information\n" .
    "Device username: $hostname\n" .
    "Device password: $device_password\n" .
    "Device mDNS name: $hostname.local\n" .
    "VPN server IP: $VPN_SERVER_IP\n" .
    "VPN username: $hostname\n" .
    "VPN password: $vpn_password\n" .
    "WiFi SSID: $hostname\n" .
    "WPA2 PSK: $wpa_psk\n" .
    "-------------------------------\n\n";

    print $config;

    my $FH;
    if(open($FH, ">", "$hostname.config")) {
        print $FH $config;
        close($FH);
        print "Config written to $hostname.config\n";
    }
    else {
        warn "Failed to open config file; $!"; 
    }

    print "Image customized successfully\n\n";
}


# End
print "To mount it and check it out, run the command:\n";
print "    sudo mount -o loop,offset=$offset $img_name /media/raspbian-image\n";
print "(the last path is an example, make sure it exists on your system)\n";
print "To mount the boot partition, use:\n";
print "    sudo mount -o loop,offset=$boot_offset $img_name /media/raspbian-boot\n";
print "To copy the image to /dev/sdb you can use: \n";
print "   sudo dd if=$img_name of=/dev/sdb bs=256K status=progress\n";

cleanup();


# Note this function references globals defined above
sub cleanup
{
    if(defined($_[0])) {
        print $_[0] . "\n";
    }
    system("umount $mount_point") == 0 || warn "Failed to unmount $mount_point; $!";
    rmdir($mount_point) || warn "Can't remove temporary directory $mount_point, was it unmounted successfully?";

    if(defined($boot_mount_point)) {
        system("umount $boot_mount_point") == 0 || warn "Failed to unmount $boot_mount_point; $!";
        rmdir($boot_mount_point) || warn "Can't remove temporary directory $boot_mount_point, was it unmounted successfully?";
    }

    exit;
}



