#!/usr/bin/python


# Script to build OpenVPN with support for OQS cipher suites from local Git clones
# Written/tested for Python 2.7

# Script assumes 
#     - it is being run from the openvpn/build directory
#     - ON WINDOWS: You have the following repos already cloned. You can create these initial clones with the following commands:
#            git clone https://github.com/open-quantum-safe/openssl repos\openssl-oqs-win-x86 -b OpenSSL_1_0_2-stable
#            git clone https://github.com/open-quantum-safe/openssl repos\openssl-oqs-win-x64 -b OpenSSL_1_0_2-stable
#     - ON LINUX: You have the following repos already cloned. You can create these initial clones on the dev branch 
#                 with the following commands:
#            git clone https://github.com/open-quantum-safe/openssl repos/openssl-oqs -b OpenSSL_1_0_2-stable
#            git clone https://github.com/Microsoft/openvpn repos/openvpn-2.4 -b pqcrypto
#            git clone https://github.com/Microsoft/openvpn-build repos/openvpn-build -b pqcrypto
#            git clone https://github.com/Microsoft/openvpn-gui repos/openvpn-gui -b pqcrypto
#     - The above repos are on whatever branch and with whatever local modifications you want to test. This script will
#       will NOT check out any particular branch or reset to any particular state. Use the regular build.py to build
#       the current `official' version from the repos.
#     - Linux: all dependencies are installed
#         - sudo apt-get install autoconf curl nsis libtool libssl-dev \
#                liblz4-dev liblzo2-dev libpam0g-dev gcc-mingw-w64 man2html dos2unix unzip
#     - Windows: Microsoft Visual Studio 2017 is installed in the default location on C:
#                recent Perl is installed and in the system PATH
#                   - http://strawberryperl.com/releases.html (MSI and standalone ZIP versions available)

# Copyright (C) 2018 Microsoft Corporation

import os
import shutil
import subprocess
import re
import fileinput
import stat
import sys
import platform

OPENVPN_TGZ_NAME = '/tmp/openvpn-2.4.tar.gz'
OPENVPN_GUI_TGZ_NAME = '/tmp/openvpn-gui-11.tar.gz'
OPENVPN_LINUX_PREFIX = '/usr/local/openvpn'
OPENVPN_INSTALL_EXE_NAME = 'openvpn-install-2.4.4-I601.exe'

VCVARSALL = '"C:\\Program Files (x86)\\Microsoft Visual Studio\\2017\\Enterprise\\VC\\Auxiliary\\Build\\vcvarsall.bat"'

# Location of scratch dir relative to repos dir
SCRATCH_DIR = '../scratch'

# Run an external command, block until it completes 
def run_command(cmd):
    print '***** Running command: %s' % ' '.join(map(str,cmd))
    p = subprocess.Popen(cmd)
    p.wait()

# Build oqs_openssl
def build_oqs_openssl():
    if platform.system() == 'Windows':
        os.chdir('openssl-oqs-win-x86')

        # Start the X86 build
        run_command(['perl', 'Configure', 'VC-WIN32', 'no-asm', 'enable-static-engine'])
        run_command(['ms\\do_ms.bat'])
        # vcvarsall may change the current working directory. Remember where we were and cd back to it.
        mycwd = os.getcwd()
        # TODO here and below: capture the exit value of the build and bail if it's an error; consider moving to subprocess instead of os.system
        os.system(VCVARSALL + ' x86 && cd /d ' + mycwd + ' && nmake -f ms\\ntdll.mak')
        # Copy the binaries to ../oqs-openssl-win
        shutil.copy('out32dll\\libeay32.dll', '..\\..\\oqs-openssl-win\\x86\\')
        shutil.copy('out32dll\\ssleay32.dll', '..\\..\\oqs-openssl-win\\x86\\')
        # TODO: is there a way to check that the other DLLs in
        # oqs-openssl-win\x86 (e.g., vcruntime140.dll) have the right version to
        # work with these openssl DLLs? somehow check that the dependencies of
        # libeay32.dll and ssleay32.dll are present in the x86 folder. 
        
        # Start the x64 build
        os.chdir('..')
        os.chdir('openssl-oqs-win-x64')
        run_command(['perl', 'Configure', 'VC-WIN64A', 'no-asm', 'enable-static-engine'])

        run_command(['ms\\do_win64a.bat'])
        mycwd = os.getcwd()
        # Before running nmake, we have to run vcvarsall.bat to set the x64 env vars, in the same shell
        os.system(VCVARSALL + ' amd64 && cd /d ' + mycwd + ' && nmake -f ms\\ntdll.mak')
        # Copy the binaries to ../oqs-openssl-win
        shutil.copy('out32dll\\libeay32.dll', '..\\..\\oqs-openssl-win\\x64\\')
        shutil.copy('out32dll\\ssleay32.dll', '..\\..\\oqs-openssl-win\\x64\\')

    if platform.system() == 'Linux':
        os.makedirs(SCRATCH_DIR + '/oqs-openssl-output/openssl')
        os.makedirs(SCRATCH_DIR + '/oqs-openssl-output/ssl')
        prefix = os.path.abspath(SCRATCH_DIR + '/oqs-openssl-output/openssl')
        openssldir = os.path.abspath(SCRATCH_DIR + '/oqs-openssl-output/ssl')
        os.chdir('openssl-oqs')

        run_command(['./config', 'shared', '--prefix='+prefix, '--openssldir='+openssldir])
        run_command(['make'])
        run_command(['make', 'test'])
        run_command(['make', 'install'])

    os.chdir('..')

def on_error(func, path, exc_info):
    """
    Error handler for ``shutil.rmtree``.

    If the error is due to an access error (read only file)
    it attempts to add write permission and then retries.

    If the error is for another reason it re-raises the error.

    Usage : ``shutil.rmtree(path, onerror=onerror)``
    """
    import stat
    if not os.access(path, os.W_OK):
        # Is the error an access error ?
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise


def build_openvpn_linux():
    oqsoutpath = os.path.abspath(SCRATCH_DIR + "/oqs-openssl-output/")
    stagepath = os.path.abspath(SCRATCH_DIR + "/stage/")

    os.chdir('openvpn-2.4')
    run_command(['autoreconf', '-i', '-f', '-v'])

    if not os.path.exists(oqsoutpath):
        print "Didn't find oqs-openssl-output directory, exiting"
        sys.exit(1)

    if os.path.exists(stagepath):
        shutil.rmtree(stagepath)

    os.makedirs(stagepath)

    lib_path = oqsoutpath + '/openssl/lib'
    inc_path = oqsoutpath + '/openssl/include'
    openssl_cflags = 'OPENSSL_CFLAGS="-I' + inc_path + '"'
    openssl_libs = 'OPENSSL_LIBS="-L' + lib_path + ' -Wl,-rpath='+ OPENVPN_LINUX_PREFIX + '/lib ' + ' -lssl -lcrypto -loqs"'

    # we need to use os.system here so that the env vars are set correctly
    os.system('./configure --prefix=' + OPENVPN_LINUX_PREFIX + ' ' + openssl_cflags + ' ' + openssl_libs + ' && make && make DESTDIR=' + stagepath + ' install')

    # We need to copy our versions of libcrypto and libssl into the staging area
    shutil.copy(lib_path + '/libcrypto.so.1.0.0', stagepath + '/' + OPENVPN_LINUX_PREFIX + '/lib')
    shutil.copy(lib_path + '/libssl.so.1.0.0', stagepath + '/' + OPENVPN_LINUX_PREFIX + '/lib')

    os.chdir('..')

    ## Create a staged tarball for Linux
    os.chdir('../scratch/stage')
    # Create placeholders for etc and log directories so they'll be created
    os.makedirs('.' + OPENVPN_LINUX_PREFIX + '/etc')
    os.makedirs('.' + OPENVPN_LINUX_PREFIX + '/log')
    run_command(['touch', '.' + OPENVPN_LINUX_PREFIX + '/etc/.placeholder', '.' + OPENVPN_LINUX_PREFIX + '/log/.placeholder'])
    # Copy initial setup script into sbin directory
    shutil.copy('../../initialsetup.sh', '.' + OPENVPN_LINUX_PREFIX + '/sbin')
    # Copy pointer to privacy statement into doc directory
    shutil.copy('../../PRIVACY.txt', '.' + OPENVPN_LINUX_PREFIX + '/share/doc/openvpn')    
    # Copy service file for systemd into the appropriate place
    os.makedirs('etc/systemd/system')
    shutil.copy('../../pq-openvpn.service', 'etc/systemd/system')
    # Create staged tarball
    run_command(['tar', '-cz', '--group=root', '--owner=root', '-f', '../../pq-openvpn-linux-staged.tar.gz', '.'])
    os.chdir('../../repos')

def build_openvpn_windows():
    os.chdir('openvpn-2.4')
    run_command(['autoreconf', '-i', '-v', '-f'])
    run_command(['./configure'])
    os.chdir('..')

    # the OpenVPN build scripts need a tarball of the same code
    if os.path.exists(OPENVPN_TGZ_NAME):
        os.remove(OPENVPN_TGZ_NAME)
    run_command(['tar', 'czvvf', OPENVPN_TGZ_NAME, 'openvpn-2.4'])

    os.chdir('openvpn-gui')
    run_command(['autoreconf', '-i', '-v', '-f'])
    os.chdir('..')

    if os.path.exists(OPENVPN_GUI_TGZ_NAME):
        os.remove(OPENVPN_GUI_TGZ_NAME)
    run_command(['tar', 'czvvf', OPENVPN_GUI_TGZ_NAME, 'openvpn-gui'])
    
    # Start the build
    os.chdir('openvpn-build')

    # To prevent stale bits from getting used, always delete any source tarballs
    # in windows-nsis's subtree for components that we have changed locally.
    # Right now this is openvpn and openvpn-gui only. The rest can stay
    # since they don't change and we can avoid downloading them each build.
    for tarball in ['openvpn-2.4.tar.gz', 'openvpn-gui-11.tar.gz']:
        tarpath = './windows-nsis/sources/' + tarball
        if os.path.exists(tarpath):
            print "Removing cached tarball " + tarball + " from sources folder"
            os.unlink(tarpath)

    run_command(['./windows-nsis/build-complete'])

    shutil.move("windows-nsis/" + OPENVPN_INSTALL_EXE_NAME, "../../" + OPENVPN_INSTALL_EXE_NAME)
    os.chdir('..')


######## main ##########

# Move into the repos dir
os.chdir('repos')

# Make sure the clones we need are there
if platform.system() == 'Windows':
    if not os.path.exists('openssl-oqs-win-x86'):
        print "OpenSSL-OQS x86 repo not found; see comments at top of this script. Exiting."
        sys.exit(1)
    if not os.path.exists('openssl-oqs-win-x64'):
        print "OpenSSL-OQS x64 repo not found; see comments at top of this script. Exiting."
        sys.exit(1)
elif platform.system() == 'Linux':
    if not os.path.exists('openssl-oqs'):
        print "OpenSSL-OQS repo not found; see comments at top of this script. Exiting."
        sys.exit(1)
    if not os.path.exists('openvpn-2.4'):
        print "OpenVPN repo not found; see comments at top of this script. Exiting."
        sys.exit(1)
    if not os.path.exists('openvpn-build'):
        print "OpenVPN-Build repo not found; see comments at top of this script. Exiting."
        sys.exit(1)
    if not os.path.exists('openvpn-gui'):
        print "OpenVPN-GUI repo not found; see comments at top of this script. Exiting."
        sys.exit(1)
else:
    print "Unrecognized platform " + platform.system()
    sys.exit(1)

# (Re)create the scratch dir
if os.path.exists(SCRATCH_DIR):
    shutil.rmtree(SCRATCH_DIR, False, on_error)
os.makedirs(SCRATCH_DIR)

build_oqs_openssl()

# If this is Windows, we're done
if platform.system() == 'Windows':
    print "Operating system detected as Windows, building OQS-OpenSSL only"
    print "The binaries in Walrus/openvpn/build/oqs-openssl-win should now be updated"
    sys.exit(0)

build_openvpn_linux()

build_openvpn_windows()

print "The staged tarball provides a readily deployable set of binaries on a Linux VM to quickly"
print "bring up a VPN server. It has been tested with the Ubuntu image currently provided by Azure."
print "This installation may be usable as a client with a client configuration file instead, but this"
print "is untested, and the automatic service startup is configured to look for server.ovpn as a config file."
print "To use the staged Linux tarball, do the following as root/using sudo in your VM:"
print "1. cd /"
print "2. tar xvzf <path>/pq-openvpn-linux-staged.tar.gz"
print "3. Create /usr/local/openvpn/etc/server.ovpn and dependent cert/key files as"
print "   needed."
print "4. /usr/local/openvpn/sbin/initialsetup.sh"
print ""
print "To upgrade an existing installation:"
print "1. systemctl stop pq-openvpn"
print "2. cd /"
print "3. tar xvzf <path>/pq-openvpn-linux-staged.tar.gz"
print "4. systemctl start pq-openvpn"
