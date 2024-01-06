from shared.extras.double_command import InternalDoubleCommand, double_commands
from server_extras.local_command import InternalLocalCommand, local_commands
from shared.extras.command import ExecuteCommandResult, CommandResult
from server_extras.server_acceptor import ServerAcceptorThread
from server_extras.command_parser import parse_command
from server_extras.custom_io import CustomStdout
from server_extras.client import ClientBucket

import concurrent.futures as futures
from typing import Callable, Any
import contextlib
import threading
import colorama
import socket
import io

# We must initialize the commands to add them to the collection of commands
import server_extras.local_commands as _
import shared.double_commands as _

del _


class ServerThread(threading.Thread):
    def __init__(self, ip: str, port: int) -> None:
        super().__init__()
        self.__ip = ip
        self.__port = port

        self.__running = True
        self.__socket = socket.socket()
        self.__socket.setblocking(False)
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

            def capture_stdout_wrapper(
                func: Callable[..., Any], *args: Any, **kwargs: Any
            ) -> tuple[str, Any]:
                stdout_capture = io.StringIO()

                with contextlib.redirect_stdout(
                    stdout_capture
                ), contextlib.redirect_stderr(stdout_capture):
                    command_result = func(*args, **kwargs)

                return stdout_capture.getvalue(), command_result

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
                if not command.no_multitask:
                    tasks = []
                    with futures.ThreadPoolExecutor(len(selected_clients) or 1) as pool:
                        for selected_client in selected_clients:
                            if selected_client not in alive_clients:
                                print(
                                    f"Client '{selected_client.name}' is dead, skipping.",
                                    flush=True,
                                )
                                continue
                            tasks.append(
                                (
                                    selected_client.name,
                                    pool.submit(
                                        capture_stdout_wrapper,
                                        selected_client.execute_command,
                                        command,
                                        cmd.parameters,
                                    ),
                                )
                            )
                        for client_name, task in tasks:
                            while not task.done:
                                pass
                            stdout_cap, command_result = task.result()
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
                else:
                    for selected_client in self.__clients.get_selected_clients():
                        if selected_client not in alive_clients:
                            print(f"Client '{selected_client.name}' is dead, skipping.")
                            continue
                        stdout_cap = io.StringIO()
                        with contextlib.redirect_stdout(
                            stdout_cap
                        ), contextlib.redirect_stderr(stdout_cap):
                            command_result = selected_client.execute_command(
                                command, cmd.parameters
                            )
                        command_results[selected_client.name] = command_result
                        print(
                            f"Completed execution of command on client '{selected_client.name}' (status: ",
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
                        print(stdout_cap, end="")
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
