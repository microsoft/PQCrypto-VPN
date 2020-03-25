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
        dos2unix                 \
        ninja-build
        
RUN cd /opt && \
        git clone -b dev-1.3 --recurse-submodules https://github.com/microsoft/PQCrypto-VPN.git || true

RUN cd /opt/PQCrypto-VPN/openvpn/build && python build.py

# If all steps complete successfully, the following installers should be available:
# Linux: /opt/PQCrypto-VPN/openvpn/build/pq-openvpn-linux-staged.tar.gz
# Windows (if built): /opt/PQCrypto-VPN/openvpn/build/openvpn-install-2.4.4-I601.exe
