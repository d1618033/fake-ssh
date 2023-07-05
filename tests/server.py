# from __future__ import with_statement
import logging
import os
import socket
import threading

import paramiko as ssh

from Python26SocketServer import TCPServer
from Python26SocketServer import ThreadingMixIn
from fake_filesystem import FakeFile
from fake_filesystem import FakeFilesystem

# import six
#
# Debugging
#
logging.basicConfig(filename='/tmp/fab.log', level=logging.DEBUG)
logger = logging.getLogger('server.py')

#
# Constants
#

HOST = '127.0.0.1'
PORT = 2200
USER = 'username'
HOME = '/'
RESPONSES = {
    'ls /simple': 'some output',
    'ls /': """AUTHORS
FAQ
Fabric.egg-info
INSTALL
LICENSE
MANIFEST
README
build
docs
fabfile.py
fabfile.pyc
fabric
requirements.txt
setup.py
tests""",
    'both_streams': [
        'stdout',
        'stderr'
    ],
}
FILES = FakeFilesystem({
    '/file.txt': 'contents',
    '/file2.txt': 'contents2',
    '/folder/file3.txt': 'contents3',
    '/empty_folder': None,
    '/tree/file1.txt': 'x',
    '/tree/file2.txt': 'y',
    '/tree/subfolder/file3.txt': 'z',
    '/etc/apache2/apache2.conf': 'Include other.conf',
    HOME: None  # So $HOME is a directory
})
PASSWORDS = {
    'root': 'root',
    USER: 'password'
}


def _local_file(filename):
    return os.path.join(os.path.dirname(__file__), filename)


SERVER_PRIVKEY = _local_file('private.key')
CLIENT_PUBKEY = _local_file('client.key.pub')
CLIENT_PRIVKEY = _local_file('client.key')
CLIENT_PRIVKEY_PASSPHRASE = 'passphrase'


def _equalize(lists, fillval=None):
    """
    Pad all given list items in ``lists`` to be the same length.
    """
    lists = list(map(list, lists))
    upper = max(len(x) for x in lists)
    for lst in lists:
        diff = upper - len(lst)
        if diff:
            lst.extend([fillval] * diff)
    return lists


class TestServer(ssh.ServerInterface):
    """
    Test server implementing the 'ssh' lib's server interface parent class.

    Mostly just handles the bare minimum necessary to handle SSH-level things
    such as honoring authentication types and exec/shell/etc requests.

    The bulk of the actual server side logic is handled in the
    ``serve_responses`` function and its ``SSHHandler`` class.
    """

    def __init__(self, passwords, home, pubkeys, files):
        self.username = None
        self.event = threading.Event()
        self.passwords = passwords
        self.pubkeys = pubkeys
        self.files = FakeFilesystem(files)
        self.home = home
        self.command = None

    def check_channel_request(self, kind, chanid):
        if kind == 'session':
            return ssh.common.OPEN_SUCCEEDED
        return ssh.common.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_exec_request(self, channel, command):
        self.command = command
        self.event.set()
        return True

    def check_channel_pty_request(self, *args):
        return True

    def check_channel_shell_request(self, channel):
        self.event.set()
        return True

    def check_auth_password(self, username, password):
        self.username = username
        passed = self.passwords.get(username) == password
        return ssh.common.AUTH_SUCCESSFUL if passed else ssh.common.AUTH_FAILED

    def check_auth_publickey(self, username, key):
        self.username = username
        return ssh.common.AUTH_SUCCESSFUL if self.pubkeys else ssh.common.AUTH_FAILED

    def get_allowed_auths(self, username):
        return 'password,publickey'


class SSHServer(ThreadingMixIn, TCPServer):
    """
    Threading TCPServer subclass.
    """

    @staticmethod
    def _socket_info(addr_tup):
        """
        Clone of the very top of Paramiko 1.7.6 SSHClient.connect().

        We must use this in order to make sure that our address family matches
        up with the client side (which we cannot control, and which varies
        depending on individual computers and their network settings).
        """
        hostname, port = addr_tup
        addr_info = socket.getaddrinfo(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)

        for (family, socktype, proto, canonname, sockaddr) in addr_info:
            if socktype == socket.SOCK_STREAM:
                af = family
                addr = sockaddr
                break
        else:
            # some OS like AIX don't indicate SOCK_STREAM support, so just
            # guess. :(
            af, _, _, _, addr = socket.getaddrinfo(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)

        return af, addr

    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True):  # noqa
        # Prevent "address already in use" errors when running tests 2x in a
        # row.
        self.allow_reuse_address = True

        # Handle network family/host addr (see docstring for _socket_info)
        family, addr = self._socket_info(server_address)
        self.address_family = family

        TCPServer.__init__(self, addr, RequestHandlerClass, bind_and_activate)


class FakeSFTPHandle(ssh.SFTPHandle):
    """
    Extremely basic way to get SFTPHandle working with our fake setup.
    """

    def __init__(self, flags: int = ...):
        super().__init__(flags)
        self.readfile = None

    def chattr(self, attr):
        self.readfile.attributes = attr
        return ssh.sftp.SFTP_OK

    def stat(self):
        return self.readfile.attributes


class PrependList(list):
    def prepend(self, val):
        self.insert(0, val)


def expand(path):
    """
    '/foo/bar/biz' => ('/', 'foo', 'bar', 'biz')
    'relative/path' => ('relative', 'path')
    """
    # Base case
    if path in ['', os.path.sep]:
        return [path]

    ret = PrependList()
    directory, filename = os.path.split(path)

    while directory and directory != os.path.sep:
        ret.prepend(filename)
        directory, filename = os.path.split(directory)

    ret.prepend(filename)
    # Handle absolute vs relative paths
    ret.prepend(directory if directory == os.path.sep else '')

    return ret


def contains(folder, path):
    """
    contains(('a', 'b', 'c'), ('a', 'b')) => True
    contains('a', 'b', 'c'), ('f',)) => False
    """
    return False if len(path) >= len(folder) else folder[:len(path)] == path


def missing_folders(paths):
    """
    missing_folders(['a/b/c']) => ['a', 'a/b', 'a/b/c']
    """
    ret = []
    pool = set(paths)

    for path in paths:
        expanded = expand(path)

        for i in range(len(expanded)):
            folder = os.path.join(*expanded[:len(expanded) - i])

            if folder and folder not in pool:
                pool.add(folder)
                ret.append(folder)

    return ret


def canonicalize(path, home):
    ret = path

    if not os.path.isabs(path):
        ret = os.path.normpath(os.path.join(home, path))

    return ret


class FakeSFTPServer(ssh.SFTPServerInterface):
    def __init__(self, server, *args, **kwargs):
        super().__init__(server, *args, **kwargs)
        self.server = server
        files = self.server.files  # noqa

        # Expand such that omitted, implied folders get added explicitly
        for folder in missing_folders(files.keys()):
            files[folder] = None

        self.files = files

    def canonicalize(self, path):
        """
        Make non-absolute paths relative to $HOME.
        """
        return canonicalize(path, self.server.home) # noqa

    def list_folder(self, path):
        path = self.files.normalize(path)

        expanded_files = map(expand, self.files)
        expanded_path = expand(path)

        candidates = [x for x in expanded_files if contains(x, expanded_path)]
        children = []

        for candidate in candidates:
            cut = candidate[:len(expanded_path) + 1]

            if cut not in children:
                children.append(cut)

        results = [self.stat(os.path.join(*x)) for x in children]
        bad = not results or any(x == ssh.sftp.SFTP_NO_SUCH_FILE for x in results)

        return ssh.sftp.SFTP_NO_SUCH_FILE if bad else results

    def open(self, path, flags, attr):
        path = self.files.normalize(path)

        try:
            fobj = self.files[path]
        except KeyError:
            if flags & os.O_WRONLY:
                # Only allow writes to files in existing directories.
                if os.path.dirname(path) not in self.files:
                    return ssh.sftp.SFTP_NO_SUCH_FILE

                self.files[path] = fobj = FakeFile('', path)
            # No write flag means a read, which means they tried to read a
            # nonexistent file.
            else:
                return ssh.sftp.SFTP_NO_SUCH_FILE

        f = FakeSFTPHandle()
        f.readfile = f.writefile = fobj

        return f

    def stat(self, path):
        path = self.files.normalize(path)

        try:
            fobj = self.files[path]
        except KeyError:
            return ssh.sftp.SFTP_NO_SUCH_FILE

        return fobj.attributes

    # Don't care about links right now
    lstat = stat

    def chattr(self, path, attr):
        path = self.files.normalize(path)

        if path not in self.files:
            return ssh.sftp.SFTP_NO_SUCH_FILE

        # Attempt to gracefully update instead of overwrite, since things like
        # chmod will call us with an SFTPAttributes object that only exhibits
        # e.g. st_mode, and we don't want to lose our filename or size...
        for which in 'size uid gid mode atime mtime'.split():
            attname = 'st_' + which
            incoming = getattr(attr, attname)

            if incoming is not None:
                setattr(self.files[path].attributes, attname, incoming)

        return ssh.sftp.SFTP_OK

    def mkdir(self, path, attr):
        self.files[path] = None
        return ssh.sftp.SFTP_OK
