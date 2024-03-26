import shared.extras.platform as platform

platform.ensure_python_version()
platform.extend_path()
from shared.extras.install_modules import install as install_modules
from shared.extras.arguments import validate_arguments
from server_extras.server import ServerThread

import argparse


def main() -> None:
    arg_parser = argparse.ArgumentParser(prog="C3 Server")
    arg_parser.add_argument(
        "-i",
        "--install_requirements",
        help="Install (double command) server requirements",
        action="store_true",
    )
    arg_parser.add_argument("listen_address")
    arg_parser.add_argument("listen_port", type=int)
    args = arg_parser.parse_args()

    if args.install_requirements:
        install_modules(server=True)

    if not validate_arguments(args.listen_address, args.listen_port, try_bind=True):
        return

    server_thread = ServerThread(args.listen_address, args.listen_port)
    server_thread.start()
    try:
        server_thread.join()
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
