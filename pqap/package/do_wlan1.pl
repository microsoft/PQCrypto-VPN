#!/usr/bin/perl -wT

use strict;
use warnings; 

# Script to bring up the interface wlan1 from a file
# Note this script runs as root, and should be minimal

# Clobber all environment vars, which we don't trust.
foreach my $key (keys %{$ENV}) {
    $ENV{$key} = "";
}
$ENV{PATH} = ""; # be explicit here to satisfy -T

if(!defined($ARGV[0])) {
    exit(-1);
}

my $interface_file;
if($ARGV[0] =~ /^([-0-9a-zA-Z.\/_]+\.interface)$/) {
    $interface_file = $1;
}
else {
    warn "Invalid filename\n";
    exit(-2);
}

#Try to bring the interface down, in case it's up.
# We don't care if this fails
system("/sbin/ifdown -i $interface_file wlan1");
system("/sbin/ifconfig wlan1 down");

# Make sure wpa_supplicant is not already running, and there is not an orphaned
# run file from a previous run.
system("/usr/bin/killall wpa_supplicant");
system("/bin/rm /var/run/wpa_supplicant/wlan1");


# Then bring the interface up
my $ret = system("/sbin/ifconfig wlan1 up");
if($ret != 0) {
    warn "ifconfig wlan1 up failed; $!\n";
    exit($ret);
}

$ret = system ("/sbin/ifup -i $interface_file wlan1");
if($ret != 0) {
    warn "ifup failed; $!\n";
    exit($ret);
}

exit(0);
