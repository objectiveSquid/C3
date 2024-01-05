type CommandToken = str | int | float


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

    def consume(self, num: int = 1) -> str:
        if len(self.__command_line) < num:
            return ""
        out = ""
        for _ in range(num):
            out += self.__command_line.pop(0)
        return out

    def peek(self, num: int = 1, through: bool = False) -> str:
        if len(self.__command_line) < num:
            return ""
        if not through:
            return self.__command_line[num - 1]
        out = ""
        for i in range(num):
            out += self.__command_line[i]
        return out

    def add_token(self, token: CommandToken) -> None:
        self.__tokens.append(token)

    @property
    def tokens(self) -> list[CommandToken]:
        return self.__tokens

    @property
    def has_more_chars(self) -> bool:
        return len(self.__command_line) > 0

    @property
    def is_done(self) -> bool:
        return not self.has_more_chars


def parse_command(command_line: str) -> ParsedCommand:
    parser = CommandParser(command_line)
    while parser.has_more_chars:
        if parser.peek() == " ":
            parser.consume()
            continue
        elif parser.peek() == ".":
            is_string = False
            float_as_string = ""
            while parser.peek().isalnum():
                float_as_string += parser.consume()
                if not parser.peek().isdecimal():
                    is_string = True
            parser.consume()
            if is_string or len(float_as_string) == 0:
                parser.add_token(float_as_string)
                continue
            parser.add_token(float(float_as_string))
        elif parser.peek().isdecimal():
            num_as_string = ""
            is_string = False
            got_dot = False
            while parser.peek().isalnum() or parser.peek() == ".":
                if is_string:
                    num_as_string += parser.consume()
                    continue
                if parser.peek().isdecimal() or parser.peek() == ".":
                    if parser.peek() == ".":
                        if got_dot:
                            print("Invalid number in arguments.")
                            return ParsedCommand(invalid=True)
                        got_dot = True
                    num_as_string += parser.consume()
                else:
                    is_string = True
                    num_as_string += parser.consume()
            parser.consume()
            if is_string:
                parser.add_token(num_as_string)
                continue
            if got_dot and num_as_string[-1] == ".":
                print("Invalid number in arguments.")
                return ParsedCommand(invalid=True)
            if got_dot:
                parser.add_token(float(num_as_string))
            else:
                parser.add_token(int(num_as_string))
        elif parser.peek() in "\"'":
            string = ""
            string_starter = parser.consume()
            while parser.peek() != string_starter:
                string += parser.consume()
            parser.consume()
            parser.add_token(string)
        elif parser.peek().isalnum():
            string = ""
            while parser.peek() != " " and len(parser.peek()) > 0:
                string += parser.consume()
            parser.add_token(string)
        else:
            return ParsedCommand(invalid=True)
    return ParsedCommand(parser.tokens)
