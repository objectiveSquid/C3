from shared.extras.command import ExecuteCommandResult
import colorama


def generate_command_execute_message(
    status: ExecuteCommandResult, client_name: str
) -> str:
    output = ""

    if status == None:
        output += f"Executing command on client '{client_name}':"
    else:
        output += f"Completed execution of command on client '{client_name}' (status: "
        if status == ExecuteCommandResult.success:
            output += colorama.Fore.LIGHTGREEN_EX
        elif status == ExecuteCommandResult.semi_success:
            output += colorama.Fore.YELLOW
        else:
            output += colorama.Fore.RED
        output += f"{status.name}{colorama.Fore.RESET}):"

    return output
