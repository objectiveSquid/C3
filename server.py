import shared.extras.platform as platform
import sys

platform.ensure_python_version()
if sys.platform == "win32":
    platform.extend_path()
from shared.extras.install_modules import install as install_modules
from shared.extras.arguments import validate_arguments, DEFAULT_PORT
from server_extras.server import ServerThread

import argparse


def main() -> int:
    arg_parser = argparse.ArgumentParser(prog="C3 Server")
    arg_parser.add_argument(
        "-i",
        "--install_requirements",
        help="Install (double command) server requirements",
        action="store_true",
    )
    arg_parser.add_argument("listen_address")
    arg_parser.add_argument("listen_port", type=int, default=DEFAULT_PORT)
    args = arg_parser.parse_args()

    if args.install_requirements:
        install_modules(server=True)

    if not validate_arguments(args.listen_address, args.listen_port, try_bind=True):
        return 1

    server_thread = ServerThread(args.listen_address, args.listen_port)
    server_thread.start()
    try:
        server_thread.join()
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == "__main__":
    exit(main())
