import os

import paramiko
import pytest


def create_client(server, password='', ssh_key_file=None):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    kwargs = dict(
        hostname=server.host,
        port=server.port,
        username='root',
        allow_agent=False,
        look_for_keys=False,
    )

    if ssh_key_file is not None:
        with open(ssh_key_file) as f:
            kwargs['pkey'] = paramiko.RSAKey.from_private_key(f)
    else:
        kwargs['password'] = password

    c.connect(**kwargs)
    return c


@pytest.mark.parametrize(
    'auth',
    [
        {'password': ''},
        {
            'ssh_key_file': os.path.join(
                os.path.dirname(__file__), 'data', 'id_rsa'
            )
        },
    ],
)
@pytest.mark.parametrize(
    'command,result',
    [
        ('ls', 'file1\nfile2'),
        ('echo 42', '42'),
    ],
)
def test_successful_command(server, auth, command, result):
    client = create_client(server, **auth)
    _stdin, stdout, stderr = client.exec_command(command)
    assert stdout.read().decode() == result, stderr.read()
