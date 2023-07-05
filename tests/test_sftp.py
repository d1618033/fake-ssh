import os
import stat
from pathlib import Path

import pytest
from paramiko.sftp_client import SFTPClient
from pytest import raises


def files_equal(fname1: str, fname2: str) -> bool:
    if os.stat(fname1).st_size == os.stat(fname2).st_size:
        with open(fname1, "rb") as f1, open(fname2, "rb") as f2:
            if f1.read() == f2.read():
                return True


def test_put(sftp_client: SFTPClient, tmpdir):
    target_name = str(tmpdir.join("foo"))
    print(target_name)

    sftp_client.put(__file__, target_name, confirm=True)
    assert files_equal(target_name, __file__)
    assert Path(target_name).exists()


def test_get(sftp_client: SFTPClient, tmpdir):
    target_name = tmpdir.join("foo")

    sftp_client.get(__file__, target_name)
    assert files_equal(target_name, __file__)


@pytest.mark.fails_on_windows
def test_symlink(sftp_client: SFTPClient, tmpdir):
    foo = str(tmpdir.join("foo"))
    bar = str(tmpdir.join("bar"))

    open(foo, "w").write("foo")

    sftp_client.symlink(foo, bar)
    assert os.path.islink(bar)


@pytest.mark.fails_on_windows
def test_lstat(sftp_client: SFTPClient, tmpdir):
    foo = str(tmpdir.join("foo"))
    bar = str(tmpdir.join("bar"))

    open(foo, "w").write("foo")
    os.symlink(foo, bar)

    state = sftp_client.stat(bar)
    lstat = sftp_client.lstat(bar)

    assert state.st_size != lstat.st_size


def test_listdir(sftp_client: SFTPClient, tmpdir):
    Path(tmpdir.join('foo')).write_text('foo')
    Path(tmpdir.join('bar')).write_text('bar')

    dir_contents = sftp_client.listdir(str(tmpdir))
    assert sorted(dir_contents) == ["bar", "foo"]

    with raises(IOError):
        sftp_client.listdir("/123_no_dir")


def test_remove(sftp_client: SFTPClient, tmpdir):
    test_file = str(tmpdir.join("x"))
    open(test_file, "w").write("X")

    sftp_client.remove(test_file)
    assert not os.listdir(tmpdir)


def test_unlink(sftp_client: SFTPClient, tmpdir):
    test_file = str(tmpdir.join("x"))
    Path(test_file).write_text("X")

    sftp_client.unlink(test_file)
    assert not os.listdir(tmpdir)


def test_mkdir(sftp_client: SFTPClient, tmpdir):
    target_dir = str(tmpdir.join("foo"))
    sftp_client.mkdir(target_dir)

    assert Path(target_dir).exists()
    assert Path(target_dir).is_dir()


def test_rmdir(sftp_client: SFTPClient, tmpdir):
    # target_dir = tmpdir.join("foo")
    # os.makedirs(target_dir)
    target_dir = tmpdir.mkdir('foo')
    sftp_client.rmdir(str(target_dir))

    assert not os.path.exists(target_dir)
    assert not os.path.isdir(target_dir)


@pytest.mark.fails_on_windows
def test_chmod(sftp_client: SFTPClient, tmpdir):
    test_file = str(tmpdir.join("foo"))
    open(test_file, "w").write("X")

    sftp_client.chmod(test_file, 0o600)
    st = os.stat(test_file)

    check_bits = stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO
    assert st.st_mode & check_bits == 0o600


@pytest.mark.fails_on_windows
def test_chown(sftp_client: SFTPClient, tmpdir):
    test_file = str(tmpdir.join("foo"))
    open(test_file, "w").write("X")

    # test process probably can't change file uids
    # so just test if no exception occurs
    sftp_client.chown(test_file, os.getuid(), os.getgid())


def test_handle_stat(sftp_client: SFTPClient, tmpdir):
    test_file = str(tmpdir.join("foo"))
    open(test_file, "w").write("X")

    handle = sftp_client.open(test_file)
    handle.stat()


def test_rename(sftp_client: SFTPClient, tmpdir):
    test_file = str(tmpdir.join("foo"))
    open(test_file, "w").write("X")

    renamed_test_file = str(tmpdir.join("bar"))
    sftp_client.rename(test_file, renamed_test_file)

    assert os.path.exists(renamed_test_file)
    assert not os.path.exists(test_file)


@pytest.fixture(params=[
    ("truncate", "/etc/passwd", 0),
    ("utime", "/", (0, 0)),
    ("listdir_attr", "/"),
    ("readlink", "/etc"),
])
def unsupported_call(request):
    return request.param


def _test_sftp_unsupported_calls(server, unsupported_call):
    for uid in server.users:
        with server.client(uid) as c:
            meth, args = unsupported_call[0], unsupported_call[1:]
            sftp = c.open_sftp()

            with raises(IOError) as exc:
                getattr(sftp, meth)(*args)

            assert str(exc.value) == "Operation unsupported"
