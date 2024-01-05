from typing import TextIO
import sys
import io


class StdoutStringIO(io.StringIO):
    def __init__(self, target_stdout: TextIO, initial_value: str = "") -> None:
        super().__init__(initial_value)
        self.__target_stdout = target_stdout

    def write(self, __s: str) -> int:
        self.__target_stdout.write(__s)
        return super().write(__s)


class CustomStdout:
    def __init__(self) -> None:
        self.__old_stdout = sys.stdout
        self.__stdout = StdoutStringIO(self.__old_stdout)
        sys.stdout = self.__stdout
        self.__destroyed = False

    def clear_screen(self) -> None:
        self.__check_destroyed()
        self.__stdout.write("\033[F\033[K" * 1000)

    def push_line_print(self, string: str) -> None:
        self.__check_destroyed()
        old_line = self.lines[-1]
        print("\r", end="", file=self.__stdout)
        print(" " * len(self.lines[-1]), end="", file=self.__stdout)
        print("\r", end="", file=self.__stdout)
        print(string, file=self.__stdout)
        print(old_line, end="", file=self.__stdout)
        self.__stdout.flush()

    def destroy(self) -> None:
        sys.stdout = self.__old_stdout
        self.__destroyed = True

    @property
    def contents(self) -> str:
        self.__check_destroyed()
        return self.__stdout.getvalue()

    @property
    def lines(self, keep_ends: bool = False) -> list[str]:
        self.__check_destroyed()
        return self.__stdout.getvalue().splitlines(keepends=keep_ends)

    def __check_destroyed(self) -> None:
        if self.__destroyed:
            raise Exception("you have already destroyed this CustomStdout object")
