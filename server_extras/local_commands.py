from server_extras.local_command import (
    InternalLocalCommand,
    LocalCommandResult,
    add_local_command,
    LocalCommand,
)
from shared.extras.double_command import (
    InternalDoubleCommand,
    ArgumentType,
)
from shared.extras.command import CommandResult

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server_extras.server import ServerThread


@add_local_command(
    "exit",
    "exit",
    "Removes all clients and exits",
    [],
)
class ExitShell(LocalCommand):
    @staticmethod
    def local_side(server_thread: "ServerThread", params: tuple) -> CommandResult:
        if len(server_thread.clients) > 0:
            alive_clients = len(server_thread.clients.get_alive_clients())
            if (
                not input(
                    f"You have {len(server_thread.clients)} clients ({alive_clients} alive) ({len(server_thread.clients) - alive_clients} dead)\nAre you sure you want to exit? [Y/n]: "
                )
                .casefold()
                .startswith("y")
            ):
                return CommandResult(LocalCommandResult.failure)
        server_thread.stop()
        print("Exiting...")
        return CommandResult(LocalCommandResult.success)


@add_local_command(
    "list_clients",
    "list_clients { subset of clients }",
    "Lists your infected clients",
    [ArgumentType.optional_string],
)
class ListClients(LocalCommand):
    @staticmethod
    def local_side(server_thread: "ServerThread", params: tuple) -> CommandResult:
        if len(params) == 0:
            print(f"You have {len(server_thread.clients)} total clients:")
            for client in server_thread.clients.client_list:
                print(f"{client.name} -> {client.ip}:{client.port}")
            return CommandResult(LocalCommandResult.success)
        match params[0]:
            case "new":
                new_clients = server_thread.clients.get_new_clients(clear=True)
                print(f"You have {len(new_clients)} new clients:")
                for client in new_clients:
                    print(f"{client.name} -> {client.ip}:{client.port}")
            case "alive":
                alive_clients = server_thread.clients.get_alive_clients()
                print(f"You have {len(alive_clients)} alive clients:")
                for client in alive_clients:
                    print(f"{client.name} -> {client.ip}:{client.port}")
            case "selected":
                selected_clients = server_thread.clients.get_selected_clients()
                print(f"You have {len(selected_clients)} selected clients:")
                for client in selected_clients:
                    print(f"{client.name} -> {client.ip}:{client.port}")
            case _:
                print(
                    f"If given, the first argument must be 'new', 'selected' or 'alive', not '{params[0]}'."
                )
                return CommandResult(LocalCommandResult.param_error)
        return CommandResult(LocalCommandResult.success)


@add_local_command(
    "remove_client",
    "remove_client [ client name ]",
    "Kills and removes a client",
    [ArgumentType.string],
)
class RemoveClient(LocalCommand):
    @staticmethod
    def local_side(server_thread: "ServerThread", params: tuple) -> CommandResult:
        client_existed, client_name = server_thread.clients.remove_client(params[0])
        if client_existed:
            print(f"Killed and removed client: {client_name}")
            return CommandResult(LocalCommandResult.success)
        else:
            print(f"No client named {params[0]}")
            return CommandResult(LocalCommandResult.param_error)


@add_local_command(
    "rename_client",
    "rename_client [ current client name ] [ new client name ]",
    "Renames a client",
    [ArgumentType.string, ArgumentType.string],
)
class RenameClient(LocalCommand):
    @staticmethod
    def local_side(server_thread: "ServerThread", params: tuple) -> CommandResult:
        from server_extras.client import RenameClientResult

        if params[0].casefold() == params[1].casefold():
            print(f"The first parameter must not be the same as the second one.")
            return CommandResult(LocalCommandResult.param_error)
        success = server_thread.clients.rename_client(params[0], params[1])
        match success:
            case RenameClientResult.success:
                print(f"Renamed client '{params[0]}' to '{params[1]}'.")
                return CommandResult(LocalCommandResult.success)
            case RenameClientResult.name_not_found:
                print(f"No client named '{params[0]}'.")
                return CommandResult(LocalCommandResult.param_error)
            case RenameClientResult.name_in_use:
                print(f"Name '{params[1]}' already in use.")
                return CommandResult(LocalCommandResult.param_error)
            case _:
                print(f"Unknown error while renaming '{params[0]}' to '{params[1]}'.")
                return CommandResult(LocalCommandResult.failure)


@add_local_command(
    "clear",
    "clear",
    "Clears the console",
    [],
)
class ClearScreen(LocalCommand):
    @staticmethod
    def local_side(server_thread: "ServerThread", params: tuple) -> CommandResult:
        server_thread.custom_stdout.clear_screen()
        return CommandResult(LocalCommandResult.success)


@add_local_command(
    "select",
    "select [ client name ]",
    "Selects a client for command execution",
    [ArgumentType.string],
)
class SelectClient(LocalCommand):
    @staticmethod
    def local_side(server_thread: "ServerThread", params: tuple) -> CommandResult:
        select_result = server_thread.clients.select_client(params[0])
        match select_result[0]:
            case 0:
                print(f"Client '{params[0]}' not found.")
                return CommandResult(LocalCommandResult.param_error)
            case 1:
                print(f"Selected '{select_result[1]}'")
                return CommandResult(LocalCommandResult.success)
            case 2:
                print(f"Client '{select_result[1]}' already selected.")
                return CommandResult(LocalCommandResult.success)
            case _:
                print(f"Unknown error.")
                return CommandResult(LocalCommandResult.failure)


@add_local_command(
    "deselect",
    "deselect [ client name ]",
    "Deselects a client",
    [ArgumentType.string],
)
class DeselectClient(LocalCommand):
    @staticmethod
    def local_side(server_thread: "ServerThread", params: tuple) -> CommandResult:
        deselect_result = server_thread.clients.deselect_client(params[0])
        match deselect_result[0]:
            case 0:
                print(f"Client '{params[0]}' not found.")
                return CommandResult(LocalCommandResult.param_error)
            case 1:
                print(f"Deselected '{deselect_result[1]}'")
                return CommandResult(LocalCommandResult.success)
            case 2:
                print(f"Client '{deselect_result[1]}' isn't selected.")
                return CommandResult(LocalCommandResult.success)
            case _:
                print(f"Unknown error.")
                return CommandResult(LocalCommandResult.failure)


@add_local_command(
    "help",
    "help { command name }",
    "Displays help about command(s)",
    [ArgumentType.optional_string],
)
class Help(LocalCommand):
    @staticmethod
    def local_side(server_thread: "ServerThread", params: tuple) -> CommandResult:
        from shared.extras.double_command import double_commands
        from server_extras.local_command import local_commands

        longest_command_name_length = max(
            max([len(cmd_name) for cmd_name in double_commands.keys()]),
            max([len(cmd_name) for cmd_name in local_commands.keys()]),
        )
        if len(params) == 0:
            print("---------- Double commands (executed on client) ----------")
            for cmd_name, cmd in double_commands.items():
                print(
                    f"{cmd_name + ':': <{longest_command_name_length + 1}} {cmd.description}"
                )
            print("\n---------- Local commands (server-side only) ----------")
            for cmd_name, cmd in local_commands.items():
                print(
                    f"{cmd_name + ':': <{longest_command_name_length + 1}} {cmd.description}"
                )
        else:
            merged_commands = {
                **double_commands,
                **local_commands,
            }
            if params[0] not in merged_commands:
                print(f"Command '{params[0]} doesn't exist")
                return CommandResult(LocalCommandResult.param_error)
            cmd: InternalLocalCommand | InternalDoubleCommand = merged_commands[
                params[0]
            ]
            if cmd.usage.count("{") or cmd.usage.count("["):
                print("{ param } = optional parameter")
                print("[ param ] = required parameter")
            print(f"Usage: {cmd.usage}", end="\n\n")
            print(f"Description: {cmd.description}")

        return CommandResult(LocalCommandResult.success)
