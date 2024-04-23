from __future__ import annotations

from shared.extras.command import (
    MAX_COMMAND_NAME_LENGTH,
    CommandResult,
    get_max_args,
    get_min_args,
)
from shared.extras.encrypted_socket import EncryptedSocket

from typing import Iterable, Callable, Literal, Generic, TypeVar
import struct
import socket
import enum
import abc

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server_extras.client import Client


class ArgumentType(enum.Enum):
    integer = 0
    float = 1
    string = 2

    optional_integer = 3
    optional_float = 4
    optional_string = 5

    @property
    def is_optional(self) -> bool:
        return self.name.startswith("optional")

    @property
    def is_string(self) -> bool:
        return self.name.endswith("string")

    @property
    def is_integer(self) -> bool:
        return self.name.endswith("integer")

    @property
    def is_float(self) -> bool:
        return self.name.endswith("float")

    def __str__(self) -> str:
        if self.is_integer:
            return "integer"
        elif self.is_float:
            return "float"
        elif self.is_string:
            return "string"
        return "unknown"


class OSType(enum.Enum):
    linux = 0
    mac_os = 1
    ms_windows = 2

    @property
    def pretty(self) -> str:
        return OS_TYPE_TO_PRETTY_LOOKUP[self]


PLATFORM_TO_OS_TYPE_LOOKUP = {
    "linux": OSType.linux,
    "win32": OSType.ms_windows,
    "darwin": OSType.mac_os,
}


OS_TYPE_TO_PRETTY_LOOKUP = {
    OSType.linux: "Linux",
    OSType.ms_windows: "MS Windows",
    OSType.mac_os: "MacOS",
}


class DoubleCommandResult(enum.Enum):
    success = 0
    semi_success = 1
    failure = 2
    timeout = 3
    conn_error = 4
    param_error = 5


class DoubleCommand(abc.ABC):
    @staticmethod
    @abc.abstractmethod
    def client_side(sock: EncryptedSocket) -> None:
        """This method will be run on the client side, and should handle exceptions and timeouts by itself.

        You should import any neccesary modules from within this function.

        When defining this method you should use the `staticmethod` decorator.

        This method must take 1 parameter:
        sock: A `socket` object representing a connection to the server.

        You can safely assume that the given `sock` parameter is a valid `socket` object.
        """
        ...

    @staticmethod
    @abc.abstractmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        """This method will be run on the server side, and must handle exceptions, timeouts and invalid parameters by itself.\n
        This method should return a `CommandResult` instance.\n
        If this method fails, it should print why before returning.

        You should import any neccesary modules from within this function.

        When defining this method you should use the `staticmethod` decorator.

        This method must take 2 arguments:
        client: A `Client` object representing the client (this includes things such as the socket and client name).
        params: A `tuple` object representing the parameters passed to the method by the caller (typically typed in by the user).

        You can safely assume that the given `client` argument is a valid `Client` object,
        and that the `params` argument is a valid `tuple` object containing `CommandToken` types.
        """
        ...


command_class_type = TypeVar("command_class_type", bound=type[DoubleCommand])


class InternalDoubleCommand(Generic[command_class_type]):
    def __init__(
        self,
        cmd: command_class_type,
        name: str,
        usage: str,
        description: str,
        argument_types: Iterable[ArgumentType],
        return_type: type = type[None],
        required_client_modules: Iterable[str] | None = None,
        required_server_modules: Iterable[str] | None = None,
        supported_os: list[OSType] | Literal["all"] = "all",
        max_selected: int = -1,
        no_multitask: bool = False,
        no_new_process: bool = False,
    ) -> None:
        self.__cmd = cmd
        self.__name = name
        self.__usage = usage
        self.__description = description
        self.__argument_types = argument_types
        self.__return_type = return_type
        self.__required_client_modules = required_client_modules or []
        self.__required_server_modules = required_server_modules or []
        self.__supported_os = list(OSType) if supported_os == "all" else supported_os
        self.__max_selected = max_selected
        self.__no_multitask = no_multitask
        self.__no_new_process = no_new_process

    @property
    def command(self) -> command_class_type:
        return self.__cmd

    @property
    def name(self) -> str:
        return self.__name

    @property
    def min_args(self) -> int:
        return get_min_args(self.argument_types)

    @property
    def max_args(self) -> int:
        return get_max_args(self.argument_types)

    @property
    def usage(self) -> str:
        return self.__usage

    @property
    def description(self) -> str:
        return self.__description

    @property
    def argument_types(self) -> Iterable[ArgumentType]:
        return self.__argument_types

    @property
    def return_type(self) -> type:
        return self.__return_type

    @property
    def required_client_modules(self) -> Iterable[str]:
        return self.__required_client_modules

    @property
    def required_server_modules(self) -> Iterable[str]:
        return self.__required_server_modules

    @property
    def supported_os(self) -> list[OSType]:
        return self.__supported_os

    @property
    def max_selected(self) -> int:
        return self.__max_selected

    @property
    def no_multitask(self) -> bool:
        return self.__no_multitask

    @property
    def no_new_process(self) -> bool:
        return self.__no_new_process


double_commands: dict[str, InternalDoubleCommand] = {}


def add_double_command[
    command_class_type
](
    name: str,
    usage: str,
    description: str,
    argument_types: Iterable[ArgumentType],
    return_type: type = type[None],
    required_client_modules: Iterable[str] | None = None,
    required_server_modules: Iterable[str] | None = None,
    supported_os: list[OSType] | Literal["all"] = "all",
    max_selected: int = -1,
    no_multitask: bool = False,
    no_new_process: bool = False,
) -> Callable[[command_class_type], command_class_type]:
    def decorator(cls: command_class_type) -> command_class_type:
        from server_extras.local_command import local_commands

        if no_new_process and not no_multitask:
            raise ValueError(
                "if no_new_process is True, no_multitask must also be True"
            )
        if len(name) > MAX_COMMAND_NAME_LENGTH:
            raise ValueError(
                f"name must be less than or equal to {MAX_COMMAND_NAME_LENGTH} characters"
            )
        if len(name) == 0:
            raise ValueError("name must have at least 1 character")
        prev_arg_optional = False
        for arg_type in argument_types:
            if not arg_type.is_optional and prev_arg_optional:
                raise ValueError("optional arguments must after required arguments")
            prev_arg_optional = arg_type.is_optional
        if name in double_commands or name in local_commands:
            raise ValueError(f"command name '{name}' already used")
        double_commands[name] = InternalDoubleCommand(
            cls,
            name,
            usage,
            description,
            argument_types,
            return_type,
            required_client_modules,
            required_server_modules,
            supported_os,
            max_selected,
            no_multitask,
            no_new_process,
        )
        return cls

    return decorator


def send_item(sock: socket.socket, item: str | int | float) -> None:
    if isinstance(item, str):
        send_string(sock, item)
    if isinstance(item, int):
        send_integer(sock, item)
    if isinstance(item, float):
        send_float(sock, item)
    if isinstance(item, bytes):
        send_bytes(sock, item)


def send_string(sock: socket.socket, string: str) -> None:
    bytes_string = string.encode()
    sock.sendall(len(bytes_string).to_bytes(8))
    sock.sendall(bytes_string)


def send_bytes(sock: socket.socket, bytes: bytes) -> None:
    sock.sendall(len(bytes).to_bytes(8))
    sock.sendall(bytes)


def send_integer(sock: socket.socket, integer: int) -> None:
    sock.sendall(integer.to_bytes(8, signed=True))


def send_float(sock: socket.socket, float: float) -> None:
    sock.sendall(struct.pack("d", float))


def send_boolean(sock: socket.socket, boolean: bool) -> None:
    if boolean:
        sock.sendall(b"\xFF")
    else:
        sock.sendall(b"\x00")


def recieve_string(sock: socket.socket, ignore_unicode_errors: bool = False) -> str:
    return recieve_bytes(sock).decode(
        errors="ignore" if ignore_unicode_errors else "strict"
    )


def recieve_bytes(sock: socket.socket) -> bytes:
    return sock.recv(int.from_bytes(sock.recv(8)))


def recieve_integer(sock: socket.socket) -> int:
    return int.from_bytes(sock.recv(8), signed=True)


def recieve_float(sock: socket.socket) -> float:
    return struct.unpack("d", sock.recv(8))[0]


def recieve_boolean(sock: socket.socket) -> bool:
    return sock.recv(1) == b"\xFF"


def recieve_maximum_bytes(sock: socket.socket, chunk_size: int = 1024) -> bytes:
    temp_bytes = sock.recv(chunk_size)
    contents = bytearray(temp_bytes)

    while len(temp_bytes) == chunk_size:
        temp_bytes = sock.recv(chunk_size)
        contents += temp_bytes

    return bytes(contents)


def recieve_last_bytes(sock: socket.socket, bytes_amount: int) -> bytes:
    return recieve_maximum_bytes(sock)[-bytes_amount:]
