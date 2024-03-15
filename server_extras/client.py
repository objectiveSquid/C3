from shared.extras.double_command import (
    InternalDoubleCommand,
    DoubleCommandResult,
    recieve_last_bytes,
    recieve_string,
    CommandResult,
    send_string,
)
from shared.extras.command import ExecuteCommandResult, CommandResult
from server_extras.command_parser import CommandToken
from server_extras.custom_io import CustomStdout

import concurrent.futures as futures
from typing import Callable, Any
import warnings
import inspect
import random
import socket
import enum


class Client:
    def __init__(
        self,
        client_socket: socket.socket,
        client_ip: str,
        client_port: int,
        name: str | None = None,
    ) -> None:
        self.__sock = client_socket
        self.__sock.setblocking(True)
        self.__sock.settimeout(5)

        self.__ip = client_ip
        self.__port = client_port
        self.__selected = False
        self.__alive = True
        if isinstance(name, str):
            self.__name = name
        else:
            self.__name = "".join(
                random.choices("abcdefghijklmnopqrstuvwxyz1234567890", k=8)
            )

    def execute_command(
        self,
        cmd: InternalDoubleCommand,
        params: list[CommandToken],
    ) -> CommandResult:
        self.__sock.setblocking(True)
        retries = 0
        sent_cmd = False
        while retries < 3:
            if not sent_cmd:
                try:
                    send_string(self.__sock, cmd.name)
                except OSError:
                    retries += 1
                    continue
                sent_cmd = True
                retries = 0
            try:
                started = recieve_string(self.__sock)
            except (UnicodeDecodeError, OSError):
                retries += 1
                continue
            match started:
                case "notfound":
                    return CommandResult(ExecuteCommandResult.not_found)
                case "running":
                    pass
                case _:
                    return CommandResult(ExecuteCommandResult.failure)
            ret_val = cmd.command.server_side(self, tuple(params))
            match ret_val.status:
                case DoubleCommandResult.success:
                    ret_val.set_status(ExecuteCommandResult.success)
                case DoubleCommandResult.semi_success:
                    ret_val.set_status(ExecuteCommandResult.semi_success)
                case (
                    DoubleCommandResult.failure
                    | DoubleCommandResult.timeout
                    | DoubleCommandResult.conn_error
                ):
                    ret_val.set_status(ExecuteCommandResult.failure)
            return ret_val
        return CommandResult(ExecuteCommandResult.max_retries_hit)

    def create_temp_socket(
        self, blocking: bool | None = None, timeout: float | None = None
    ) -> socket.socket:
        tmp_sock = self.__sock.dup()

        if blocking == None:
            tmp_sock.setblocking(self.__sock.getblocking())
        else:
            tmp_sock.setblocking(blocking)
        if timeout == None:
            orig_sock_timeout = self.__sock.gettimeout()
            tmp_sock.settimeout(5 if orig_sock_timeout == None else orig_sock_timeout)
        else:
            tmp_sock.settimeout(timeout)

        if blocking != None:
            tmp_sock.setblocking(blocking)
        if timeout != None:
            tmp_sock.settimeout(timeout)
        return tmp_sock

    def ping(self, kill_if_dead: bool = True) -> bool:
        try:
            send_string(self.__sock, "ping")
            is_alive = (
                recieve_last_bytes(self.__sock, 4) == b"pong"
            )  # if a command left some unused socket data, we clear it
            self.__alive = is_alive
            if kill_if_dead and not is_alive:
                self.kill()
            return is_alive
        except OSError:
            if kill_if_dead:
                self.kill()
            return False

    def set_name(self, new_name: str) -> None:
        self.__name = new_name

    def set_selected(self, new_value: bool) -> None:
        self.__selected = new_value

    def kill(self) -> None:
        try:
            self.__sock.close()
        except OSError:
            pass
        self.mark_dead()

    def mark_dead(self) -> None:
        self.__alive = False

    @property
    def ip(self) -> str:
        return self.__ip

    @property
    def port(self) -> int:
        return self.__port

    @property
    def is_alive(self) -> bool:
        return self.__alive

    @property
    def is_dead(self) -> bool:
        return not self.__alive

    @property
    def socket(self) -> socket.socket:
        return self.__sock

    @property
    def name(self) -> str:
        return self.__name

    @property
    def is_selected(self) -> bool:
        return self.__selected


class RenameClientResult(enum.Enum):
    success = 0
    name_not_found = 1
    name_in_use = 2
    no_name = 3


class ClientBucket:
    def __init__(
        self,
        custom_stdout: CustomStdout,
        on_new_connect: Callable[[Client], None] | None = None,
    ) -> None:
        self.__clients: list[Client] = []
        self.__new_clients: list[Client] = []
        self.__custom_stdout = custom_stdout
        self.__on_new_connect = None
        if self.__callable_with_args(on_new_connect, 1):
            self.__on_new_connect = on_new_connect

    def add(self, new_client: Client) -> None:
        self.__clients.append(new_client)
        self.__new_clients.append(new_client)
        if self.__on_new_connect == None:
            self.__custom_stdout.push_line_print(
                f"New connection from {new_client.ip}:{new_client.port} ({new_client.name})"
            )
            return
        else:
            self.__on_new_connect(new_client)
            return

    def kill_all_clients(self) -> None:
        for client in self.__clients:
            client.kill()

    def remove_all_clients(self) -> None:
        self.kill_all_clients()
        self.__clients.clear()
        self.__new_clients.clear()

    def rename_client(self, old_name: str, new_name: str) -> RenameClientResult:
        current_names = [client.name.casefold() for client in self.__clients]
        if old_name.casefold() not in current_names:
            return RenameClientResult.name_not_found
        if new_name.casefold() in current_names:
            return RenameClientResult.name_in_use
        for client in self.__clients:
            if client.name.casefold() == old_name.casefold():
                client.set_name(new_name)
                return RenameClientResult.success
        return RenameClientResult.no_name

    def remove_client(self, name: str) -> tuple[bool, str]:
        for client in self.__clients:
            if client.name.casefold() == name.casefold():
                client.kill()
                self.__clients.remove(client)
                self.__new_clients.remove(client)
                return True, client.name
        return False, ""

    def select_client(self, name: str) -> tuple[int, str]:
        for client in self.__clients:
            if client.name.casefold() == name.casefold():
                if client.is_selected:
                    return 2, client.name
                client.set_selected(True)
                return 1, client.name
        return 0, ""

    def deselect_client(self, name: str) -> tuple[int, str]:
        for client in self.__clients:
            if client.name.casefold() == name.casefold():
                if not client.is_selected:
                    return 2, client.name
                client.set_selected(False)
                return 1, client.name
        return 0, ""

    def get_selected_clients(self) -> list[Client]:
        return [client for client in self.__clients if client.is_selected]

    def get_alive_clients(self) -> list[Client]:
        if len(self.__clients) == 0:
            return []
        with futures.ThreadPoolExecutor(len(self.__clients)) as pool:
            return [
                client
                for client in pool.map(
                    lambda c: c if c.ping() else None, self.__clients
                )
                if isinstance(client, Client)
            ]

    def get_new_clients(self, clear: bool = True) -> list[Client]:
        output = self.__new_clients.copy()
        if clear:
            self.__new_clients.clear()
        return output

    @staticmethod
    def __callable_with_args(obj: Any, num_args: int, return_val: type = type[Any]):
        if callable(obj):
            sig = inspect.signature(obj)
            sig_params = sig.parameters
            sig_ret = sig.return_annotation
            if len(sig_params) < num_args:
                return False
            for func_param_num, func_param in enumerate(sig_params.values()):
                if func_param.default != sig.empty:
                    continue
                if func_param_num >= num_args:
                    return False
            if sig_ret != return_val and sig_ret != sig.empty:
                return False
            return True
        else:
            return False

    @property
    def client_list(self) -> list[Client]:
        return self.__clients

    def __len__(self) -> int:
        return len(self.__clients)
