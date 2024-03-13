from typing import Iterable, Any
import enum

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shared.extras.double_command import DoubleCommandResult, ArgumentType
    from server_extras.local_command import LocalCommandResult


class ExecuteCommandResult(enum.Enum):
    success = 0
    semi_success = 1
    failure = 2
    max_retries_hit = 3
    not_found = 4


type AnyCommandResult = ExecuteCommandResult | DoubleCommandResult | LocalCommandResult
MAX_COMMAND_NAME_LENGTH: int = 32


class CommandResult:
    def __init__(
        self,
        status: AnyCommandResult,
        ret_value: Any = None,
    ) -> None:
        self.__status: AnyCommandResult = status
        self.__ret_value = ret_value

    def set_status(self, new_status: AnyCommandResult) -> None:
        self.__status: AnyCommandResult = new_status  # type: ignore

    def set_ret_value(self, new_ret_value: Any) -> None:
        self.__ret_value = new_ret_value

    @property
    def status(
        self,
    ) -> AnyCommandResult:
        return self.__status

    @property
    def ret_value(self) -> Any:
        return self.__ret_value


def get_min_args(arg_types: Iterable["ArgumentType"]) -> int:
    return sum([1 for arg_type in arg_types if not arg_type.is_optional])


def get_max_args(arg_types: Iterable["ArgumentType"]) -> int:
    return len(list(arg_types))
