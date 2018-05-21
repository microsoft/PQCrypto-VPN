#!/usr/bin/perl -wT

# Note: This script runs as root.  It's minimal, and takes no input by design.

if($> != 0 ) {  # if EUID is not 0 (root)
    print "You must run this script as root\n";
    die;
}


# Clobber all environment vars, which we don't trust.
foreach my $key (keys %{$ENV}) {
    $ENV{$key} = "";
}
$ENV{PATH} = ""; # be explicit here to satisfy -T

my $ret = system("/sbin/ifconfig wlan1 up");
if($ret != 0) {
    warn "ifconfig failed to bring up wlan1";
    exit($ret);
}
exec("/sbin/iwlist wlan1 scan");
