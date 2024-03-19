from server_extras.custom_io import StdoutCapturingProcess

from typing import Iterable, Any
import tempfile
import random
import pickle
import enum
import os

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shared.extras.double_command import (
        InternalDoubleCommand,
        DoubleCommandResult,
        ArgumentType,
    )
    from server_extras.local_command import InternalLocalCommand, LocalCommandResult


class ExecuteCommandResult(enum.Enum):
    success = 0
    semi_success = 1
    failure = 2
    max_retries_hit = 3
    not_found = 4


type AnyCommandResult = ExecuteCommandResult | DoubleCommandResult | LocalCommandResult
type AnyInternalCommand = InternalDoubleCommand | InternalLocalCommand
MAX_COMMAND_NAME_LENGTH: int = 32


# XXX: I will apologize for any brain damage invoked by this code. It was written at no other time than 4:45 AM on a Thursday.
# I could for the life of me not bother with those GOD DAMN 'multiprocessing.Queue' or whatever objects.
class CommandResult:
    def __init__(
        self,
        status: AnyCommandResult | None = None,
        ret_value: Any = None,
        process_handle: StdoutCapturingProcess | None = None,
    ) -> None:
        self.__status_file = (
            tempfile.gettempdir()
            + "/"
            + "".join(
                random.choices(
                    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890",
                    k=8,
                )
            )
            + ".pkl"
        )
        if status != None:
            self.set_status(status)
        self.__ret_value = ret_value
        self.__process_handle = process_handle

    def set_status(self, new_status: AnyCommandResult) -> None:
        with open(self.__status_file, "wb") as status_fd:
            pickle.dump(new_status, status_fd)

    def set_ret_value(self, new_ret_value: Any) -> None:
        self.__ret_value = new_ret_value

    def set_process_handle(self, process_handle: StdoutCapturingProcess) -> None:
        self.__process_handle = process_handle

    @property
    def status(
        self,
    ) -> AnyCommandResult | None:
        if not os.path.isfile(self.__status_file):
            return

        with open(self.__status_file, "rb") as status_fd:
            return pickle.load(status_fd)

    @property
    def ret_value(self) -> Any:
        return self.__ret_value

    @property
    def process_handle(self) -> StdoutCapturingProcess | None:
        return self.__process_handle


def get_min_args(arg_types: Iterable["ArgumentType"]) -> int:
    return sum([1 for arg_type in arg_types if not arg_type.is_optional])


def get_max_args(arg_types: Iterable["ArgumentType"]) -> int:
    return len(list(arg_types))
