FROM ubuntu:18.04

RUN apt update && apt install -y \
        liblz4-dev               \
        liblzo2-dev              \
        libpam-dev               \
        libssl-dev               \
        libtool                  \
        libtool-bin              \
        cmake                    \
        make                     \
        autoconf                 \
        python                   \
        git                      \
        curl                     \
        libpam0g-dev             \
        unzip                    \
        net-tools                \
        pkg-config               \
        wget                     \
        nsis                     \
        gcc-mingw-w64            \
        man2html                 \
        dos2unix
        
RUN cd /opt && \
        git clone --recurse-submodules https://github.com/microsoft/PQCrypto-VPN.git && \
        cd PQCrypto-VPN
        
# If you have Windows OQS-OpenSSL binaries from following the Windows build instructions
# and want to build the Windows installer, place libeay32.dll and ssleay32.dll for x86 into
# a directory named x86, and the versions for x64 into a directory named x64. Then uncomment
# the two COPY directives below.

# COPY x86/libeay32.dll x86/ssleay32.dll /opt/PQCrypto-VPN/openvpn/build/oqs-openssl-win/x86/
# COPY x64/libeay32.dll x64/ssleay32.dll /opt/PQCrypto-VPN/openvpn/build/oqs-openssl-win/x64/
        
RUN cd /opt/PQCrypto-VPN/openvpn/build && python build.py

# If all steps complete successfully, the following installers should be available:
# Linux: /opt/PQCrypto-VPN/openvpn/build/pq-openvpn-linux-staged.tar.gz
# Windows (if built): /opt/PQCrypto-VPN/openvpn/build/openvpn-install-2.4.4-I601.exe
