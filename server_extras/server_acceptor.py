from server_extras.client import ClientBucket, Client

import threading
import socket
import time


class ServerAcceptorThread(threading.Thread):
    def __init__(self, server_socket: socket.socket, clients: ClientBucket) -> None:
        super().__init__(name="Server Acceptor")
        self.__sock = server_socket
        self.__clients = clients
        self.__running = True

    def run(self) -> None:
        while self.__running:
            try:
                client_socket, (client_ip, client_port) = self.__sock.accept()
            except OSError:
                time.sleep(0.1)
                continue
            self.__clients.add(Client(client_socket, client_ip, client_port))

    def stop(self) -> None:
        """Sets the private variable `__running` to `False`, which stops the accept loop."""
        self.__running = False

    @property
    def clients(self) -> ClientBucket:
        return self.__clients
