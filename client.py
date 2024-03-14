import shared.extras.platform as platform

platform.ensure_python_version()
platform.extend_path()
from shared.extras.install_modules import install as install_modules
from client_extras.connection import Connection

from typing import Final


IP: Final[str] = "127.0.0.1"
PORT: Final[int] = 7892


def main() -> None:
    install_modules(client=True)
    conn = Connection(IP, PORT)
    print("Connected to server.")
    while True:
        try:
            conn.recieve_command()
        except ConnectionResetError:
            print("Connection closed by server, quitting...")
            exit()
        except OSError:
            print("Connection error, quitting...")
            exit()


if __name__ == "__main__":
    main()
