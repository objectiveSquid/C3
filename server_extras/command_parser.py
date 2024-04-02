from shared.extras.command import AnyInternalCommand

import enum


type CommandToken = str | int | float


class ValidateCommandResult(enum.Enum):
    valid = 0
    too_few_args = 1
    too_many_args = 2
    invalid_type = 3
    cant_parse = 4
    no_tokens = 5


class ParsedCommand:
    def __init__(
        self,
        tokens: list[CommandToken] | None = None,
        validity: ValidateCommandResult | None = None,
    ) -> None:
        self.__tokens = [] if tokens == None else tokens
        self.__validity = validity

    def validate(self, command: AnyInternalCommand) -> ValidateCommandResult:
        if isinstance(self.__validity, ValidateCommandResult):
            return self.__validity

        if len(self.parameters) < command.min_args:
            return ValidateCommandResult.too_few_args
        if len(self.parameters) > command.max_args:
            return ValidateCommandResult.too_many_args

        for given_param, expected_param_type in zip(
            self.parameters, command.argument_types
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
        try:
            return str(self.__tokens[0])
        except IndexError:
            return ""

    @property
    def parameters(self) -> list[CommandToken]:
        return self.__tokens[1:]

    @property
    def tokens(self) -> list[CommandToken]:
        return self.__tokens


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

    @staticmethod
    def try_parse_float(chars: str) -> tuple[str, float | None]:
        parser = CommandParser(chars)
        output = ""
        while (
            parser.has_more_chars
            and parser.peek().isdigit()
            or (parser.peek() in ".-" and len(parser.peek()) > 0)
        ):
            output += parser.consume()

        try:
            output = float(output)
        except ValueError:
            return chars, None

        return parser.rest, output

    @staticmethod
    def try_parse_integer(chars: str) -> tuple[str, int | None]:
        parser = CommandParser(chars)
        output = ""
        while parser.has_more_chars and parser.peek().isdigit() or parser.peek() == "-":
            output += parser.consume()

        try:
            output = int(output)
        except ValueError:
            return chars, None

        return parser.rest, output

    @staticmethod
    def try_parse_string(chars: str) -> tuple[str, str | None]:
        parser = CommandParser(chars)
        output = ""
        escaped = False
        start_char = parser.consume()
        if start_char not in "'\"":
            output += start_char

        while parser.has_more_chars and not (
            start_char not in "'\"" and parser.peek() == " "
        ):
            if escaped:
                output += parser.consume()
                escaped = False
                continue
            if parser.peek() == start_char and start_char in "'\"":
                parser.consume()
                break
            if parser.peek() == "\\":
                parser.consume()
                escaped = True
                continue
            output += parser.consume()

        return parser.rest, output

    @property
    def tokens(self) -> list[CommandToken]:
        return self.__tokens

    @property
    def has_more_chars(self) -> bool:
        return self.__progress < len(self.__command_line)

    @property
    def rest(self) -> str:
        return self.peek(len(self.__command_line) - self.__progress, through=True)

    @property
    def is_done(self) -> bool:
        return not self.has_more_chars

    @property
    def progress(self) -> int:
        return self.__progress


def parse_command(command_line: str, command: AnyInternalCommand) -> ParsedCommand:
    tokens = []
    first_token = True
    parser = CommandParser(command_line)

    while parser.has_more_chars:
        if parser.peek().isspace():
            parser.consume()
            continue

        integer_rest, integer_arg = CommandParser.try_parse_integer(parser.rest)
        float_rest, float_arg = CommandParser.try_parse_float(parser.rest)
        string_rest, string_arg = CommandParser.try_parse_string(parser.rest)

        if (float_arg, integer_arg, string_arg) == (None, None, None):
            return ParsedCommand(validity=ValidateCommandResult.cant_parse)

        if not first_token:
            current_target_type = list(command.argument_types)[len(tokens) - 1]

        if first_token:
            if not string_arg:
                return ParsedCommand(validity=ValidateCommandResult.invalid_type)
            parser = CommandParser(string_rest)
            tokens.append(string_arg)
            first_token = False
            continue

        if current_target_type.is_float:
            if float_arg == None:
                return ParsedCommand(validity=ValidateCommandResult.invalid_type)
            parser = CommandParser(float_rest)
            tokens.append(float_arg)
        if current_target_type.is_integer:
            if integer_arg == None:
                return ParsedCommand(validity=ValidateCommandResult.invalid_type)
            parser = CommandParser(integer_rest)
            tokens.append(integer_arg)
        if current_target_type.is_string:
            if string_arg == None:
                return ParsedCommand(validity=ValidateCommandResult.invalid_type)
            parser = CommandParser(string_rest)
            tokens.append(string_arg)

    parsed = ParsedCommand(tokens)
    return parsed
