from typing import Iterable, Callable, Mapping, TextIO, Any
import multiprocessing
import queue
import sys
import io


class StdoutStringIO(io.StringIO):
    def __init__(self, target_stdout: TextIO, initial_value: str = "") -> None:
        super().__init__(initial_value)
        self.__target_stdout = target_stdout

    def write(self, __s: str) -> int:
        self.__target_stdout.write(__s)
        self.__target_stdout.flush()
        return super().write(__s)


class CustomStdout:
    def __init__(self) -> None:
        self.__old_stdout = sys.stdout
        self.__stdout = StdoutStringIO(self.__old_stdout)
        sys.stdout = self.__stdout
        self.__destroyed = False

    def clear_lines(self, count: int = 1000) -> None:
        self.__check_destroyed()
        self.__stdout.write("\033[F\033[K" * count)

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


class QueueWriter:
    def __init__(self, queue: multiprocessing.Queue) -> None:
        self.__queue = queue

    def write(self, __s: str) -> None:
        self.__queue.put(__s)


class StdoutCapturingProcess(multiprocessing.Process):
    def __init__(
        self,
        group: None = None,
        target: Callable[..., Any] | None = None,
        name: str | None = None,
        args: Iterable[Any] | None = None,
        kwargs: Mapping[str, Any] | None = None,
        *,
        daemon: bool | None = None
    ) -> None:
        self.__args = args if args != None else ()
        self.__kwargs = kwargs if kwargs != None else {}

        super().__init__(
            group=group,
            target=target,
            name=name,
            args=self.__args,
            kwargs=self.__kwargs,
            daemon=daemon,
        )
        self.__queue = multiprocessing.Queue()
        self.__capture = ""

    def run(self) -> None:
        sys.stdout = QueueWriter(self.__queue)

        err = None
        try:
            super().run()
        except BaseException as exception:
            err = exception

        sys.stdout = sys.__stdout__

        if err != None:
            raise err

    @property
    def stdout(self) -> str:
        while True:
            try:
                message = self.__queue.get_nowait()
                self.__capture += message
            except queue.Empty:
                break
        return self.__capture
