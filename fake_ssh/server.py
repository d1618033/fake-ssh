import errno
import selectors
import socket
import threading
from contextlib import suppress
from typing import Any, Optional, Tuple

import logbook

from .command import (
    CommandHandler,
    CommandHandlerWrapped,
    command_handler_wrapper,
)
from .connection_handler import ConnectionHandler

_logger = logbook.Logger(__name__)


class Server:
    def __init__(
        self,
        command_handler: CommandHandler,
        host: str = "127.0.0.1",
        port: int = 0,
    ):
        self._socket: Optional[socket.SocketIO] = None
        self._thread: Optional[threading.Thread] = None
        self.host: str = host
        self._port: int = port
        self._command_handler: CommandHandlerWrapped = command_handler_wrapper(
            command_handler
        )

    def __enter__(self) -> "Server":
        self.run_non_blocking()
        return self

    def run_non_blocking(self) -> None:
        self._create_socket()
        self._thread = threading.Thread(target=self._run)
        self._thread.setDaemon(True)
        self._thread.start()

    def _create_socket(self) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.bind((self.host, self._port))
        self._socket.listen(5)
        _logger.info(f"Starting ssh server on {self.host}:{self.port}")

    def run_blocking(self) -> None:
        self._create_socket()
        self._run()

    def _run(self) -> None:
        assert self._socket is not None
        sock = self._socket
        selector = selectors.DefaultSelector()
        selector.register(sock, selectors.EVENT_READ)
        while sock.fileno() > 0:
            _logger.debug("Waiting for incoming connections ...")
            events = selector.select(timeout=1.0)
            if not events:
                continue
            try:
                conn, addr = sock.accept()
            except OSError as ex:
                if ex.errno in (errno.EBADF, errno.EINVAL):
                    break
                raise
            _logger.debug(f"... got connection {conn} from {addr}")
            handler = ConnectionHandler(conn, self._command_handler)
            thread = threading.Thread(target=handler.run)
            thread.setDaemon(True)
            thread.start()

    def __exit__(self, *exc_info: Tuple[Any]) -> None:
        self.close()

    def close(self) -> None:
        if self._socket:
            with suppress(Exception):
                self._socket.shutdown(socket.SHUT_RDWR)
                self._socket.close()
            self._socket = None
        if self._thread is not None:
            self._thread.join()
            self._thread = None

    @property
    def port(self) -> int:
        if self._socket is None:
            raise RuntimeError("Server not running")
        return self._socket.getsockname()[1]
