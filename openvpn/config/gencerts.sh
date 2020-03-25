#!/bin/bash

# Set LD_LIBRARY_PATH to the location of the OQS-OpenSSL libcrypto.so.1.1 and
# libssl.so.1.1. The default setting assumes they are in the current working
# directory. If you have installed the binaries somewhere on the system, set
# this path to be the lib subdirectory, like /usr/local/oqssl/lib.
export LD_LIBRARY_PATH=.

# Set OPENSSL to the full path location of the openssl binary, including the
# filename. See the notes above if you have installed these binaries somewhere
# onto your system.
OPENSSL=./openssl

# Set FILEPREFIX to whatever you want the filenames for the keys, certificates,
# and other files generated to be.
FILEPREFIX=picnic

# Set days to the number of days for which certificates will be valid, including the CA.
DAYS=3650

${OPENSSL} genpkey -algorithm picnicl1fs -out ${FILEPREFIX}-CA.key
${OPENSSL} req -x509 -key ${FILEPREFIX}-CA.key -out ${FILEPREFIX}-CA.crt -subj "/CN=Picnic CA/name=Picnic CA" -days ${DAYS} -sha512
${OPENSSL} req -new -newkey picnicl1fs -keyout ${FILEPREFIX}-server.key -out ${FILEPREFIX}-server.csr -nodes -sha512 -subj "/CN=Picnic VPN Server/name=Picnic VPN Server"
${OPENSSL} req -new -newkey picnicl1fs -keyout ${FILEPREFIX}-client.key -out ${FILEPREFIX}-client.csr -nodes -sha512 -subj "/CN=Picnic VPN Client/name=Picnic VPN Client"
${OPENSSL} x509 -req -in ${FILEPREFIX}-server.csr -out ${FILEPREFIX}-server.crt -CA ${FILEPREFIX}-CA.crt -CAkey ${FILEPREFIX}-CA.key -CAcreateserial -days ${DAYS} -sha512 -extensions server -extfile cert-exts
${OPENSSL} x509 -req -in ${FILEPREFIX}-client.csr -out ${FILEPREFIX}-client.crt -CA ${FILEPREFIX}-CA.crt -CAkey ${FILEPREFIX}-CA.key -CAcreateserial -days ${DAYS} -sha512 -extensions client -extfile cert-exts
