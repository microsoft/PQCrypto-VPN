#!/usr/bin/perl

# Web interface for configuring the the VPN device

# stdout from this script is sent to the browser and stderr goes to /var/log/lighttpd/breakage.log
# Details of the requests made by the brower can be found in /var/log/lighttpd/error.log
# if the line ' debug.log-request-handling = "enable" ' is present in /etc/lighttpd/lighttpd.conf

use strict;
use warnings;

use Template;
use CGI qw/ -utf8 escapeHTML/;
use Digest::SHA qw(sha256_hex);
use File::Copy;
use Path::Tiny qw(path);
use Sys::Hostname;


my $g_cgi = CGI->new;
 
# Get the page name from the query string 
my $p = $g_cgi->param( 'p' );
if(!defined($p)) {
    $p = "";
}

# Dispatch to the correct handler
if($p eq 'dashboard') {
    dashboard_page();
}
elsif($p eq 'example') {
    example_page();
}
elsif($p eq 'configure') {
    configure_page();
}
elsif($p eq 'configure_result') {
    configure_result_page();
}
elsif($p eq 'connect') {
    connect_result_page();
}
elsif($p eq 'connectivity') {
    connectivity_test_page();
}
else {
    warn "p not set or unrecognized, defaulting to index page";
    index_page();
}


########## Page handlers ###################

sub dashboard_page
{
    # Get info about device mac addresses
    my $macs_msg = "";
    my $macs_warn = "";
    my $macs = get_mac_addrs();
    foreach my $interface (keys %{$macs}) {
        $macs_msg .= "<tr><td>$interface</td><td>$macs->{$interface}</td></tr>\n";
    }

    if(!defined($macs->{"wlan1"})) {
        $macs_warn .= "Interface wlan1 not found, wireless uplink not supported.  Is the USB WiFi adapter connected?";
    }

    # Get info for Connectivity status
    my $have_network = 0;
    my $connectivity_msg = "";  
    if(test_interface_ping_ip("eth0")) {
        $connectivity_msg .= "Wired internet connectivity found (eth0).</br>";
        $have_network = 1;
    }
    else {
        $connectivity_msg .= "No wired Internet connectivity found (eth0).</br>";
    }

    if(test_interface_ping_ip("wlan1")) {
        $connectivity_msg .= "Wireless internet connectivity found (wlan1).</br>";
        $have_network = 1;
    }
    else {
        $connectivity_msg .= "No wireless Internet connectivity found (wlan1).</br>";
    }


    my $server_ip = get_openvpn_server_ip();
    if(!defined($server_ip) || $server_ip eq "") {
        $connectivity_msg .= "Failed to get server IP, can't check for connectivity</br>";
        $server_ip = "";
    }

    # Get info about Known WiFi Networks
    my ($available, $unavailable) = read_cached_interfaces();

    my $known_available = "";
    foreach my $network (@{$available}) {
        $network = escapeHTML($network);
        my $connect_button = qq(<form action="/" method="post"><input type="hidden" name="ssid" value="$network"><input type="hidden" name="p" value="connect"><input type="submit" value="Connect"></form> );
        my $forget_button = qq(<form action="/" method="post"><input type="hidden" name="ssid" value="$network"><input type="hidden" name="p" value="forget"><input type="submit" value="Forget"></form> );
        $known_available .= qq(<tr><td>$network</td><td>$connect_button</td> <td>$forget_button</td> </tr>);
    }

    my $known_unavailable = "";
    foreach my $network (@{$unavailable}) {
        $network = escapeHTML($network);
        my $connect_button = qq(<form action="/" method="post"><button type="button" disabled>Connect</button></form> );
        my $forget_button = qq(<form action="/" method="post"><input type="hidden" name="ssid" value="$network"><input type="hidden" name="p" value="forget"><input type="submit" value="Forget"></form> );
        $known_unavailable .= qq(<tr><td>$network</td><td>$connect_button</td> <td>$forget_button</td> </tr>);
    }

    # Get info for Nearby WiFi Networks
    my $ssids_msg = "";
    my @ssids = get_list_of_ssids();

    foreach my $ssid (@ssids) {
        if($ssid ne hostname()) {
            $ssids_msg .= format_ssid_row($ssid);
        }
    }
    if($ssids_msg eq "") {
        $ssids_msg .= "No wireless networks founds\n";
    }

    my $vars = {
                "macs" => $macs_msg,
                "macs_warn" => $macs_warn,
                "connectivity" => $connectivity_msg, 
                "ssids_rows" => $ssids_msg,
                "known_available" => $known_available,
                "known_unavailable" => $known_unavailable
               };

    output_page_helper("dashboard.html.tt", $vars);
}

sub connect_result_page
{
    my $message = "";
    my $ssid = $g_cgi->param('ssid');
    if(!defined($ssid) || $ssid eq "") {
        $ssid = "";
        warn "Failed to connect; missing ssid";
        $message .= "Failed to connect; missing ssid</br>";
        goto error;
    }

    my $interface_file = find_cache_file($ssid);

    if($interface_file eq "") {
        $message .= "Failed to connect; can't find cached network info</br>";
        goto error;
    }


    $message = 'Going to restart the access point and enable the VPN tunnel.</br>
    Your device may be disconnected momentarily before Internet connectivity is available. </br>
    Some devies may automatically connect to another network</br>
    <a href="config.local">Return to the control panel.</a> </br>';

    my $vars = {
                "ssid" => $ssid,
                "message" => $message 
            };

    output_page_helper("connect_result.html.tt", $vars);

    # Wait for the data to reach the browser before kiling the network
    sleep(2); 

    # This step restarts the AP and will kill this connection to the device, so that's
    # why we output a message before doing this. 
    # This shuts down the AP too, can this be avoided?  
    warn "DEBUG: Calling pqap.sh stop";
    my $homedir = get_homedir();
    my $ret = system("sudo $homedir/vpn/pqap.sh stop");  
    if($ret != 0) {
        warn "Failed while trying to stop pqap";
    }
    
    # If bringing up wlan1 fails; we still continue executing to the 'pqap.sh restart'
    # command so that the web UI comes back up. 
    warn "DEBUG: calling do_wlan1.pl";
    $ret = system("sudo $homedir/vpn/do_wlan1.pl $interface_file");
    if($ret != 0) {
        warn "Failed to connect to network specified by interface file: $interface_file";
        return;
    }

    if(!test_interface_ping_ip('wlan1') ) {
        warn "Connection failed; can't ping IPs";
    }
    else{
        if(!test_interface_ping_name('wlan1') ) {
            warn "Connection failed (name resolution failure)</br>";
        }
    }

    warn "DEBUG: calling pqap restart";
    $ret = system("sudo $homedir/vpn/pqap.sh restart");  
    if($ret != 0) {
        warn "Tried to start VPN tunnel but failed</br>";
    }

    return;

error:
    my $vars_error = {
                "ssid" => $ssid,
                "message" => $message 
            };

    output_page_helper("connect_result.html.tt", $vars_error);

}

sub configure_page
{
    my $ssid = $g_cgi->param('ssid');
    if(!defined($ssid) || $ssid eq "") {
        # This is OK -- ssid will be missing when configuring a hidden network. 
        $ssid = "";
    }
    
    $ssid = escapeHTML($ssid);

    my $security = $g_cgi->param('security');
    if(!defined($security) || 
        $security eq "" || 
        ($security ne '0' and $security ne '1')) {
        warn "Missing/invalid security parameter";
        $security = "";
    }

    my $ssid_details = get_ssid_details($ssid);

    my $vars = {
                "ssid" => $ssid,
                "ssid_details" => $ssid_details
            };

    if($security eq '1') {
        $vars->{"security"} = $security;
    }

    output_page_helper("configure.html.tt", $vars);
}

sub configure_result_page
{
    my $message = "";
    my $ssid = $g_cgi->param('ssid');
    if(!defined($ssid) || $ssid eq "" || !valid_ssid($ssid)) {
        $message .= "Missing or invalid ssid parameter";
        $ssid = "";
        goto output;
    }

    my $psk;
    my $security;
    $security = $g_cgi->param('security');

    if(defined($security) and $security eq "1") {
        $security = "wpa";
        $psk = $g_cgi->param('psk');
        if(!defined($psk) || !valid_psk($psk)) {
            $psk = "";
            $message .= "Failed to configure network; missing or invalid PSK for secure network";
            goto output;
        }
    }
    else {
        $security = "open";
    }

    my $ret = create_interface_file($security, $ssid, $psk);
    if($ret != 0) {
        $message .= "Failed to configure network; failed to store configuration";
        warn "Failed to create interface file\n";
    }
    else {
        $message .= "Interface configured successfully. You can connect to it from the dashboard.";
    }

output:    
    $ssid = escapeHTML($ssid);

    my $vars = {
                "ssid" => $ssid,
                "message" => $message
               };

    output_page_helper("configure_result.html.tt", $vars);

}

sub index_page
{
    my $vars = {};

    output_page_helper("index.html.tt", $vars);
}

# Helper to output the page
# Parameters
#     template_name:  The name of the template file (e.g., index.html.tt)
#     vars:  A hash containing the keys and values of stuff that gets
#            replaced in the template
sub output_page_helper 
{
    my ($template_name, $vars) = @_;

    # Force stdout to flush after every write 
    $| = 1; 

    my $tt  = Template->new({
        INCLUDE_PATH => "/var/www",
    });
     
    # we're using TT but we *still* need to print the Content-Type header
    # we can't put that in the template because we need it to be reusable
    # by the various other frameworks
    my $out = $g_cgi->header(
        -type    => 'text/html',
        -charset => 'utf-8',
    );
     
    # Use Template to replace [% foo %] in the template with variables 
    # TT will append the output to the passed referenced SCALAR
    $tt->process(
        $template_name,
        $vars,
        \$out,
    ) or die $tt->error; # This will cause an error 500
     
    print $out;
}

sub connectivity_test_page
{
    # Get info for Connectivity status
    my $have_network = 0;
    my $connectivity_msg = "";  
    if(test_interface_ping_ip("eth0")) {
        $connectivity_msg .= "Wired internet connectivity found (eth0).</br>";
        $have_network = 1;
    }
    else {
        $connectivity_msg .= "No wired Internet connectivity found (eth0).</br>";
    }

    if(test_interface_ping_ip("wlan1")) {
        $connectivity_msg .= "Wireless internet connectivity found (wlan1).</br>";
        $have_network = 1;
    }
    else {
        $connectivity_msg .= "No wireless Internet connectivity found (wlan1).</br>";
    }

    my $server_ip = get_openvpn_server_ip();
    if(!defined($server_ip) || $server_ip eq "") {
        $connectivity_msg .= "Failed to get server IP, can't check for connectivity</br>";
        $server_ip = "";
    }

    if($have_network and $server_ip ne "") {
        if(check_connectivity($server_ip)) {
            $connectivity_msg .= "OpenVPN server found at $server_ip</br>";
            if(test_interface_ping_ip("tun0")) {
                $connectivity_msg .= "Interface tun0 is up and ping succeeds</br>";
                if(test_interface_ping_name("tun0")) {
                    $connectivity_msg .= "Name resolution on tun0 succeeds</br>";
                }
                else {
                    $connectivity_msg .= "Name resolution on tun0 fails</br>";
                }
            }
            else {
                $connectivity_msg .= "Interface tun0 is not up or ping fails</br>";
            }
        }
        else {
            $connectivity_msg .= "OpenVPN server not found at $server_ip</br>";
        }
    }

    my $vars = {
                "message" => $connectivity_msg
               };

    output_page_helper("connectivity_test.html.tt", $vars);
   

}

############ VPN/System functions ################

sub get_homedir
{
    my $hostname = hostname();
    chomp($hostname);
    return "/home/$hostname";
}

sub get_openvpn_server_ip
{
    my $homedir = get_homedir();
    my $config = "$homedir/vpn/client.ovpn";

    my $fh;
    my $ret = open($fh, "<", "$config");
    if(!$ret) {
        warn "Failed to open $config; $!";
    }
   
    my $ip = "0.0.0.0";
    while( my $line = <$fh>) {

        if($line =~ /^\s*#/) { #skip lines that start with '#'
            next;
        }
        if($line =~ /remote (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) .*/) {
            $ip = $1;
            last;
        }
    }
    close($fh);

    return $ip;
}

# Returns 1 if an openvpn server is running at the given IP (on port 1194)
# parameters:
#     openvpn_server_ip  The ip of the server
sub check_connectivity 
{
    my ($openvpn_server_ip) = @_;

    # Use netcat to send a hello packet to the server and check for a
    # response
    my $openvpn_hello = '"\x38\x01\x00\x00\x00\x00\x00\x00\x00"';
    my $reply = `echo -e $openvpn_hello | timeout 10 nc -u $openvpn_server_ip 1194 | od -X -N 14 `;

    if(length($reply) > 5) {
        return 1;
    }
    return 0;
}

# Scan for wireless APs with wlan1
sub get_list_of_ssids
{
    my ($hidden_ssid) = @_;

    my $scan_output;


    if(defined($hidden_ssid)) {
        warn "Hidden SSIDs not supported";
    }

    # Triggering scanning is a privileged operation (root only) and normal users can
    # only read left-over scan results.  So to get fresh results we call the do_scan.pl
    # script that does the scan for us. 
    my $homedir = get_homedir();
    $scan_output = `sudo $homedir/vpn/do_scan.pl`; 

    if($? != 0) {
        warn "do_scan.pl failed with error code $?";
        return ();
    }

    if($scan_output =~ /No such device/) {
        warn "wlan1 is not present; probably USB wifi is not present";
    }

    my @aps = split(/Cell \d\d - /m, $scan_output);

    # The first element is the output of iwlist before the APs
    # so we return starting from 1
    @aps = splice(@aps, 1); 

    # Sort them by SSID
    @aps = sort { parse_ssid($a) cmp parse_ssid($b) } @aps;

    return @aps;
}

sub parse_ssid
{
    my ($iwlist_output) = @_;

    if($iwlist_output =~  /ESSID:"(.*)"\n/m) {
        return $1;
    }
    return "";

}

sub format_ssid_row
{
    my ($scan_output) = @_;

    my $ssid = "<i>ssid</i>";
    if($scan_output =~ /ESSID:"(.*)"\n/m) { 
        $ssid = escapeHTML($1);
    }
    
    my $security = "<i>encryption</i>";
    my $security_bool = 0;
    if($scan_output =~ /Encryption key:(.*)\n/m) { 
        if($1 eq 'on') {
            $security = 'encrypted';
            $security_bool = 1;
            if($scan_output =~ /WPA2/m) {
                $security .= " (WPA2)"
            }
            elsif($scan_output =~ /WPA/m) {
                $security .= " (WPA)"
            }
            elsif($scan_output =~ /WEP/m) {
                $security .= " (WEP)"
            }
        }
        elsif($1 eq 'off') {
            $security = 'not encrypted';
        }
    }

    my $strength = "<i>?</i>";
    if($scan_output =~ /(Quality=.*)\n/m) { 
        $strength = $1;
    }

    # Add a link to the configure page
    my $hostname = hostname();
    if($ssid ne $hostname) {
        $ssid = qq(<a href="/?p=configure&ssid=$ssid&security=$security_bool">$ssid</a>);
    }
    
    return qq(<tr><td>$ssid</td> <td>$security</td> <td align="center">&nbsp;&nbsp;&nbsp;$strength</td></tr>\n);
}

# Returns the full network details of the specified SSID
# If the network is not up at the time, it returns the empty string
sub get_ssid_details
{
    my ($ssid) = @_;

    my @ssids = get_list_of_ssids($ssid);

    foreach my $ssid_details (@ssids) {
        if($ssid_details =~ /ESSID:"(.*)"\n/m) { 
            if($1 eq $ssid) {
                return $ssid_details;
            }
        }
    }
    return "";
}

# Return 1 if the provide interface is up, and we can ping over it. 
sub test_interface_ping_ip
{
    my ($interface) = @_; 

    # Ping Google's primary DNS server, 
    return ping_helper($interface, "8.8.8.8");
}

sub test_interface_ping_name
{
    my ($interface) = @_; 

    # Ping MSFT's Network Connectivity Status Indicator site. 
    # https://technet.microsoft.com/en-us/library/ee126135
    return ping_helper($interface, "www.msftncsi.com");
}

sub ping_helper
{
    my ($interface, $addr) = @_;

    # Ping with one packet and a one second timeout
    # The timeout is set to only one second because the UI blocks on this. 

    my $timeout = 1;
    my $packet_count = 1;
    my $ping_res = `/bin/ping -I $interface -w $timeout -c $packet_count $addr`;
    if($? != 0) {
        warn "Ping command failed; returned $?\n";
        return 0;
    }

    if($ping_res =~ / 0% packet loss/m) {
        return 1;
    }
    else {
        return 0;
    }
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


# Validating SSID and PSK
# We allow any printable characters.  The strings are quoted in the interface
# file, but only the quotes at the beginning and ending are special (and we
# always add these).
# See https://unix.stackexchange.com/questions/102530/escape-characters-in-etc-network-interfaces
sub valid_ssid 
{
    my $ssid = shift;

    if($ssid !~ /^[[:print:]]+$/) {
        warn "Invalid SSID, contains nonprintable characters";
        return 0;
    }
    else {
        return 1;
    }


}
sub valid_psk
{
    my $psk = shift;

    if($psk !~ /^[[:print:]]+$/) {
        warn "Invalid PSK, contains nonprintable characters";
        return 0;
    }
    else {
        return 1;
    }
}

# Find the directory containting cached interfaces
# If none is found, "0" is returned.
sub get_interface_cache_path
{
    my $homedir = get_homedir();

    my $full_path = "$homedir/vpn/interfaces/";
    if(-d $full_path) {
        if(! -R $full_path || !-W $full_path) {
            warn "Found path for interfaces cache, but can't read or write to it";
            return "0";
        }
        return $full_path;
    }

    return "0";
}


# Create a file describing a wireless interface for use with ifup
# Parameters
#     type  The network security type ("open", or "wpa" for WPA/WPA2)
#     ssid  The network SSID
#     psk   (optional) The pre-shared key for the network, if required by the type
#
# returns: 0 on success, nonzero on error
sub create_interface_file
{
    my ($type, $ssid, $psk) = @_;

    if(!valid_ssid($ssid)) {
        warn "Invalid ssid '$ssid'";
        return -1;
    }

    if($type eq 'wpa' and !valid_psk($psk)) {
        warn "PSK not valid, contains invalid characters";
        return -1;
    }

    my $cache_path = get_interface_cache_path();

    my $template_file;
    if($type eq 'open') {
        $template_file = "$cache_path/open_template.interface";
    }
    elsif ($type eq 'wpa') {
        $template_file = "$cache_path/wpa_template.interface";
    }

    # For the interface file name, we hash the SSID to get a hex string
    # since SSIDs can contain characters that we don't want in filenames
    my $ssid_hash = hash_ssid($ssid);
    my $interface_file = "$cache_path/$ssid_hash.interface";
    if(-e $interface_file) {
        warn "Interface file $interface_file exists already, going to replace it.";
    }

    my $ret = copy($template_file, $interface_file); 
    if(!$ret) {
        warn "Failed to create new interface file $!"; 
        return -1;
    }    

    replace_in_file($interface_file, '%%SSID%%', $ssid);
    if($type eq 'wpa') {
        replace_in_file($interface_file, '%%PSK%%', $psk);
    }

    return 0;
}

sub read_cached_interfaces
{
    my $cache_path = get_interface_cache_path();

    my $dh;
    my $ret = opendir($dh, $cache_path);
    if(!$ret) {
        warn "Failed to open interface cache path; $!\n";
        return "";
    }

    my @available = ();
    my @not_available = (); 

    while(my $interface_file = readdir($dh)) {

        # Skip the template files and '.', and '..' by only reading files with
        # long names 
        if(length($interface_file) < 74) {
            next;
        }

        my $fh;
        my $full_path = $cache_path . $interface_file;
        my $ret = open($fh, "<", $full_path);
        if(!$ret) {
            warn "Failed to open interface file '$full_path'; $!\n";
            next;
        }
        my $config = join('', <$fh>);
        close($fh);


        my $ssid = "";
        if(($config =~ /^\s*wireless-essid "(.*)"$/m) ||
           ($config =~ /^\s*wpa-ssid "(.*)"$/m)) {
            $ssid = $1;
            if(is_ssid_available($ssid)) {
                push(@available, $ssid);
            }
            else {
                push(@not_available, $ssid);
            }
        }
    }

    return (\@available, \@not_available);
}

# For a given SSID find the interface file in the cache, 
# as created by create_interface_file. 
# Paramters:
#   ssid The name of the ssid we're looking for
# Returns: 
#   The interface file name, if found, or "" if not
sub find_cache_file
{
    my ($ssid) = @_;

    my $cache_path = get_interface_cache_path();

    my $ssid_hash = hash_ssid($ssid);
    my $interface_file = $cache_path . "$ssid_hash.interface";

    if(-e $interface_file) {
        return $interface_file;
    }

    return "";
}

sub is_ssid_available
{
    my ($ssid) = @_;

    if(get_ssid_details($ssid) eq "") {
        return 0;
    }
    return 1;
}

sub hash_ssid
{
    my ($ssid) = @_;

    return sha256_hex($ssid);
}

# Returns a hashref with interfaces and their MACs, e.g., 
# {'wlan0' => '74:da:38:ca:8d:e1', 'wlan1' => 'b8:27:eb:b6:7d:51'}
sub get_mac_addrs
{
    my %macs;
    my $ifconfig_output = `/sbin/ifconfig`;

    if(!defined($ifconfig_output)) {
        warn "Failed to run ifconfig";
        return \%macs;
    }

    # Interface output is separated by a blank line
    my @interfaces = split(/\n\s*\n/, $ifconfig_output);
   
    foreach my $interface_text (@interfaces) {
        if($interface_text =~ /^([a-z]+[0-9]*):* /g) {
            my $name = $1;
            if($interface_text =~ /HWaddr ([A-Fa-f0-9]{2}:[A-Fa-f0-9]{2}:[A-Fa-f0-9]{2}:[A-Fa-f0-9]{2}:[A-Fa-f0-9]{2}:[A-Fa-f0-9]{2})/g) {
                $macs{$name} = $1;
            }
            elsif($interface_text =~ /ether ([A-Fa-f0-9]{2}:[A-Fa-f0-9]{2}:[A-Fa-f0-9]{2}:[A-Fa-f0-9]{2}:[A-Fa-f0-9]{2}:[A-Fa-f0-9]{2})/g) {
                $macs{$name} = $1;
            }
        }
    }

    return \%macs;
}
