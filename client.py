import shared.extras.platform as platform

platform.ensure_python_version()
platform.extend_path()
from shared.extras.install_modules import install as install_modules
from client_extras.connection import Connection

from typing import Final
import argparse


IP: Final[str] = "127.0.0.1"
PORT: Final[int] = 7890


def main() -> None:
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument(
        "-r", "--reconnect", help="Reconnect with specific username", type=str
    )
    arg_parser.add_argument(
        "-i",
        "--install_requirements",
        help="Reconnect with specific username",
        action="store_true",
    )
    args = arg_parser.parse_args()

    if args.install_requirements:
        install_modules(client=True)

    name = args.reconnect

    conn = Connection(IP, PORT, name)
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
