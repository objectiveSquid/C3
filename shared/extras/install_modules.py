from shared.extras.double_command import PLATFORM_TO_OS_TYPE_LOOKUP, double_commands

import subprocess
import sys


def install(
    server: bool = False, client: bool = False, skip_client_non_compatible: bool = True
):
    print("Installing required modules.")
    install_commands = []
    required_modules = []
    if skip_client_non_compatible:
        os_type = PLATFORM_TO_OS_TYPE_LOOKUP.get(sys.platform)
        if os_type == None:
            print(
                f"OS type not recognized ('{sys.platform}' not in lookup table), not checking for non compatible commands when installing dependencies"
            )
    for command_name, command in double_commands.items():
        if server:
            required_modules.append((command_name, command.required_server_modules))
        if client:
            if skip_client_non_compatible and os_type not in command.supported_os:
                continue
            required_modules.append((command_name, command.required_client_modules))

    for command_name, modules in required_modules:
        for module in modules:
            install_commands.append(
                (
                    command_name,
                    module,
                    subprocess.Popen(
                        [sys.executable, "-m", "pip", "install", module],
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
    print("Installed required modules.")
