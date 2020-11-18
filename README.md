Mock SSH Server
-----------------


Do you...

* have a test that SSHs into a server and don't want the hassle of setting one up for testing?

* think monkeypatching isn't as good as it sounds?

* want to develop an application and need a fake server to return predefined results?

This package is for you!

Installation
-----------

```
pip install fake-ssh
```

Usage
-----

## Blocking Server

A blocking server is often used for development purposes.

Simply write yourself a `server.py` file:

```python
from typing import Optional
from fake_ssh import Server


def handler(command: str) -> Optional[str]:
    if command.startswith("ls"):
        return "file1\nfile2\n"
    elif command.startswith("echo"):
        return command[4:].strip() + "\n"

if __name__ == "__main__":
    Server(command_handler=handler, port=5050).run_blocking()

```

And run it:

```
$ python3 server.py
```

In a separate terminal, run:

```
$ ssh root@127.0.0.1 -p 5050 echo 42
42
                                                                         
$ ssh root@127.0.0.1 -p 5050 ls
file1
file2
```

(if you are prompted for a password, you can leave it blank)

## Non-Blocking Server

A non blocking server is often used in tests. 

This server runs in a thread and allows you to run some tests in parallel.

```python
import paramiko
import pytest

from fake_ssh import Server


def handler(command):
    if command == "ls":
        return "file1\nfile2\n"


@pytest.fixture
def server():
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


def test_ls(client):
    _stdin, stdout, stderr = client.exec_command("ls")
    assert stdout.read().decode() == "file1\nfile2\n"

```