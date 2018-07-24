#!/usr/bin/python


# Script to build OpenVPN with support for OQS cipher suites
# Written/tested for Python 2.7

# Script assumes 
#     - it is being run from the openvpn/build directory
#     - any necessary authentication tokens are already available to Git (if not using the public GitHub URLs)
#     - Linux: all dependencies are installed
#         - sudo apt-get install autoconf curl nsis libtool libssl-dev \
#                liblz4-dev liblzo2-dev libpam0g-dev gcc-mingw-w64 man2html dos2unix unzip
#     - Windows: Microsoft Visual Studio 2017 is installed in the default location on C:
#                recent Perl is installed and in the system PATH
#                     - http://strawberryperl.com/releases.html (MSI and standalone ZIP versions available)

# Copyright (C) 2018 Microsoft Corporation

import os
import shutil
import subprocess
import re
import fileinput
import stat
import sys
import platform

OPENVPN_REPO = 'https://github.com/Microsoft/openvpn'
OPENVPN_BRANCH = 'pqcrypto'
OPENVPN_BUILD_REPO = 'https://github.com/Microsoft/openvpn-build'
OPENVPN_BUILD_BRANCH = 'pqcrypto'
OPENVPN_GUI_REPO = 'https://github.com/Microsoft/openvpn-gui'
OPENVPN_GUI_BRANCH = 'pqcrypto'
OPENSSL_OQS_REPO = 'https://github.com/open-quantum-safe/openssl'
OPENSSL_OQS_BRANCH = 'OpenSSL_1_0_2-stable'
OPENSSL_OQS_COMMIT = '01f211920aea41640c647f462e9d7c4c106e3240'

OPENVPN_TGZ_NAME = '/tmp/openvpn-2.4.4.tar.gz'
OPENVPN_GUI_TGZ_NAME = '/tmp/openvpn-gui-11.tar.gz'
OPENVPN_REPO_DIRNAME = 'openvpn-2.4.4'
OPENVPN_INSTALL_EXE_NAME = 'openvpn-install-2.4.4-I601.exe'
OPENVPN_GUI_REPO_DIRNAME = 'openvpn-gui'
OPENVPN_LINUX_PREFIX = '/usr/local/openvpn'

VCVARSALL = '"C:\\Program Files (x86)\\Microsoft Visual Studio\\2017\\Enterprise\\VC\\Auxiliary\\Build\\vcvarsall.bat"'

# Run an external command, block until it completes 
def run_command(cmd):
    print '***** Running command: %s' % ' '.join(map(str,cmd))
    p = subprocess.Popen(cmd)
    p.wait()

# Clone a git repo, using the default name, in the CWD
# If branch is specified, clone that branch
def git_clone(repo_url, branch, local_name, commit=None):
    r = re.compile(".*/(.*)$")
    m = r.match(repo_url)
    repo_name = m.group(1)
    print "Cloning %s ..." % repo_name

    cmd = ['git', 'clone', '-q']
    if branch:
        cmd.extend(['--branch', branch])
   
    cmd.append(repo_url)

    if local_name:    
        cmd.append(local_name)

    run_command(cmd)

    if commit is not None:
        if local_name:
            os.chdir(local_name)
        else:
            print "git_clone with a commit ID only valid with a local_name"
            sys.exit(1)
        cmd = ['git', 'checkout', commit]
        run_command(cmd)
        os.chdir('..')


# Build oqs_openssl
def build_oqs_openssl():
    if platform.system() == 'Windows':
        # Create source trees for x86 and x64
        # Note that there's no way to clean up one tree and re-use it for a different arch
        git_clone(OPENSSL_OQS_REPO, OPENSSL_OQS_BRANCH, 'openssl-oqs-win-x86', OPENSSL_OQS_COMMIT)
        shutil.copytree('openssl-oqs-win-x86', 'openssl-oqs-win-x64')
        os.chdir('openssl-oqs-win-x86')

        # Start the X86 build
        run_command(['perl', 'Configure', 'VC-WIN32', 'no-asm', 'enable-static-engine'])
        run_command(['ms\\do_ms.bat'])
        # vcvarsall may change the current working directory. Remember where we were and cd back to it.
        mycwd = os.getcwd()
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
        mycwd = os.getcwd()
        os.system(VCVARSALL + ' amd64 && cd /d ' + mycwd + ' && nmake -f ms\\ntdll.mak')
        # Copy the binaries to ../oqs-openssl-win
        shutil.copy('out32dll\\libeay32.dll', '..\\..\\oqs-openssl-win\\x64\\')
        shutil.copy('out32dll\\ssleay32.dll', '..\\..\\oqs-openssl-win\\x64\\')

    if platform.system() == 'Linux':
        git_clone(OPENSSL_OQS_REPO, OPENSSL_OQS_BRANCH, 'openssl-oqs', OPENSSL_OQS_COMMIT)

        os.makedirs('oqs-openssl-output/openssl')
        os.makedirs('oqs-openssl-output/ssl')
        prefix = os.path.abspath('oqs-openssl-output/openssl')
        openssldir = os.path.abspath('oqs-openssl-output/ssl')
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
    git_clone(OPENVPN_REPO, OPENVPN_BRANCH, 'openvpn-pq')

    if os.path.exists('stage'):
        shutil.rmtree('stage')

    os.makedirs('stage')
    stagepath = os.path.abspath('stage')

    os.chdir('openvpn-pq')
    run_command(['autoreconf', '-i', '-f', '-v'])

    if not os.path.exists("../oqs-openssl-output/"):
        print "Didn't find oqs-openssl-output directory, exiting"
        sys.exit(1)

    lib_path = os.path.abspath('../oqs-openssl-output/openssl/lib')
    inc_path = os.path.abspath('../oqs-openssl-output/openssl/include')
    openssl_cflags = 'OPENSSL_CFLAGS="-I' + inc_path + '"'
    openssl_libs = 'OPENSSL_LIBS="-L' + lib_path + ' -Wl,-rpath='+ OPENVPN_LINUX_PREFIX + '/lib ' + ' -lssl -lcrypto"'

    # we need to use os.system here so that the env vars are set correctly
    os.system('./configure --prefix=' + OPENVPN_LINUX_PREFIX + ' ' + openssl_cflags + ' ' + openssl_libs + ' && make && make DESTDIR=' + stagepath + ' install')

    # We need to copy our versions of libcrypto and libssl into the staging area
    shutil.copy('../oqs-openssl-output/openssl/lib/libcrypto.so.1.0.0', stagepath + '/' + OPENVPN_LINUX_PREFIX + '/lib')
    shutil.copy('../oqs-openssl-output/openssl/lib/libssl.so.1.0.0', stagepath + '/' + OPENVPN_LINUX_PREFIX + '/lib')

    os.chdir('..')

    # Create a tarball for linux (needed to do Raspberry Pi builds)
    os.makedirs('pq-openvpn-linux')
    shutil.move('oqs-openssl-output', 'pq-openvpn-linux')
    shutil.move('openvpn-pq', 'pq-openvpn-linux')

    run_command(['tar', 'czf', 'pq-openvpn-linux.tgz', 'pq-openvpn-linux'])
    shutil.move('pq-openvpn-linux.tgz', '../pq-openvpn-linux.tgz')

    ## Create a staged tarball for Linux
    os.chdir('stage')
    # Create placeholders for etc and log directories so they'll be created
    os.makedirs('.' + OPENVPN_LINUX_PREFIX + '/etc')
    os.makedirs('.' + OPENVPN_LINUX_PREFIX + '/log')
    run_command(['touch', '.' + OPENVPN_LINUX_PREFIX + '/etc/.placeholder', '.' + OPENVPN_LINUX_PREFIX + '/log/.placeholder'])
    # Copy initial setup script into sbin directory
    shutil.copy('../../initialsetup.sh', '.' + OPENVPN_LINUX_PREFIX + '/sbin')
    # Copy pointer to privacy statement into doc directory
    shutil.copy('../../PRIVACY.txt', '.' + OPENVPN_LINUX_PREFIX + '/share/doc/openvpn')
    # Copy Third Party notice into doc directory
    shutil.copy('../../../../ThirdPartyNotice.txt', '.' + OPENVPN_LINUX_PREFIX + '/share/doc/openvpn')
    # Copy service file for systemd into the appropriate place
    os.makedirs('etc/systemd/system')
    shutil.copy('../../pq-openvpn.service', 'etc/systemd/system')
    # Create staged tarball
    run_command(['tar', '-cz', '--group=root', '--owner=root', '-f', '../../pq-openvpn-linux-staged.tar.gz', '.'])
    os.chdir('..')

def build_openvpn_windows():
    # clone Walrus/openvpn
    git_clone(OPENVPN_REPO, OPENVPN_BRANCH, OPENVPN_REPO_DIRNAME)

    os.chdir(OPENVPN_REPO_DIRNAME)
    run_command(['autoreconf', '-i', '-v', '-f'])
    run_command(['./configure'])
    os.chdir('..')

    # the OpenVPN build scripts need a tarball of the same code
    if os.path.exists(OPENVPN_TGZ_NAME):
        os.remove(OPENVPN_TGZ_NAME)
    run_command(['tar', 'czvvf', OPENVPN_TGZ_NAME, OPENVPN_REPO_DIRNAME])

    # clone Walrus/openvpn-build
    git_clone(OPENVPN_BUILD_REPO, OPENVPN_BUILD_BRANCH, "")
    
    # clone Walrus/openvpn-gui
    git_clone(OPENVPN_GUI_REPO, OPENVPN_GUI_BRANCH, OPENVPN_GUI_REPO_DIRNAME)

    os.chdir(OPENVPN_GUI_REPO_DIRNAME)
    run_command(['autoreconf', '-i', '-v', '-f'])
    os.chdir('..')

    if os.path.exists(OPENVPN_GUI_TGZ_NAME):
        os.remove(OPENVPN_GUI_TGZ_NAME)
    run_command(['tar', 'czvvf', OPENVPN_GUI_TGZ_NAME, OPENVPN_GUI_REPO_DIRNAME])
    
    # Start the build
    os.chdir('openvpn-build')
    run_command(['./windows-nsis/build-complete'])

    shutil.move("windows-nsis/" + OPENVPN_INSTALL_EXE_NAME, "../../" + OPENVPN_INSTALL_EXE_NAME)
    os.chdir('..')


######## main ##########

# (Re)create the scratch dir, switch to it
scratch_dir = "scratch"
if os.path.exists(scratch_dir):
    shutil.rmtree(scratch_dir, False, on_error)
os.makedirs(scratch_dir)
os.chdir(scratch_dir)

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
