import shared.extras.platform as platform

platform.ensure_python_version()
platform.extend_path()
from shared.extras.install_modules import install as install_modules
from server_extras.server import ServerThread

from typing import Final
import argparse


IP: Final[str] = "127.0.0.1"
PORT: Final[int] = 7890


def main() -> None:
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument(
        "-i",
        "--install_requirements",
        help="Reconnect with specific username",
        action="store_true",
    )
    args = arg_parser.parse_args()

    if args.install_requirements:
        install_modules(server=True)

    server_thread = ServerThread(IP, PORT)
    server_thread.start()
    try:
        server_thread.join()
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
