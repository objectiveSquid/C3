from shared.extras.double_command import (
    recieve_boolean,
    recieve_integer,
    recieve_string,
)
from shared.extras.encrypted_socket import EncryptedSocket
from server_extras.client import ClientBucket, Client
from shared.extras.custom_io import CustomStdout
from shared.extras.double_command import OSType

import threading
import time


class ServerAcceptorThread(threading.Thread):
    def __init__(
        self,
        server_socket: EncryptedSocket,
        clients: ClientBucket,
        custom_stdout: CustomStdout,
    ) -> None:
        super().__init__(name="Server Acceptor")
        self.__sock = server_socket
        self.__clients = clients
        self.__custom_stdout = custom_stdout
        self.__running = True

    def run(self) -> None:
        while self.__running:
            try:
                client_socket, (client_ip, client_port) = self.__sock.accept()
            except OSError:
                time.sleep(0.1)
                continue
            try:
                client_socket.initialize_encryption()
            except OSError:
                print(
                    f"Recieved connection from {client_ip}:{client_port} but failed to initialize encryption"
                )
                continue
            client_reconnect_name = None
            try:
                if recieve_boolean(client_socket):
                    client_reconnect_name = recieve_string(client_socket)
                client_os = OSType(recieve_integer(client_socket))
            except OSError:
                self.__custom_stdout.push_line_print(
                    f"Client from '{client_ip}:{client_port}' tried to connect but didn't send the necesarry information"
                )
                continue
            except ValueError:
                self.__custom_stdout.push_line_print(
                    f"Client from '{client_ip}:{client_port}' tried to connect but it sent an invalid os type"
                )
                continue
            client_socket.setblocking(True)
            client_socket.settimeout(5)
            self.__clients.add(
                Client(
                    client_socket,
                    client_ip,
                    client_port,
                    client_os,
                    client_reconnect_name,
                )
            )

    def stop(self) -> None:
        """Sets the private variable `__running` to `False`, which stops the accept loop."""
        self.__running = False

    @property
    def clients(self) -> ClientBucket:
        return self.__clients
