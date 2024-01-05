from shared.extras.command import (
    MAX_COMMAND_NAME_LENGTH,
    CommandResult,
    get_max_args,
    get_min_args,
)

from typing import Iterable, Callable
import socket
import enum
import abc

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server_extras.client import Client


type EmptyReturn = None


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
    def client_side(sock: socket.socket) -> None:
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
    def server_side(client: "Client", params: tuple) -> CommandResult:
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


class InternalDoubleCommand:
    def __init__(
        self,
        cmd: type[DoubleCommand],
        name: str,
        usage: str,
        description: str,
        argument_types: Iterable[ArgumentType],
        return_type: type,
        required_client_modules: Iterable[str] | None = None,
        required_server_modules: Iterable[str] | None = None,
        max_selected: int = -1,
        no_multitask: bool = False,
    ) -> None:
        self.__cmd = cmd
        self.__name = name
        self.__usage = usage
        self.__description = description
        self.__argument_types = argument_types
        self.__return_type = return_type
        self.__required_client_modules = required_client_modules or []
        self.__required_server_modules = required_server_modules or []
        self.__max_selected = max_selected
        self.__no_multitask = no_multitask

    @property
    def command(self) -> type[DoubleCommand]:
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
    def max_selected(self) -> int:
        return self.__max_selected

    @property
    def no_multitask(self) -> bool:
        return self.__no_multitask


double_commands: dict[str, InternalDoubleCommand] = {}


def add_double_command(
    name: str,
    usage: str,
    description: str,
    argument_types: Iterable[ArgumentType],
    return_type: type,
    required_client_modules: Iterable[str] | None = None,
    required_server_modules: Iterable[str] | None = None,
    max_selected: int = -1,
    no_multitask: bool = False,
) -> Callable[[type[DoubleCommand]], type[DoubleCommand]]:
    def decorator(cls: type[DoubleCommand]) -> type[DoubleCommand]:
        from server_extras.local_command import local_commands

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
            max_selected,
            no_multitask,
        )
        return cls

    return decorator
