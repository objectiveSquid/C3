from shared.extras.double_command import double_commands

from typing import Literal
import subprocess
import sys


def install(target: Literal["server", "client"]):
    print("Installing required modules.")
    pip_path = f"{sys.executable} -m pip"
    install_commands = []
    for command_name, command in double_commands.items():
        if target == "client":
            required_modules = command.required_client_modules
        else:
            required_modules = command.required_server_modules

        for module in required_modules:
            install_commands.append(
                (
                    command_name,
                    module,
                    subprocess.Popen(
                        [pip_path, "install", module],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=(
                            subprocess.CREATE_NO_WINDOW
                            if sys.platform == "win32"
                            else 0
                        ),
                    ),
                )
            )
    for command_name, module, command in install_commands:
        if command.wait() != 0:
            print(
                f"Command '{command_name}' depended on '{module}', but it failed to install."
            )
    print(f"Installed required modules.")
