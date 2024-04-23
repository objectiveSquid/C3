from shared.extras.encrypted_socket import EncryptedSocket
from shared.extras.double_command import (
    PLATFORM_TO_OS_TYPE_LOOKUP,
    double_commands,
    recieve_string,
    send_boolean,
    send_integer,
    send_string,
)

import time
import sys

# We must initialize the commands to add them to the collection of commands
import shared.double_commands as _

del _


class Connection:
    def __init__(
        self, remote_ip: str, remote_port: int, name: str | None = None
    ) -> None:
        self.__sock = EncryptedSocket()
        self.__sock.setblocking(True)
        self.__sock.settimeout(5)
        self.connect(remote_ip, remote_port, name)

    def connect(self, ip: str, port: int, name: str | None = None) -> None:
        try:
            self.__sock.connect((ip, port))
        except OSError:
            print("Failed to connect, retrying...")
            time.sleep(0.1)
            self.connect(ip, port, name)
            return

        try:
            self.__sock.initialize_encryption()
        except OSError:
            print("Connected to server but failed to initialize encryption")
            self.connect(ip, port, name)
            return

        if isinstance(name, str):
            send_boolean(self.__sock, True)
            send_string(self.__sock, name)
        else:
            send_boolean(self.__sock, False)

        os_type = PLATFORM_TO_OS_TYPE_LOOKUP.get(sys.platform)
        if os_type == None:
            print(f"OS type not recognized ('{sys.platform}' not in lookup table)")
            return
        send_integer(self.__sock, os_type.value)

    def recieve_command(self) -> None:
        try:
            buffer = recieve_string(self.__sock)
        except TimeoutError:
            return

        if len(buffer) == 0:
            raise ConnectionResetError(
                "closing connection as we recieved 0 bytes on a blocking socket"
            )

        if buffer == "ping":
            try:
                self.__sock.sendall(b"pong")
            except OSError:
                pass
            return

        status_to_send = "running"
        if buffer not in double_commands:
            status_to_send = "notfound"

        try:
            send_string(self.__sock, status_to_send)
        except OSError:
            pass

        if status_to_send != "running":
            return

        print(f"Calling command '{buffer}'")
        self.__call_func(buffer)
        print(f"Called command '{buffer}'")

    def __call_func(self, func_name: str) -> None:
        try:
            double_commands[func_name].command.client_side(self.socket)
        except Exception as err:
            print(f"{err.__class__} thrown: {err}")

    @property
    def socket(self) -> EncryptedSocket:
        return self.__sock
