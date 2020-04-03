# Welcome to the PQCrypto-VPN project!

Please start with our [project page at Microsoft Research](https://www.microsoft.com/en-us/research/project/post-quantum-crypto-vpn/) for an overview of this project.

This project takes a fork of the OpenVPN software and combines it with post-quantum cryptography. In this way, we can test these algorithms with VPNs, evaluating functionality and performance of the quantum resistant cryptography. Because this project is experimental, it should not be used to protect sensitive data or communications at this time. Further cryptanalysis and research must first be done over the next few years to determine which algorithms are truly post-quantum safe. 

This work is sponsored by [Microsoft Research Security and Cryptography](https://www.microsoft.com/en-us/research/group/security-and-cryptography/), as part of our [post-quantum cryptography project](https://www.microsoft.com/en-us/research/project/post-quantum-cryptography/). Along with academic and industry collaborators, we have designed the following algorithms and contributed them to the [Open Quantum Safe](https://openquantumsafe.org/) project and are usable in this fork of OpenVPN:

* [Frodo](https://github.com/Microsoft/PQCrypto-LWEKE): a key exchange protocol based on the learning with errors problem
* [SIDH](https://github.com/Microsoft/PQCrypto-SIDH): a key exchange protocol based on Supersingular Isogeny Diffie-Hellman
* [Picnic](https://github.com/Microsoft/Picnic): a signature algorithm using symmetric-key primitives and non-interactive zero-knowledge proofs

We will also enable other ciphersuites as much as we are able to make them work. Our OpenVPN fork depends on the [Open Quantum Safe project fork of OpenSSL](https://github.com/open-quantum-safe/openssl), so contributors looking to add support for a new algorithm should ensure it is supported by Open Quantum Safe. 

We also provide software and instructions for building a post-quantum secure VPN appliance with a Raspberry Pi 3.  The device acts as a WiFi access point, and tunnels all of its traffic over the post-quantum VPN.  This has two main advantages when compared to using a VPN client on the device.  First, installing VPN client software is not required.  Second, using VPN software can be error prone, and not all traffic will be protected if there are configuration errors.  With a hardware device, all devices connecting to it get post-quantum security transparently.  See the `pqap` directory, and the README file there for more information.

---

## Releases

Please see [our releases page](https://github.com/Microsoft/PQCrypto-VPN/releases) for pre-built binaries for both Windows and Ubuntu Linux.

---

## Tell us what you think

For bug reports, feature requests, and other issues with the code itself, please raise them in [our issues tracker](https://github.com/Microsoft/PQCrypto-VPN/issues). For pull requests, please see the next section on Contributing. For other feedback, questions, comments, or anything else you'd like to tell us, you can talk to us at [msrsc@microsoft.com](mailto:msrsc@microsoft.com).

---

## Prerequisites

* To run the binaries: either Ubuntu Linux 18.04 or newer, or Windows 10. Only 64-bit operating systems are supported.
* To build the source: Ubuntu Linux 18.04. Newer versions of Ubuntu are likely to also be fine, but we have not tested them.

OpenVPN for Windows does not build natively on Windows; it is only cross-compiled on Linux. Therefore all building from source must be done on Linux.

---

## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.microsoft.com.

When you submit a pull request, a CLA-bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., label, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA, so if you have
already signed a CLA with Microsoft for another project, that covers contributions to us as well.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

---

## Cloning

Our build relies on Git submodules for the sources to OQS-OpenSSL and OpenVPN. When cloning, be sure to use the `--recurse-submodules` option to `git clone`. If you forget, you should be able to run `git submodule init` followed by `git submodule update` to retrieve the submodules after a clone. For your convenience, here is a full clone command:

	git clone --branch dev-1.3 --recurse-submodules https://github.com/microsoft/PQCrypto-VPN.git

## Build Process Overview

Following OpenVPN's build process, binaries for both Linux and Windows are produced by a Linux-based build system that cross-compiles for Windows. Our build process first builds liboqs and the Open Quantum Safe fork of OpenSSL, and then our version of OpenVPN which uses them.

There is one Python script for running the build:

* _build.py_: This does a full build of everything on Linux: both Linux and Windows versions of liboqs, OpenSSL, OpenVPN, and on Windows only, OpenVPN-GUI. The outputs of the build process are a gzipped tarball that can be unpacked onto an Ubuntu Linux system, and a Windows installer executable for installing on 64-bit Windows.

See the comments at the top of `build.py` for a list of prerequisite packages that must be installed before building. There is also a Dockerfile in `openvpn/build/docker` to build the installers in a container.

Previous versions of PQCrypto-VPN required OpenSSL ot be built on Windows, but now cross-compilation on Linux is supported there as well. As a result, our entire build process runs only on Linux, and we no longer require doing part of the build process on Windows nor are dependent on the Visual C++ Runtime Redistributable DLLs.

---

## Subprojects

To enable our build of OpenVPN, we have forks of three OpenVPN GitHub repos that we have modified to enable this functionality. Issues and pull requests are welcomed in these subprojects as well. The same requirements to sign a CLA apply to these repos.

* https://github.com/microsoft/openvpn
* https://github.com/microsoft/openvpn-build
* https://github.com/microsoft/openvpn-gui

Open Quantum Safe's implementations of the algorithms are in their liboqs library, which is consumed by the OpenSSL fork below.

* https://github.com/open-quantum-safe/liboqs

We also use the OpenSSL fork maintained by the Open Quantum Safe Project for the implementations of the algorithms themselves. As we work closely with OQS, we do not maintain our own fork of their code. They also welcome opening issues and pull requests directly at their project.

* https://github.com/open-quantum-safe/openssl

We are temporarily using a private fork of both liboqs and OpenSSL while both upstream code bases are still rapidly changing, and keeping them snapped to a known working point. When the upstream branches have stable release points, we will return to referencing them directly. For now these are our private forks:

* https://github.com/kevinmkane/liboqs
* https://github.com/kevinmkane/openssl

---

## Setup instructions

The setup instructions are the same whether you download our pre-made binaries, or if you build them yourself.

### Windows client

After running the installer executable, you will need to create a configuration file. This can be located anywhere, though OpenVPN-GUI uses `%USERPROFILE%\OpenVPN\config`. Samples have beeen provided in the `openvpn\config` directory:

* _client-win.ovpn_: Client authenticating with a certificate
* _client-passdb.ovpn_: Client authenticating with a username/password. This sample configuration file is based on Linux, so you will need to adjust the pathnames for a Windows host.

The tunnel can then be established by running OpenVPN-GUI, right-clicking on its system tray icon, selecting the configuration file, and choosing Connect. OpenVPN can be run from an elevated command prompt, just like on Linux; see the Linux instructions below if you prefer this method.

### Linux client or server

Unpack `pq-openvpn-linux-staged.tgz` from the root directory as root. This will drop the installation in `/usr/local/openvpn` as well as an automatic startup script suitable for Ubuntu hosts running `systemd`.

Optional: If you are configuring a server and want OpenVPN to start automatically at boot, run the `initialsetup.sh` script installed in the `/usr/local/openvpn/sbin` directory. We recommend you only do this when you have thoroughly tested your configuration.

You then need to create a configuration file. If running a server, the automatic start scripts expect this to be called `server.ovpn` and located in `/usr/local/openvpn/etc`. If you are running a client or a server from the command line, it can be called whatever you want as you will provide the configuration filename when starting OpenVPN. The following samples have been provided in the `openvpn/config` directory:

* _client.ovpn_: Client authenticating with a certificate
* _client-passdb.ovpn_: Client authenticating with a username/password
* _server.ovpn_: Server only accepting client certificate authentication
* _server-passdb.ovpn_: Server only accepting username/password authentication

The `ecdh-curve` configuration directive is used to select the key exchange algorithm and must be present to guarantee a post-quantum algorithm is selected. You can see the list of valid choices from the list of supported algorithms at OQS's OpenSSL fork here: https://github.com/open-quantum-safe/openssl#supported-algorithms

If no `ecdh-curve` directive is present, `p256_sikep434` is chosen by default. If present, the `ecdh-curve` directive must agree on both client and server, or a session will fail to negotiate. It is possible to pick a non-post quantum algorithm from the list of all algorithms supported by OpenSSL; make sure only to select choices from the list linked above to ensure use of a post-quantum key exchange.

The authentication algorithm depends on the types of certificates provided as part of the configuration. You can use classical signature algorithms (like RSA or ECDSA), but these are not post-quantum. See the instructions in `openvpn/config/picnic-pki.md` for creating certificates using Picnic-L1FS as the signature algorithm as one post-quantum option. See the above list of supported algorithms for post-quantum signature algorithms.

OpenVPN is then started by running from a root command prompt:

``
    /usr/local/openvpn/sbin/openvpn --config <config file name>
``

This will keep OpenVPN running in the foreground and keep control of your terminal. You can safely terminate OpenVPN by typing Control-C; OpenVPN will clean up its network setup before exiting. You can add the `--daemon` to the command line or `daemon` to the configuration file to make it go into the background, and you can then use `kill` to send its process a signal to terminate when desired.

### Setting up username/password authentication on a Linux server 

This setup uses the host's built-in username and password database for authentication as an expedient method of authentication. Any valid user presenting a correct password will be able to authenticate and connect.

 Suggested procedure for creating a user that can't log into the host but can authenticate to OpenVPN with these settings:

``
useradd -c "<User Full Name Here>" -d /usr/local/openvpn -s /bin/false <username>  
``

``
passwd <username>
``

`<username>` and `<User Full Name Here>` are user-specific inputs. The above example assumes `${INSTALL_ROOT}` is  `/usr/local/openvpn`; modify as needed if the path is different. It is critical that whatever follows the `-s` parameter does NOT appear in the `/etc/shells` file on the host; `/bin/false` should never be in there.

 For additional security, in `/etc/ssh/sshd_config` should be the line `PasswordAuthentication no` to prevent any password authentication. This appears to be the default for Azure VMs but not for regular Linux hosts. This will, of course, require using public key authentication for administrators to log into the host directly. If password authentication to the host is required, create a group for OpenVPN users and then instruct the SSH server to deny logins to that group as follows as root:

1. `groupadd openvpn`
2. Add a `-g openvpn` argument to the `useradd` command above
3. Add a `DenyGroups openvpn` directive to `/etc/ssh/sshd_config`

Already-created users can be retroactively added to this group with `usermod -a -G openvpn <username>`.

Although having `/bin/false` as the shell should prevent users from doing anything, denying the group will make the SSH  return an authentication failure; not having this will cause the authentication to succeed, but when the host executes `/bin/false` as the shell, it will return immediately and the connection should then close. But since SSH allows authenticated users to do a number of things like open network tunnels without starting a shell, SSH access should be explicitly denied to prevent any functionality being invoked by a successful authentication.

### Setting up certificate authentication

The process of setting up RSA-signed certificates for client and server authentication is the same for regular OpenVPN, and so we refer you to their [excellent instructions](https://openvpn.net/index.php/open-source/documentation/howto.html#pki) for setting up a Certificate Authority (CA) and issuing certificates. Even if you use username/password authentication for clients, servers must still have a certificate, and the certificate of the CA must be provided to clients.

The analogous process for Picnic-signed certificates is described in in `openvpn/config/picnic-pki.md`.
This uses the OpenSSL command line tool from the Open Quantum Safe fork of OpenSSL. 

---

# Known Issues

Only the server currently lists the key exchange algorithm used in its log output as "group_id", and it is only listed by the OpenSSL numerical identifier, which we realize is not very user-friendly. After the group_id value will be a message that says either `(post-quantum key exchange)` or `(NOT post-quantum key exchange)` to address this. OpenSSL does not expose the necessary API surface to obtain this information on the client.

Although the p256_sikep434 hybrid key exchange is chosen by default, it is possible to choose a non-post quantum key exchange with the `ecdh-curve` configuration directive. We have chosen this default and provided ample documentation to ensure as much as possible that a non-post quantum key exchange is not selected accidentally.

The Open Quantum Safe fork of OpenSSL only provides post-quantum algorithms for TLS 1.3 connections. Use of TLS 1.2 or earlier has no post-quantum algorithms. Therefore, it is vital the `tls-version-min 1.3` directive is always present in configuration files to ensure clients and servers never fall back to older versions of TLS.
