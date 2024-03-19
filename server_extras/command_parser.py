from shared.extras.command import AnyInternalCommand

import shlex
import enum


type CommandToken = str | int | float


class ValidateCommandResult(enum.Enum):
    valid = 0
    too_few_args = 1
    too_many_args = 2
    invalid_type = 3


class ParsedCommand:
    def __init__(self, tokens: list[CommandToken] = [], invalid: bool = False) -> None:
        self.__invalid = invalid
        self.__tokens = tokens

        # no tokens
        if len(self.__tokens) == 0:
            self.__invalid = True
            return
        # command name invalid
        if not isinstance(self.__tokens[0], str) or len(self.__tokens[0]) == 0:
            self.__invalid = True

    def validate(self, command: AnyInternalCommand) -> ValidateCommandResult:
        if len(self.__tokens) < command.min_args:
            return ValidateCommandResult.too_few_args
        if len(self.__tokens) > command.max_args:
            return ValidateCommandResult.too_many_args

        for given_param, expected_param_type in zip(
            self.__tokens, command.argument_types
        ):
            if isinstance(given_param, str) and not expected_param_type.is_string:
                return ValidateCommandResult.invalid_type
            elif isinstance(given_param, int) and not expected_param_type.is_integer:
                return ValidateCommandResult.invalid_type
            elif isinstance(given_param, float) and not expected_param_type.is_float:
                return ValidateCommandResult.invalid_type

        return ValidateCommandResult.valid

    @property
    def command_name(self) -> str:
        if self.__invalid:
            return ""
        return str(self.__tokens[0])

    @property
    def parameters(self) -> list[CommandToken]:
        return self.__tokens[1:]

    @property
    def tokens(self) -> list[CommandToken]:
        return self.__tokens

    @property
    def is_valid(self) -> bool:
        return not self.__invalid

    @property
    def is_invalid(self) -> bool:
        return self.__invalid


class CommandParser:
    def __init__(self, command_line: str) -> None:
        self.__command_line = list(command_line)
        self.__tokens = []
        self.__progress = 0

    def consume(self, num: int = 1) -> str:
        txt = self.peek(num, through=True)
        self.__progress += len(txt)
        return txt

    def peek(self, num: int = 1, *, through: bool = False) -> str:
        if len(self.__command_line) - self.__progress < num:
            return ""
        if not through:
            return self.__command_line[(num - 1) + self.__progress]
        out = ""
        for i in range(num):
            out += self.__command_line[i + self.__progress]
        return out

    def add_token(self, token: CommandToken) -> None:
        self.__tokens.append(token)

    @property
    def tokens(self) -> list[CommandToken]:
        return self.__tokens

    @property
    def has_more_chars(self) -> bool:
        return self.__progress < len(self.__command_line)

    @property
    def is_done(self) -> bool:
        return not self.has_more_chars

    @property
    def progress(self) -> int:
        return self.__progress


def parse_command(command_line: str) -> ParsedCommand:
    tokens = []
    items = shlex.split(command_line, posix=True)
    for item in items:
        if item.isdecimal():
            tokens.append(int(item))
            continue
        try:
            float(item)
            tokens.append(float(item))
        except ValueError:
            tokens.append(item)
    escaped_tokens = []
    for token in tokens:
        if not isinstance(token, str):
            escaped_tokens.append(token)
            continue
        try:
            if "'" in token:
                escaped_tokens.append(eval(f'"{token}"'))
            elif '"' in token:
                escaped_tokens.append(eval(f"'{token}'"))
            else:
                escaped_tokens.append(token)
        except SyntaxError:
            return ParsedCommand(invalid=True)
    return ParsedCommand(escaped_tokens)
