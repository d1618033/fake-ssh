import sys
from typing import Iterator

import paramiko
import pytest
from logbook import StreamHandler
from paramiko.sftp_client import SFTPClient

from fakessh import CommandFailure
from fakessh import Server


@pytest.fixture(scope="session")
def server():
    def handler(command: str) -> str:
        if command == "ls":
            return "file1\nfile2"

        if command.startswith("echo"):
            return command[4:].strip()

        raise CommandFailure(f"Unknown command {command}")

    StreamHandler(sys.stdout).push_application()
    with Server(command_handler=handler) as server:
        yield server


@pytest.fixture()
def sftp_client(server) -> Iterator[SFTPClient]:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs = dict(
        hostname=server.host,
        port=server.port,
        username="root",
        allow_agent=False,
        look_for_keys=False,
    )
    kwargs["password"] = "password"

    c.connect(**kwargs)
    yield c.open_sftp()
