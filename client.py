import shared.extras.platform as platform
import sys

platform.ensure_python_version()
if sys.platform == "win32":
    platform.extend_path()
from shared.extras.install_modules import install as install_modules
from shared.extras.arguments import validate_arguments
from client_extras.connection import Connection

import argparse


def main() -> int:
    arg_parser = argparse.ArgumentParser(prog="C3 Client")
    arg_parser.add_argument(
        "-r", "--reconnect", help="Reconnect with specific username", type=str
    )
    install_reqs_group = arg_parser.add_mutually_exclusive_group()
    install_reqs_group.add_argument(
        "-i",
        "--install_requirements",
        help="Install (double command) client requirements",
        action="store_true",
    )
    install_reqs_group.add_argument(
        "-si",
        "--smart_install_requirements",
        help="Install (double command) client requirements, and skip those from non compatible commands",
        action="store_true",
    )
    arg_parser.add_argument("remote_address")
    arg_parser.add_argument("remote_port", type=int)
    args = arg_parser.parse_args()

    if args.install_requirements:
        install_modules(client=True)
    if args.smart_install_requirements:
        install_modules(client=True, skip_client_non_compatible=True)

    if not validate_arguments(args.remote_address, args.remote_port):
        return 1

    conn = Connection(args.remote_address, args.remote_port, args.reconnect)
    print("Connected to server.")
    while True:
        try:
            conn.recieve_command()
        except ConnectionResetError:
            print("Connection closed by server, quitting...")
            break
        except OSError:
            print("Connection error, quitting...")
            break

    return 0


if __name__ == "__main__":
    exit(main())
