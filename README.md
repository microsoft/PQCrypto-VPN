# Welcome to the PQCrypto-VPN project!

Please start with our [project page at Microsoft Research](https://www.microsoft.com/en-us/research/project/post-quantum-crypto-vpn/) for an overview of this project.

This project takes a fork of the OpenVPN software and combines it with post-quantum cryptography. In this way, we can test these algorithms with VPNs, evaluating functionality and performance of the quantum resistant cryptography. Because this project is experimental, it should not be used to protect sensitive data or communications at this time. Further cryptanalysis and research must first be done over the next few years to determine which algorithms are truly post-quantum safe. 

This work is sponsored by [Microsoft Research Security and Cryptography](https://www.microsoft.com/en-us/research/group/security-and-cryptography/), as part of our [post-quantum cryptography project](https://www.microsoft.com/en-us/research/project/post-quantum-cryptography/). Along with academic and industry collaborators, we have designed the following algorithms and contributed them to the [Open Quantum Safe](https://openquantumsafe.org/) project and are usable in this fork of OpenVPN:

* [Frodo](https://github.com/Microsoft/PQCrypto-LWEKE): a key exchange protocol based on the learning with errors problem
* [SIDH](https://github.com/Microsoft/PQCrypto-SIDH): a key exchange protocol based on Supersingular Isogeny Diffie-Hellman
* [Picnic](https://github.com/Microsoft/Picnic): a signature algorithm using symmetric-key primitives and non-interactive zero-knowledge proofs

We will also enable other ciphersuites as much as we are able to make them work. Our OpenVPN fork depends on the [Open Quantum Safe project fork of OpenSSL](https://github.com/open-quantum-safe/openssl), so contributors looking to add support for a new algorithm should ensure it is supported by Open Quantum Safe. 

We test on Ubuntu Server 16.04 LTS as our Linux platform, and on Windows 10 with Visual Studio 2017. We have not yet tested any other combinations but will offer comment on what we think will be required with other versions, particularly for Microsoft platforms.

We also provide software and instructions for building a post-quantum secure VPN appliance with a Raspberry Pi 3.  The device acts as a WiFi access point, and tunnels all of its traffic over the post-quantum VPN.  This has two main advantages when compared to using a VPN client on the device.  First, installing VPN client software is not required.  Second, using VPN software can be error prone, and not all traffic will be protected if there are configuration errors.  With a hardware device, all devices connecting to it get post-quantum security transparently.  See the `pqap` directory, and the README file there for more information.

---

## Releases

Please see [our releases page](https://github.com/Microsoft/PQCrypto-VPN/releases) for pre-built binaries for both Windows and Ubuntu Linux.

---

## Tell us what you think

For bug reports, feature requests, and other issues with the code itself, please raise them in [our issues tracker](https://github.com/Microsoft/PQCrypto-VPN/issues). For pull requests, please see the next section on Contributing. For other feedback, questions, comments, or anything else you'd like to tell us, you can talk to us at [msrsc@microsoft.com](mailto:msrsc@microsoft.com).

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

Our build relies on Git submodules for the sources to OQS-OpenSSL and OpenVPN. When cloning, be sure to use the `--recurse-submodules` option to `git clone`. If you forget, you should be able to run `git submodules init` followed by `git submodules update` to retrieve the submodules after a clone.

## Build Process Overview

Following OpenVPN's build process, binaries for both Linux and Windows are produced by a Linux-based build system that cross-compiles for Windows. Because we require a fork of OpenSSL instead of the standard version, we have to build our own versions for both Linux and Windows. As there is no supported system for cross-compilation of OpenSSL for Windows on Linux, building OpenSSL requires a build step on a Windows system. Our build system on Windows requires Visual Studio 2017. Visual Studio 2019 should work but requires the "MSVC v141 - VS 2017 C++ x64/x86 build tools (v14.16)" component to be installed.

There is one Python script for running the build:

* _build.py_: On Windows, this builds only OpenSSL. On Linux, this builds everything, using the output from the Windows OpenSSL build to generate the Windows binaries. This builds out of the submodule repos which are initially set to the revisions for our official builds. Modifications can be tested by making changes to the submodule repos after cloning. 

The Linux build will expect to find the Windows OpenSSL DLLs in the `openvpn\build\oqs-openssl-win\{x86,x64}`. After building these DLLs on Windows, copy them to your Linux host's repo in this location. Because we build on Windows with Visual Studio 2017, we have included the redistributable Visual C++ Runtime 2017 DLLs in this repo and configured the build to include them in the installer. If the Windows DLL's are not present on the Linux build host, the Windows build will be skipped and only Linux binaries will be built.

### Visual Studio and Visual C++ Runtime Redistributable Note

We have not tested building with other versions of Visual Studio other than 2017 Enterprise. Visual Studio 2019 should work, but will require installing the Visual Studio 

Building OpenSSL DLLs with Visual Studio will make it dependent upon the Visual C++ runtime corresponding to the version of Visual Studio build tools you use. You can check [this page on docs.microsoft.com](https://docs.microsoft.com/en-us/cpp/ide/determining-which-dlls-to-redistribute) for information about where to find the DLLs. Doing this will require you to clone the repos yourself and use the devbuild.py script above, as our official version is locked to version 2017. To use a different version of Visual Studio, you have two options:

1. _Include the appropriate redistributable DLLs in the OpenVPN installer built by our build process._ In the openvpn-build repo, edit `windows-nsis\openvpn.nsi`, and add/change/remove lines from the Section "-OpenSSL DLLs" to name the DLLs for the version of Visual Studio you're using to build. Add them as well at the bottom where the "Delete" lines are so they are properly removed when uninstalled. Then place those DLLs alongside the OpenSSL DLLs in the `oqs-openssl-win` subdirectory.
2. _Install the redistributable installer on the host directly._ Using the site above, locate the standalone installer appropriate to your version of Visual Studio and run it on the host where you'll be running OpenVPN. The references to these DLLs in `openvpn.nsi` can then be removed. This does require running the standalone installer on each host where you will run OpenVPN.

Using a different version of Visual Studio will also require changing the `build.py` or `devbuild.py` script to change the VCVARSALL declaration near the top to point to the location of the 1vcvarsall.bat` file as installed by your version of Visual Studio. This sets up the path and other environment variables so the script can find the build tools.

---

## Subprojects

To enable our build of OpenVPN, we have forks of three OpenVPN GitHub repos that we have modified to enable this functionality. Please open all issues here on the PQCrypto-VPN issue tracker. Pull requests are welcomed in the subprojects. The same requirements to sign the Microsoft CLA apply to these repos.

* https://github.com/Microsoft/openvpn
* https://github.com/Microsoft/openvpn-build
* https://github.com/Microsoft/openvpn-gui

We also use the OpenSSL fork maintained by the Open Quantum Safe Project for the implementations of the algorithms themselves. As we work closely with OQS, we do not maintain our own fork of their code. They also welcome opening issues and pull requests directly at their project.

* https://github.com/open-quantum-safe/openssl

Due to changes in the content of the upstream OQS OpenSSL fork, we are temporarily using a fork of that repo to fix the resulting build break. We will return to the official upstream branch when we migrate to the OpenSSL 1.1.1 fork.

* https://github.com/kevinmkane/openssl

No issues or pull requests are accepted on this private fork. Please address all issues and pull requests to the Open Quantum Safe repositories linked above.

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

OpenVPN is then started by running from a root command prompt:

``
    /usr/local/openvpn/sbin/openvpn --config <config file name>
``

This will keep OpenVPN running in the foreground and keep control of your terminal. You can safely terminate OpenVPN by typing Control-C; OpenVPN will clean up its network setup before exiting. You can add the `--daemon` to the command line to make it go into the background, and you can then use `kill` to send its process a signal to terminate when desired.

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

The build system currently does some extraneous work, such as cross-compiling OpenSSL for Windows on Linux, and then using the pre-made OpenSSL binaries. At present the Open Quantum Safe extensions do not cross-compile.

OpenVPN's line length limit in configuration files limits how many ciphersuites we can specify in order to guarantee a post-quantum ciphersuite is selected.

Our code is currently based on OpenVPN 2.4.4 and the Open Quantum Safe fork of OpenSSL 1.0.2. Because work is still underway to integrate liboqs with the OpenSSL 1.1 series, and OpenVPN began supporting OpenSSL 1.1 with version 2.4.5, we have not yet updated to the latest version of OpenVPN. To address CVE-2018-9336 which affects OpenVPN versions 2.4.5 and earlier, we have backported the fix from version 2.4.6.
