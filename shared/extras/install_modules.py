from shared.extras.double_command import double_commands

from typing import Literal
import subprocess
import os.path


def install(target: Literal["server", "client"]):
    print("Installing required modules.")
    pip_path = "pip"
    parent_dir = os.path.split(__file__)[0].replace("\\", "/").split("/")[:-2]
    possible_pip_path = f"{parent_dir}/runtime/Scripts/pip.exe"
    if os.path.isfile(possible_pip_path):
        pip_path = possible_pip_path
    installed_modules = []
    install_commands: list[tuple[str, subprocess.Popen]] = []
    for command in double_commands.values():
        required_modules = (
            command.required_client_modules
            if target == "client"
            else command.required_server_modules
        )
        for module in required_modules:
            if module.lower() in installed_modules:
                continue
            installed_modules.append(module.lower())
            install_commands.append(
                (
                    module,
                    subprocess.Popen(
                        [pip_path, "install", module],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    ),
                )
            )
    for module, command in install_commands:
        if command.wait() != 0:
            print(f"Module '{module}' failed to install.")
    print(f"Installed required modules.")
