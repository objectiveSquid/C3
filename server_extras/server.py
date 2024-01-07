from shared.extras.double_command import InternalDoubleCommand, double_commands
from server_extras.local_command import InternalLocalCommand, local_commands
from shared.extras.command import ExecuteCommandResult, CommandResult
from server_extras.server_acceptor import ServerAcceptorThread
from server_extras.command_parser import parse_command
from server_extras.client import ClientBucket, Client
from server_extras.custom_io import CustomStdout

from typing import Callable, Any
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
        self.__custom_stdout = CustomStdout()
        self.__clients = ClientBucket(self.__custom_stdout)
        self.__acceptor = ServerAcceptorThread(self.__socket, self.__clients)

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
            if len(command_line) == 0:
                continue
            cmd = parse_command(command_line)
            if cmd.is_invalid:
                print("Invalid command supplied.")
                continue
            command_name = cmd.command_name
            command = double_commands.get(command_name) or local_commands.get(
                command_name
            )
            if command == None:
                print(f"Command '{command_name}' doesn't exist.")
                continue
            if len(cmd.parameters) < command.min_args:
                print(f"Not enough arguments, need at least {command.min_args}.")
                continue
            if len(cmd.parameters) > command.max_args:
                print(f"Too many arguments, need at most {command.max_args}.")
                continue

            invalid_param = False
            for given_param, expected_param_type in zip(
                cmd.parameters, command.argument_types
            ):
                if isinstance(given_param, str) and not expected_param_type.is_string:
                    print(
                        f"Argument '{given_param}' of type string should be: {expected_param_type}"
                    )
                    invalid_param = True
                elif (
                    isinstance(given_param, int) and not expected_param_type.is_integer
                ):
                    print(
                        f"Argument '{given_param}' of type integer should be: {expected_param_type}"
                    )
                    invalid_param = True
                elif (
                    isinstance(given_param, float) and not expected_param_type.is_float
                ):
                    print(
                        f"Argument '{given_param}' of type float should be: {expected_param_type}"
                    )
                    invalid_param = True
            if invalid_param:
                continue

            if isinstance(command, InternalDoubleCommand):
                command_results: dict[str, CommandResult] = {}
                selected_clients = self.__clients.get_selected_clients()
                alive_clients = self.__clients.get_alive_clients()
                if len(selected_clients) == 0:
                    print(
                        f"No selected clients, you can select a client with `select [client_name]`"
                    )
                    continue
                if (
                    command.max_selected < len(self.clients.get_selected_clients())
                    and command.max_selected > 0
                ):
                    print(
                        f"You must have at most {command.max_selected} selected clients to run this command."
                    )
                tasks: list[
                    tuple[str, multiprocessing.Queue, multiprocessing.Process]
                ] = []
                for selected_client in selected_clients:
                    if selected_client not in alive_clients:
                        print(
                            f"Client '{selected_client.name}' is dead, skipping.",
                            flush=True,
                        )
                        continue
                    stdout_queue = multiprocessing.Queue()
                    proc = multiprocessing.Process(
                        target=capture_stdout_wrapper,
                        args=(
                            stdout_queue,
                            Client.execute_command,
                            selected_client,
                            command,
                            cmd.parameters,
                        ),
                    )

                    proc.start()
                    tasks.append((selected_client.name, stdout_queue, proc))
                    if command.no_multitask:
                        proc.join()

                for client_name, queue, task in tasks:
                    task.join()
                    stdout_cap, command_result = queue.get()
                    print(
                        f"Completed execution of command on client '{client_name}' (status: ",
                        flush=True,
                        end="",
                    )
                    match command_result.status:
                        case ExecuteCommandResult.success:
                            print(colorama.Fore.LIGHTGREEN_EX, end="")
                        case ExecuteCommandResult.semi_success:
                            print(colorama.Fore.YELLOW, end="")
                        case _:
                            print(colorama.Fore.RED, end="")
                    print(
                        f"{command_result.status.name}{colorama.Fore.RESET}):",
                        flush=True,
                    )
                    print(stdout_cap, end="", flush=True)
                    command_results[client_name] = command_result
            elif isinstance(command, InternalLocalCommand):
                command.command.local_side(self, tuple(cmd.parameters))

        self.__custom_stdout.destroy()
        self.__acceptor.stop()
        self.__clients.remove_all_clients()
        self.__socket.close()

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
