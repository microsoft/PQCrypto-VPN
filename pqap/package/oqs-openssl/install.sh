#!/bin/bash


# This has to be run as root
if [ "$EUID" -ne 0 ]
    then echo "Please run as root"
    exit
fi

INSTALL_LOCATION=/opt/

echo "Installing OQS-OpenSSL to $INSTALL_LOCATION"

echo "Copying ssl to $INSTALL_LOCATION"
cp -r ssl $INSTALL_LOCATION 
echo "Copying openssl to $INSTALL_LOCATION"
cp -r openssl $INSTALL_LOCATION
echo "Running ldconfg"
sudo ldconfig $INSTALL_LOCATION/openssl/lib/
echo "Done"

echo "To check, make sure:" 
echo '    sudo ldconfig -p |grep "/opt/openssl"'
echo "is not null "

