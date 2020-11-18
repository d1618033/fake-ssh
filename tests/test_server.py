import sys

import paramiko
import pytest
from logbook import StreamHandler

from fake_ssh import Server, CommandFailure


@pytest.fixture
def server():
    def handler(command: str) -> str:
        if command == "ls":
            return "file1\nfile2"
        elif command.startswith("echo"):
            return command[4:].strip()
        raise CommandFailure(f"Unknown command {command}")

    StreamHandler(sys.stdout).push_application()
    with Server(command_handler=handler) as server:
        yield server


@pytest.fixture
def client(server):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=server.host,
              port=server.port,
              username="root",
              password="",
              allow_agent=False,
              look_for_keys=False)
    return c


@pytest.mark.parametrize("command,result", [
    ("ls", "file1\nfile2"),
    ("echo 42", "42"),
])
def test_successful_command(client, command, result):
    _stdin, stdout, stderr = client.exec_command(command)
    assert stdout.read().decode() == result, stderr.read()
