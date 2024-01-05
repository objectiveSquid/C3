from shared.extras.double_command import CommandResult, ArgumentType
from shared.extras.command import MAX_COMMAND_NAME_LENGTH

from typing import Iterable, Callable
import enum
import abc

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server_extras.server import ServerThread


class LocalCommandResult(enum.Enum):
    success = 0
    failure = 1
    param_error = 2


class LocalCommand(abc.ABC):
    @staticmethod
    @abc.abstractmethod
    def local_side(server_thread: "ServerThread", params: tuple) -> CommandResult:
        """
        This method will be run on the server side, and must handle exceptions, timeouts and invalid parameters by itself.\n
        This method should return a `CommandResult` instance.\n
        If this method fails, it should print why before returning.

        When defining this method you should use the `staticmethod` decorator.

        This method must take 2 arguments:
        server_thread: The server thread, it's here you access all the things you want to use.
        params: A `tuple` object representing the parameters passed to the method by the caller (typically typed in by the user).

        You can safely assume that the given `server_thread` argument is a valid `ServerThread` object,
        and that the `params` argument is a valid `tuple` object containing `CommandToken` types.
        """
        ...


class InternalLocalCommand:
    def __init__(
        self,
        cmd: type[LocalCommand],
        name: str,
        usage: str,
        description: str,
        min_args: int,
        max_args: int,
        argument_types: Iterable[ArgumentType],
    ) -> None:
        self.__cmd = cmd
        self.__name = name
        self.__usage = usage
        self.__description = description
        self.__min_args = min_args
        self.__max_args = max_args
        self.__argument_types = argument_types

    @property
    def command(self) -> type[LocalCommand]:
        return self.__cmd

    @property
    def name(self) -> str:
        return self.__name

    @property
    def usage(self) -> str:
        return self.__usage

    @property
    def description(self) -> str:
        return self.__description

    @property
    def min_args(self) -> int:
        return self.__min_args

    @property
    def max_args(self) -> int:
        return self.__max_args

    @property
    def argument_types(self) -> Iterable[ArgumentType]:
        return self.__argument_types


local_commands: dict[str, InternalLocalCommand] = {}


def add_local_command(
    name: str,
    usage: str,
    description: str,
    min_args: int,
    max_args: int,
    argument_types: Iterable[ArgumentType],
) -> Callable[[type[LocalCommand]], type[LocalCommand]]:
    def decorator(cls: type[LocalCommand]) -> type[LocalCommand]:
        from shared.extras.double_command import double_commands

        if len(name) > MAX_COMMAND_NAME_LENGTH:
            raise ValueError(
                f"name must be less than or equal to {MAX_COMMAND_NAME_LENGTH} characters"
            )
        if min_args > max_args:
            raise ValueError("min_args, must be smaller or equal to max_args")
        prev_arg_optional = False
        for arg_type in argument_types:
            if not arg_type.is_optional and prev_arg_optional:
                raise ValueError("optional arguments must after required arguments")
            prev_arg_optional = arg_type.is_optional
        if name in double_commands or name in local_commands:
            raise ValueError(f"command name '{name}' already used")
        local_commands[name] = InternalLocalCommand(
            cls,
            name,
            usage,
            description,
            min_args,
            max_args,
            argument_types,
        )
        return cls

    return decorator
