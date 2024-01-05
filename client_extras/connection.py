from shared.extras.double_command import double_commands
import socket

# We must initialize the commands to add them to the collection of commands
import shared.double_commands as _

del _


class Connection:
    def __init__(self, remote_ip: str, remote_port: int) -> None:
        self.__sock = socket.socket()
        self.__sock.setblocking(True)
        self.__sock.settimeout(5)
        self.__sock.connect((remote_ip, remote_port))

    def connect(self, ip: str, port: int) -> None:
        try:
            self.__sock.connect((ip, port))
        except OSError:
            print("Failed to connect, retrying...")
            self.connect(ip, port)

    def recieve_command(self) -> None:
        try:
            cmd_name_buf = self.__sock.recv(64)
            try:
                decoded_buffer = cmd_name_buf.decode("ascii")
            except UnicodeDecodeError:
                decoded_buffer = ""
        except TimeoutError:
            return

        if len(cmd_name_buf) == 0:
            raise ConnectionResetError(
                "closing connection as we recieved 0 bytes on a blocking socket"
            )

        if decoded_buffer == "ping":
            try:
                self.__sock.sendall("pong".encode("ascii"))
            except OSError:
                pass
            return

        if decoded_buffer not in double_commands:
            try:
                self.__sock.sendall("notfound".encode("ascii"))
            except OSError:
                pass
            return
        else:
            try:
                self.__sock.sendall("running".encode("ascii"))
            except OSError:
                pass

        print(f"Calling command '{decoded_buffer}'")
        self.__call_func(decoded_buffer)
        print(f"Called command '{decoded_buffer}'")

    def __call_func(self, func_name: str) -> None:
        try:
            double_commands[func_name].command.client_side(self.__sock)
        except Exception as err:
            print(f"{err.__class__} thrown: {err}")

    @property
    def socket(self) -> socket.socket:
        return self.__sock
