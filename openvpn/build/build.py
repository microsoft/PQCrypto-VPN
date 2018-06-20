#!/usr/bin/env python2.7


# Script to build OpenVPN with support for OQS cipher suites
# Written/tested for Python 2.7

# Script assumes
#     - it is being run from the openvpn/build directory
#     - any necessary authentication tokens are already available to Git
#       (if not using the public GitHub URLs)
#     - Linux: all dependencies are installed
#         - sudo apt-get install autoconf curl nsis libtool libssl-dev \
#             liblz4-dev liblzo2-dev libpam0g-dev gcc-mingw-w64 man2html \
#             dos2unix unzip
#         - mingw when cross compiling for windows (apt-get install mingw-w64)
#     - Darwin: all dependencies are installed
#         - XCode xcode-select --install
#     - Windows:
#         - Microsoft Visual Studio 2017 is installed in the default
#           location on C:
#         - recent Perl is installed and in the system PATH
#           http://strawberryperl.com/releases.html (MSI and standalone ZIP
#           versions available)
#         - recent Python is installed and in the system PATH
#           msiexec -i /tmp/python-2.7.14.msi -q
#           from https://www.python.org/ftp/python/

import argparse
import os
import shutil
import subprocess
import re
import stat
import sys
import platform

from contextlib import contextmanager

OPENVPN_REPO = 'https://github.com/Microsoft/openvpn'
OPENVPN_BRANCH = 'pqcrypto'
OPENVPN_BUILD_REPO = 'https://github.com/Microsoft/openvpn-build'
OPENVPN_BUILD_BRANCH = 'pqcrypto'
OPENVPN_BUILD_REPO_DIRNAME = 'openvpn-build'
OPENVPN_GUI_REPO = 'https://github.com/Microsoft/openvpn-gui'
OPENVPN_GUI_BRANCH = 'pqcrypto'
OPENSSL_OQS_REPO = 'https://github.com/open-quantum-safe/openssl'
OPENSSL_OQS_BRANCH = 'OpenSSL_1_0_2-stable'
OPENSSL_OQS_COMMIT = '01f211920aea41640c647f462e9d7c4c106e3240'
OPENSSL_OQS_REPO_DIRNAME = 'openssl-oqs'
OPENVPN_TGZ_NAME = '/tmp/openvpn-2.4.4.tar.gz'
OPENVPN_GUI_TGZ_NAME = '/tmp/openvpn-gui-11.tar.gz'
OPENVPN_REPO_DIRNAME = 'openvpn-2.4.4'
OPENVPN_INSTALL_EXE_NAME = 'openvpn-install-2.4.4-I601.exe'
OPENVPN_GUI_REPO_DIRNAME = 'openvpn-gui'
PREFIX = '/usr/local/openvpn'

BUILD_TARGET_OS = platform.system()

SOURCES_DIR = os.path.abspath('./sources')
BUILD_DIR = os.path.abspath('./build')
STAGE_DIR = os.path.abspath('./stage')
IMAGE_DIR = os.path.abspath('./images')

OPENSSL_CONFIG_PLATFORM_SCRIPT = os.path.abspath('gentoo-config-0.9.8')
RES_PRIVACY_TXT = os.path.abspath('PRIVACY.txt')
RES_INITIAL_SETUP = os.path.abspath('initialsetup.sh')
RES_PQ_OPENVPN_SERVICE = os.path.abspath('pq-openvpn.service')

VCVARSALL = (
    '"C:\\Program Files (x86)\\Microsoft Visual Studio\\2017\\'
    'Enterprise\\VC\\Auxiliary\\Build\\vcvarsall.bat"'
)
VERBOSE = False

LINUX_UBUNTU_POST = ('''
The staged tarball provides a readily deployable set of binaries on a Linux VM
to quickly bring up a VPN server. It has been tested with the Ubuntu image
currently provided by Azure. This installation may be usable as a client with
a client configuration file instead, but this is untested, and the automatic
service startup is configured to look for server.ovpn as a config file. To use
the staged Linux tarball, do the following as root/using sudo in your VM:

1. cd /
2. tar xvzf <path>/pq-openvpn-linux-staged.tar.gz
3. Create /usr/local/openvpn/etc/server.ovpn and dependent cert/key files as
   needed.
4. /usr/local/openvpn/sbin/initialsetup.sh

To upgrade an existing installation:
1. systemctl stop pq-openvpn
2. cd /
3. tar xvzf <path>/pq-openvpn-linux-staged.tar.gz
4. systemctl start pq-openvpn
''')

LINUX_WINDOWS_POST = ('''
The openvpn installer was built and needs to be tested on a windows machine.
''')

WINDOWS_POST = ('''
Only the openssl lib was build. OpenVPN needs to be build with mingw.

The libeay32.dll and ssleay32.dll need to be copied from the x86 or x64 stage.
''')

#
# Private Utility Methods
# they should be shared with other python scripts to avoid
# repeating code, errors, documentation
#


@contextmanager
def chdir(path):
    '''
    chdir helper that returns to the cwd when the context is left.
    avoids chdir('somewhere');do_something();chdir('..')
    '''
    oldcwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(oldcwd)


def die(message):
    '''
    Display a message and stop the build with a nonzero exit code.
    '''
    sys.stderr.write(message)
    sys.stderr.write('\n')
    sys.exit(1)


def git_clone(repo_url, branch, local_name, commit=None):
    '''
    Clone a git repo, using the default name, in the CWD
    If branch is specified, clone that branch
    '''
    r = re.compile('.*/(.*)$')
    m = r.match(repo_url)
    repo_name = m.group(1)
    if os.path.isdir(local_name):
        if commit is None:
            return git_pull(local_name)
        else:
            die(
                'git_clone with commit cannot be cached. Use --skip-download'
                ' or clean the SOURCES_DIR ({SOURCES_DIR})'.format(
                    SOURCES_DIR=SOURCES_DIR))
    print('Cloning %s ...' % repo_name)

    cmd = ['git', 'clone']

    if not VERBOSE:
        cmd.append('-q')

    if branch:
        cmd.extend(['--branch', branch])

    cmd.append(repo_url)

    if local_name:
        cmd.append(local_name)

    run_command(cmd)

    if commit is None:
        return

    if not os.path.isdir(local_name):
        die('git_clone with a commit ID only valid with a local_name')

    with chdir(local_name):
        run_command(['git', 'checkout', commit])


def git_pull(local_name):
    '''
    Update a existing git repository.
    '''
    with chdir(local_name):
        run_command(['git', 'pull'])


def git_restore(local_name):
    '''
    Restore a git repository from a tar.gz
    '''
    package_name = '{local_name}.tar.gz'.format(local_name=local_name)
    package_file = os.path.abspath('{sources_dir}/{package_name}'.format(
        package_name=package_name,
        sources_dir=SOURCES_DIR))
    if not os.path.exists(package_file):
        print(
            'No package for {package_name} available in the sources'.format(
                package_name=package_name))
    run_command(['tar', 'xzf', package_file])


def git_store(local_name):
    '''
    Store a git repository in a tar.gz
    '''
    package_name = '{local_name}.tar.gz'.format(local_name=local_name)
    run_command([
        'tar', 'czf', package_name,
        local_name])


def info_build(options):
    print('Building {BUILD_TARGET_OS} on {platform}.'.format(
        BUILD_TARGET_OS=BUILD_TARGET_OS,
        platform=platform.system()))

    if options.skip_download:
        print(
            'Skip downloading sources. They are expected in'
            ' {SOURCES_DIR}'.format(
            SOURCES_DIR=SOURCES_DIR))
    else:
        print('Downloading sources')

    if options.skip_openssl:
        print(
            'Skip building OpenSSL. It is expected installed to'
            ' "{STAGE_DIR}/lib" and "{STAGE_DIR}/include".'.format(
                STAGE_DIR=STAGE_DIR))
    else:
        print('Building OpenSSL')

    if options.skip_test:
        print('Skip running "make test" on OpenSSL build')
    else:
        print('Running "make test" on OpenSSL build.')

    if options.skip_openvpn:
        print(
            'Skip building OpenVPN. Used on Windows to produce the OpenSSL'
            ' binaries only.')
    else:
        print('Building OpenVPN')

    if options.skip_images:
        print(
            'Skip building images from {STAGE_DIR}. Used to inspect the build'
            ' result.'.format(
                STAGE_DIR=STAGE_DIR))
    else:
        print(
            'Creating packed images of build binaries in {IMAGE_DIR}.'.format(
                IMAGE_DIR=IMAGE_DIR))
    print('')

def mkdir(dir_name):
    '''
    Create a directory with the given name if it does not exist yet
    '''
    if os.path.isdir(dir_name):
        return
    os.makedirs(dir_name)


def rmtree_force(func, path, exc_info):
    '''
    Error handler for ``shutil.rmtree``.

    If the error is due to an access error (read only file)
    it attempts to add write permission and then retries.

    If the error is for another reason it re-raises the error.

    Usage : ``shutil.rmtree(path, onerror=onerror)``
    '''
    if not os.access(path, os.W_OK):
        # Is the error an access error ?
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise


def run_command(cmd, environment=None):
    '''
    Run an external command, block until it completes.
    When the exitcode is nonzero, exit the build.
    '''
    if VERBOSE:
        print(
            '***** Running command: %s\nin %s'
            % (' '.join(map(str, cmd)), os.getcwd()))

    self_env = os.environ.copy()
    if environment is not None:
        for (key, value) in environment.items():
            if value is None and key in self_env.keys():
                # allow removal of environment variables
                del self_env[key]
                continue
            self_env[str(key)] = str(value)
        if VERBOSE:
            print('***** Environment: %s' % (str(self_env),))

    p = subprocess.Popen(
        cmd,
        env=self_env)
    p.wait()
    if p.returncode is not 0:
        die(
            'Running command %sfailed with exitcode %d'
            % (' '.join(map(str, cmd)), p.returncode))


def run_command_capture(cmd):
    '''
    Run an external command, return its stdout.
    '''
    if VERBOSE:
        print(
            '***** Running command: %s in %s'
            % (' '.join(map(str, cmd)), os.getcwd()))
    try:
        return subprocess.check_output(cmd)
    except subprocess.CalledProcessError as error:
        die('Running command %s failed with exitcode %d'
            % (' '.join(map(str, cmd)), error.returncode))


#
# Download Remote Resources
#


def download_remote_repositories():
    '''
    Download all remote sources and create packages from the repositories.

    This avoids traffic when repeating builds and allows to verify the
    build sources.
    '''
    mkdir(SOURCES_DIR)
    with chdir(SOURCES_DIR):
        git_clone(
            OPENSSL_OQS_REPO, OPENSSL_OQS_BRANCH, OPENSSL_OQS_REPO_DIRNAME,
            OPENSSL_OQS_COMMIT)
        git_clone(OPENVPN_REPO, OPENVPN_BRANCH, OPENVPN_REPO_DIRNAME)

        git_clone(
            OPENVPN_BUILD_REPO, OPENVPN_BUILD_BRANCH,
            OPENVPN_BUILD_REPO_DIRNAME)
        git_clone(
            OPENVPN_GUI_REPO, OPENVPN_GUI_BRANCH,
            OPENVPN_GUI_REPO_DIRNAME)

        git_store(OPENVPN_REPO_DIRNAME)
        git_store(OPENVPN_BUILD_REPO_DIRNAME)
        git_store(OPENVPN_GUI_REPO_DIRNAME)

        git_store(OPENSSL_OQS_REPO_DIRNAME)
        git_store(OPENVPN_REPO_DIRNAME)


#
# OpenSSL
#


def build_oqs_openssl_windows(test_build=False):
    '''
    Create source trees for x86 and x64
    Note that there's no way to clean up one tree and re-use it for a
    different arch.

    this builds the ssl-dlls on windows, as they cannot be cross-compiled
    from a linux buildhost.
    '''
    git_restore(OPENSSL_OQS_REPO_DIRNAME)
    if BUILD_TARGET_OS == 'Windows' and platform.system() == 'Linux':
        if not os.path.isdir(os.path.join(STAGE_DIR, 'x86')):
            die(
                'There is a manual step copying the windows-build ssl dll to'
                ' a location that openvpn configure can find it.')
    shutil.copytree(OPENSSL_OQS_REPO_DIRNAME, 'openssl-oqs-win-x86')
    with chdir('openssl-oqs-win-x86'):

        # Start the X86 build
        run_command([
            'perl', 'Configure', 'VC-WIN32', 'no-asm',
            'enable-static-engine'])
        run_command(['ms\\do_ms.bat'])
        # vcvarsall may change the current working directory. Remember where
        # we were and cd back to it.
        mycwd = os.getcwd()
        os.system(
            VCVARSALL + ' x86 && cd /d ' +
            mycwd + ' && nmake -f ms\\ntdll.mak')
        # Copy the binaries to ../oqs-openssl-win
        shutil.copy(
            os.path.join('out32dll', 'libeay32.dll'),
            os.path.join(STAGE_DIR, 'x86'))
        shutil.copy(
            os.path.join('out32dll', 'ssleay32.dll'),
            os.path.join(STAGE_DIR, 'x86'))

        # TODO: is there a way to check that the other DLLs in
        # oqs-openssl-win\x86 (e.g., vcruntime140.dll) have the right version
        # to work with these openssl DLLs? somehow check that the dependencies
        # of libeay32.dll and ssleay32.dll are present in the x86 folder.

    # Start the x64 build
    shutil.copytree(OPENSSL_OQS_REPO_DIRNAME, 'openssl-oqs-win-x64')
    with chdir('openssl-oqs-win-x64'):
        run_command([
            'perl', 'Configure', 'VC-WIN64A', 'no-asm',
            'enable-static-engine'])

        run_command(['ms\\do_win64a.bat'])
        mycwd = os.getcwd()
        # Before running nmake, we have to run vcvarsall.bat to set the x64
        # env vars, in the same shell
        mycwd = os.getcwd()
        os.system(
            VCVARSALL + ' amd64 && cd /d ' + mycwd +
            ' && nmake -f ms\\ntdll.mak')

        shutil.copy(
            os.path.join('out32dll', 'libeay32.dll'),
            os.path.join(STAGE_DIR, 'x64'))
        shutil.copy(
            os.path.join('out32dll', 'ssleay32.dll'),
            os.path.join(STAGE_DIR, 'x64'))


def build_oqs_openssl_unix(test_build=False):
    '''
    Build openssl for linux/unix
    '''
    git_restore(OPENSSL_OQS_REPO_DIRNAME)

    with chdir(OPENSSL_OQS_REPO_DIRNAME):
        target_system = run_command_capture(
            ['/bin/sh', OPENSSL_CONFIG_PLATFORM_SCRIPT])
        target_system = target_system.strip()
        run_command([
            'sed', '-i org', '1s|^|#!/usr/bin/env perl\\\n#|', 'Configure'])
        run_command([
            './Configure', 'shared',
            '--prefix={PREFIX}'.format(PREFIX=PREFIX),
            target_system])
        run_command(['make'])
        if test_build:
            run_command(['make', 'test'])
        run_command([
            'make', 'install',
            'INSTALL_PREFIX={STAGE_DIR}'.format(STAGE_DIR=STAGE_DIR),
            'INSTALL_TOP="/"'])


#
# OpenVPN
#


def build_openvpn():
    '''
    Build openvpn on linux/unix/windows
    '''

    git_restore(OPENVPN_REPO_DIRNAME)

    with chdir(OPENVPN_REPO_DIRNAME):
        run_command(['autoreconf', '-i', '-f', '-v'])
        lib_dir = os.path.abspath(
            os.path.join(STAGE_DIR, PREFIX[1:], 'lib'))
        include_dir = os.path.abspath(
            os.path.join(STAGE_DIR, PREFIX[1:], 'include'))

        if not os.path.exists(lib_dir):
            die(
                'Did not find lib_dir: {lib_dir} directory.'.format(
                    lib_dir=lib_dir))
        if not os.path.exists(include_dir):
            die(
                'Did not find include_dir: {include_dir} directory.'.format(
                    include_dir=include_dir))

        extra_openssl_libs = ''
        if BUILD_TARGET_OS == 'Linux':
            extra_openssl_libs = '-Wl,-rpath={prefix}/lib'.format(
                prefix=PREFIX)

        run_env = dict(
            OPENSSL_LIBS=(
                '-L{lib_dir} {extra_openssl_libs} -lssl -lcrypto'.format(
                    lib_dir=lib_dir,
                    extra_openssl_libs=extra_openssl_libs)),
            OPENSSL_CFLAGS='-I{include_dir}'.format(include_dir=include_dir),
            PKCS11_HELPER_CFLAGS='',
            PKCS11_HELPER_LIBS='')

        if BUILD_TARGET_OS == 'Windows':
            run_env['CHOST'] = 'i686-w64-mingw32'
            run_env['CBUILD'] = 'i686-pc-linux-gnu'

        run_command([
            './configure',
            '--prefix={prefix}'.format(prefix=PREFIX),
            '--disable-plugins',
            '--with-special-build=pq-openvpn'],
            environment=run_env)
        run_command(['make'], environment=run_env)
        run_command([
            'make', 'install',
            'DESTDIR={destdir}'.format(destdir=STAGE_DIR)])


def pack_images_windows():
    '''
    Pack the redistributable image for windows
    '''
    with chdir(OPENVPN_BUILD_REPO_DIRNAME):
        shutil.move(
            os.path.join('windows-nsis', OPENVPN_INSTALL_EXE_NAME),
            os.path.join(IMAGE_DIR, OPENVPN_INSTALL_EXE_NAME))


def pack_images_unix():
    '''
    Pack the redistributable image for unix.
    '''
    # Create a tarball for linux (needed to do Raspberry Pi builds)
    tarball_name = 'pq-openvpn-{platform}'.format(
        platform=BUILD_TARGET_OS.lower())
    tarball_file = '{tarball_name}.tar.gz'.format(tarball_name=tarball_name)

    if os.path.isdir(tarball_name):
        shutil.rmtree(tarball_name, False, rmtree_force)
    mkdir(tarball_name)

    shutil.copytree(
        STAGE_DIR,
        os.path.join(tarball_name, 'staged'))
    shutil.copytree(
        os.path.join(BUILD_DIR, OPENVPN_REPO_DIRNAME),
        os.path.join(tarball_name, OPENVPN_REPO_DIRNAME))

    run_command([
        'tar', 'czf',
        os.path.join(IMAGE_DIR, tarball_file),
        tarball_name])

    shutil.rmtree(tarball_name, False, rmtree_force)

    sbin_dir = os.path.join(STAGE_DIR, PREFIX[1:], 'sbin')
    etc_dir = os.path.join(STAGE_DIR, PREFIX[1:], 'etc')
    etc_systemd_dir = os.path.join(etc_dir, 'systemd/system')
    log_dir = os.path.join(STAGE_DIR, PREFIX[1:], 'log')
    doc_dir = os.path.join(STAGE_DIR, PREFIX[1:], 'share/doc/openvpn')

    # Create a staged tarball for Linux
    if not os.path.isdir(sbin_dir):
        print('!!! no sbin in stage, did openvpn make install run?')
        exit(1)

    if BUILD_TARGET_OS == 'Darwin':
        # Copy pointer to privacy statement into doc directory
        shutil.copy(RES_PRIVACY_TXT, doc_dir)

    if BUILD_TARGET_OS == 'Linux':
        # Systemd convenience scripts
        with chdir(STAGE_DIR):
            # Create placeholders for etc and log directories so they are
            # available for copy
            mkdir(etc_dir)
            mkdir(log_dir)
            mkdir(etc_systemd_dir)
            run_command([
                'touch', os.path.join(etc_dir, '.placeholder')])
            run_command([
                'touch', os.path.join(log_dir, '.placeholder')])

            # Copy initial setup script into sbin directory
            shutil.copy(RES_INITIAL_SETUP, sbin_dir)
            # Copy pointer to privacy statement into doc directory
            shutil.copy(RES_PRIVACY_TXT, doc_dir)
            # Copy service file for systemd into the appropriate place
            shutil.copy(RES_PQ_OPENVPN_SERVICE, etc_systemd_dir)
            # Create staged tarball

    # Pack the staged files into a package.
    with chdir(STAGE_DIR):
        # Handle tar != tar (linux vs osx)
        tar_options = run_command_capture(['tar', '--help'])
        cmd = ['tar', '-cz']
        if '--group=' in tar_options:
            cmd.append('--group=root')
        if '--owner=' in tar_options:
            cmd.append('--owner=root')

        cmd.append('-f')
        cmd.append(os.path.join(
            IMAGE_DIR, '{tarball_name}-staged.tar.gz'.format(
                tarball_name=tarball_name)))
        cmd.append('.')
        run_command(cmd)
        print('{tarball_name} is now stored in {IMAGE_DIR}'.format(
            tarball_name=tarball_name, IMAGE_DIR=IMAGE_DIR))


def build_oqs_openssl(test_build=False):
    '''
    Build oqs_openssl
    '''
    if BUILD_TARGET_OS == 'Windows':
        build_oqs_openssl_windows(test_build)

    if BUILD_TARGET_OS == 'Linux' or BUILD_TARGET_OS == 'Darwin':
        build_oqs_openssl_unix(test_build)


def pack_images():
    '''
    Build oqs_openssl
    '''
    if BUILD_TARGET_OS == 'Windows':
        pack_images_windows()

    if BUILD_TARGET_OS == 'Linux' or BUILD_TARGET_OS == 'Darwin':
        pack_images_unix()


def post_messages():
    '''
    Display messages when the build has completed
    '''
    if BUILD_TARGET_OS == 'Linux':
        print(LINUX_UBUNTU_POST)
    if BUILD_TARGET_OS == 'Windows' and platform.system() == 'Linux':
        print(LINUX_WINDOWS_POST)
    if BUILD_TARGET_OS == 'Windows' and platform.system() == 'Windows':
        print(WINDOWS_POST)


#
# commandline options
#
# enables --help


parser = argparse.ArgumentParser(
    description='Build OpenVPN PQ.',
    epilog='Copyright 2018 Microsoft')

parser.add_argument(
    '--no-clean', action='store_true',
    help=('clean build directory before.'),
    default=False)
parser.add_argument(
    '--verbose', action='store_true',
    help=('Be verbose.'),
    default=False)
parser.add_argument(
    '--target', action='store',
    choices=['Linux', 'Darwin', 'Windows'],
    help=(
        'Build target platform. Defaults to "{platform}".'
        ' On Linux you may build Linux and Windows using mingw.'
        ' On Windows you may only build the openssl library'
        ' On Darwin you may only build the Darwin binaries.'.format(
            platform=platform.system())),
    default=platform.system())

parser.add_argument(
    '--prefix', nargs='?', action='store', dest='prefix',
    help=('prefix for the packaged results.'),
    default=PREFIX)
parser.add_argument(
    '--build-dir', nargs='?', action='store', dest='build_dir',
    help=('directory where to build.'),
    default=BUILD_DIR)
parser.add_argument(
    '--sources-dir', nargs='?', action='store', dest='sources_dir',
    help=('directory where to find downloaded content.'),
    default=SOURCES_DIR)
parser.add_argument(
    '--image-dir', nargs='?', action='store', dest='image_dir',
    help=('directory where to store the build results.'),
    default=IMAGE_DIR)

parser.add_argument(
    '--skip-test', action='store_true',
    help=('skip running make test on build binaries.'),
    default=False)
parser.add_argument(
    '--skip-openssl', action='store_true',
    help=('skip building openssl.'),
    default=False)
parser.add_argument(
    '--skip-openvpn', action='store_true',
    help=('skip building openvpn.'),
    default=False)
parser.add_argument(
    '--skip-images', action='store_true',
    help=('skip building images from staged.'),
    default=False)
parser.add_argument(
    '--skip-download', action='store_true',
    help=('skip downloading files, use BUILD_DIR contents.'),
    default=False)
options, unknown = parser.parse_known_args()


#
#  Main
#

BUILD_DIR = os.path.abspath(options.build_dir)
SOURCES_DIR = os.path.abspath(options.sources_dir)
IMAGE_DIR = os.path.abspath(options.image_dir)
VERBOSE = options.verbose
PREFIX = options.prefix
BUILD_TARGET_OS = options.target

if not options.no_clean:
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR, False, rmtree_force)
if BUILD_TARGET_OS == 'Windows' and platform.system() == 'Windows':
    # windows cannot really build openvpn, this is done on linux with
    # mingw.
    options.skip_openvpn = True
    options.skip_images = True
if BUILD_TARGET_OS == 'Windows' and platform.system() == 'Linux':
    # openssl was build on windows and copied back to this host.
    options.skip_openssl = True

mkdir(BUILD_DIR)
mkdir(IMAGE_DIR)
mkdir(STAGE_DIR)

info_build(options)

if not options.skip_download:
    download_remote_repositories()

with chdir(BUILD_DIR):
    if not options.skip_openssl:
        build_oqs_openssl(not options.skip_test)

    if not options.skip_openvpn:
        build_openvpn()

    if not options.skip_images:
        pack_images()

    post_messages()
