import shared.extras.platform as platform

platform.ensure_versions()
platform.extend_path()
from shared.extras.install_modules import install as install_modules
from server_extras.server import ServerThread

from typing import Final


IP: Final[str] = "127.0.0.1"
PORT: Final[int] = 7892


def main() -> None:
    install_modules("server")
    server_thread = ServerThread(IP, PORT)
    server_thread.start()
    try:
        server_thread.join()
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
