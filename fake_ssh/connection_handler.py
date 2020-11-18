import os
import socket
import threading
from queue import Queue
from typing import Dict, Optional

import logbook
import paramiko

from .command import CommandHandler

ChannelID = int
_SERVER_KEY = os.path.join(os.path.dirname(__file__), "server_key")
_logger = logbook.Logger(__name__)


class ConnectionHandler(paramiko.ServerInterface):
    def __init__(
        self, client_conn: socket.SocketIO, command_handler: CommandHandler
    ):
        self._command_handler: CommandHandler = command_handler
        self.thread: Optional[threading.Thread] = None
        self.command_queues: Dict[ChannelID, Queue] = {}
        self.transport: paramiko.Transport = paramiko.Transport(client_conn)
        self.transport.add_server_key(paramiko.RSAKey(filename=_SERVER_KEY))

    def run(self) -> None:
        self.transport.start_server(server=self)
        while True:
            channel: paramiko.Channel = self.transport.accept()
            if channel is None:
                _logger.debug("Closing session")
                break
            if channel.chanid not in self.command_queues:
                self.command_queues[channel.chanid] = Queue()
            thread = threading.Thread(
                target=self._handle_client, args=(channel,)
            )
            thread.setDaemon(True)
            thread.start()

    def _handle_client(self, channel: paramiko.Channel) -> None:
        try:
            command = self.command_queues[channel.chanid].get(block=True)
            _logger.debug(f"Channel {channel.chanid}, executing {command}")
            command_result = self._command_handler(command.decode())
            channel.sendall(command_result.stdout)
            channel.sendall_stderr(command_result.stderr)
            channel.send_exit_status(command_result.returncode)
        except Exception:  # pylint: disable=broad-except
            _logger.exception(f"Error handling client (channel: {channel})")
        finally:
            try:
                channel.close()
            except EOFError:
                _logger.debug("Tried to close already closed channel")

    def check_auth_publickey(self, username: str, key: paramiko.PKey) -> int:
        return paramiko.AUTH_SUCCESSFUL

    def check_auth_password(self, username: str, password: str) -> int:
        return paramiko.AUTH_SUCCESSFUL

    def check_channel_exec_request(
        self, channel: paramiko.Channel, command: bytes
    ) -> bool:
        self.command_queues.setdefault(channel.get_id(), Queue()).put(command)
        return True

    def check_channel_request(self, kind: str, chanid: ChannelID) -> int:
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def get_allowed_auths(self, username: str) -> str:
        return "password,publickey"
