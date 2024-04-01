from server_extras.command_parser import (
    ValidateCommandResult,
    CommandParser,
    ParsedCommand,
    parse_command,
)
from shared.extras.double_command import InternalDoubleCommand, double_commands
from server_extras.local_command import InternalLocalCommand, local_commands
from server_extras.custom_io import StdoutCapturingProcess, CustomStdout
from shared.extras.command import ExecuteCommandResult, CommandResult
from server_extras.server_acceptor import ServerAcceptorThread
from server_extras.client import ClientBucket, Client

from typing import Callable, Literal, Any
import multiprocessing
import threading
import colorama
import socket

# We must initialize the commands to add them to the collection of commands
import server_extras.local_commands as _
import shared.double_commands as _

del _


def capture_stdout_wrapper(
    output_queue: multiprocessing.Queue,
    func: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> None:
    import sys
    import io

    stdout_capture = io.StringIO()
    sys.stdout = stdout_capture
    sys.stderr = stdout_capture

    command_result = func(*args, **kwargs)

    output_queue.put((stdout_capture.getvalue(), command_result))


class ServerThread(threading.Thread):
    def __init__(self, ip: str, port: int) -> None:
        super().__init__()
        self.__ip = ip
        self.__port = port

        self.__running = True
        self.__socket = socket.socket()
        self.__socket.setblocking(True)
        self.__socket.settimeout(5)
        self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.__custom_stdout = CustomStdout()
        self.__clients = ClientBucket(self.__custom_stdout)
        self.__acceptor = ServerAcceptorThread(
            self.__socket, self.__clients, self.__custom_stdout
        )

    def run(self) -> None:
        self.__bind_sock()
        self.__listen_sock()
        self.__start_acceptor()

        while self.__running:
            try:
                command_line = input("> ")
            except EOFError:
                print("\n", end="")
                exit_cmd = local_commands.get("exit")
                if exit_cmd == None:
                    print("Exit command not found!")
                    continue
                exit_cmd.command.local_side(self, ())
                continue
            if len(command_line.strip()) == 0:
                continue

            remainder, command_name = CommandParser.try_parse_string(command_line)
            if command_name == None:
                print("Invalid command name.")
                continue
            command = double_commands.get(command_name) or local_commands.get(
                command_name
            )
            if command == None:
                print(f"Command '{command_name}' doesn't exist.")
                continue
            cmdline = parse_command(command_line, command)

            match cmdline.validate(command):
                case ValidateCommandResult.no_tokens | ValidateCommandResult.cant_parse:
                    print("Could not parse command.")
                    continue
                case ValidateCommandResult.invalid_type:
                    print("Invalid argument type supplied.")
                    continue
                case ValidateCommandResult.too_few_args:
                    print(
                        f"Not enough arguments supplied, use {command.min_args} argument(s) at least."
                    )
                    continue
                case ValidateCommandResult.too_many_args:
                    print(
                        f"Too many arguments supplied, use {command.max_args} argument(s) at most."
                    )
                    continue

            if isinstance(command, InternalDoubleCommand):
                command_outputs: dict[str, CommandResult] = {}
                self.__prepare_and_start_double_command(
                    command.name, cmdline, command_outputs
                )

                old_stdout = self.__custom_stdout.contents
                while any(
                    [output.status == None for output in command_outputs.values()]
                ):
                    self.__custom_stdout.clear_lines()
                    print(old_stdout, end="")
                    for client_name, output in command_outputs.items():
                        if output.status == None:
                            print(f"Executing command on client '{client_name}'")
                        else:
                            print(
                                f"Completed execution of command on client '{client_name}' (status: ",
                                end="",
                            )
                            match output.status:
                                case ExecuteCommandResult.success:
                                    print(colorama.Fore.LIGHTGREEN_EX, end="")
                                case ExecuteCommandResult.semi_success:
                                    print(colorama.Fore.YELLOW, end="")
                                case _:
                                    print(colorama.Fore.RED, end="")
                            print(f"{output.status.name}{colorama.Fore.RESET}):")
                        print(output.process_handle.stdout, end="", flush=True)  # type: ignore

            elif isinstance(command, InternalLocalCommand):
                command.command.local_side(self, tuple(cmdline.parameters))

        self.__custom_stdout.destroy()
        self.__acceptor.stop()
        self.__clients.remove_all_clients()
        self.__socket.close()

    def __prepare_and_start_double_command(
        self,
        command_name: str,
        arguments: ParsedCommand,
        outputs: dict[str, CommandResult],
    ) -> tuple[
        Literal["no_clients", "too_many_clients", "command_not_found", "started"],
        list[str],
    ]:
        try:
            command = double_commands[command_name]
        except KeyError:
            return "command_not_found", []

        selected_clients = self.__clients.get_selected_clients()
        alive_clients = self.__clients.get_alive_clients()

        if len(selected_clients) == 0:
            print(
                f"No selected clients, you can select a client with `select [client_name]`"
            )
            return "no_clients", []
        if command.max_selected < len(selected_clients) and command.max_selected > 0:
            print(
                f"You must have at most {command.max_selected} selected clients to run this command."
            )
            return "too_many_clients", []

        skipped_clients = self.__start_double_command(
            arguments, command, selected_clients, alive_clients, outputs
        )
        return "started", skipped_clients

    @staticmethod
    def __start_double_command(
        cmdline_args: ParsedCommand,
        command: InternalDoubleCommand,
        selected_clients: list[Client],
        alive_clients: list[Client],
        outputs: dict[str, CommandResult],
    ) -> list[str]:
        skipped_clients = []
        for selected_client in selected_clients:
            if selected_client not in alive_clients:
                print(f"Client '{selected_client.name}' is dead, skipping.", flush=True)
            if selected_client.os_type not in command.supported_os:
                print(
                    f"Client '{selected_client.name}'s OS type isn't supported by the command, skipping."
                )
                skipped_clients.append(selected_client.name)
                continue
            command_output = CommandResult()

            outputs[selected_client.name] = command_output
            proc = StdoutCapturingProcess(
                target=Client.execute_command,
                args=[
                    selected_client,
                    command,
                    cmdline_args.parameters,
                    command_output,
                ],
            )

            proc.start()
            outputs[selected_client.name].set_process_handle(proc)

        return skipped_clients

    def stop(self) -> None:
        self.__running = False

    def __bind_sock(self) -> None:
        self.__socket.bind((self.__ip, self.__port))

    def __listen_sock(self) -> None:
        self.__socket.listen()

    def __start_acceptor(self) -> None:
        self.__acceptor.start()

    @property
    def custom_stdout(self) -> CustomStdout:
        return self.__custom_stdout

    @property
    def socket(self) -> socket.socket:
        return self.__socket

    @property
    def clients(self) -> ClientBucket:
        return self.__clients

    @property
    def acceptor(self) -> ServerAcceptorThread:
        return self.__acceptor

    @property
    def ip(self) -> str:
        return self.__ip

    @property
    def port(self) -> int:
        return self.__port
