from server_extras.command_parser import (
    ValidateCommandResult,
    CommandParser,
    ParsedCommand,
    parse_command,
)
from shared.extras.double_command import InternalDoubleCommand, double_commands
from server_extras.local_command import InternalLocalCommand, local_commands
from shared.extras.custom_io import StdoutCapturingProcess, CustomStdout
from server_extras.server_acceptor import ServerAcceptorThread
from server_extras.formatting import generate_command_execute_message
from shared.extras.encrypted_socket import EncryptedSocket
from server_extras.client import ClientBucket, Client
from shared.extras.command import CommandResult

from typing import Callable, Literal, Any
import multiprocessing
import threading
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
        self.__socket = EncryptedSocket()
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
                started, skipped_clients = self.__prepare_and_start_double_command(
                    command.name, cmdline, command_outputs
                )

                if started != "success":
                    continue

                if (
                    command.no_new_process
                ):  # the command handler will handle the command output
                    continue

                old_line_count = len(self.__custom_stdout.lines)
                is_first_run = True
                last_run = False
                all_done = all(
                    [output.status != None for output in command_outputs.values()]
                )
                while last_run or (not all_done):
                    self.__custom_stdout.clear_lines(
                        (len(self.__custom_stdout.lines) - old_line_count)
                        + (0 if is_first_run else 1)
                    )
                    is_first_run = False
                    old_line_count = len(self.__custom_stdout.lines)
                    for client_name, output in command_outputs.items():
                        print(
                            generate_command_execute_message(output.status, client_name)  # type: ignore
                        )
                        print(output.process_handle.stdout, end="", flush=True)  # type: ignore

                    if last_run:
                        break
                    all_done = all(
                        [output.status != None for output in command_outputs.values()]
                    )
                    if all_done:
                        last_run = True

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
        Literal["no_clients", "too_many_clients", "command_not_found", "success"],
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

        if command.no_new_process:
            skipped_clients = self.__run_double_command(
                arguments, command, selected_clients, alive_clients, outputs
            )
        else:
            skipped_clients = self.__start_double_command(
                arguments, command, selected_clients, alive_clients, outputs
            )
        return "success", skipped_clients

    def __run_double_command(
        self,
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

        for selected_client, output in zip(selected_clients, outputs.values()):
            print(f"Executing command on client '{selected_client.name}':")
            old_line_count = len(self.__custom_stdout.lines)
            selected_client.execute_command(command, cmdline_args.parameters, output)
            new_line_count = len(self.__custom_stdout.lines)

            self.__custom_stdout.print_to_earlier_line(
                (new_line_count - old_line_count) + 1,
                generate_command_execute_message(
                    output.status, selected_client.name  # type: ignore
                ),
            )

        return skipped_clients

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

            outputs[selected_client.name].set_process_handle(proc)

        for output in outputs.values():
            output.process_handle.start()  # type: ignore
            if command.no_multitask:
                output.process_handle.join()  # type: ignore

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
    def socket(self) -> EncryptedSocket:
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
