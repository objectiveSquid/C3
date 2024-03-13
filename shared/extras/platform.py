from typing import NoReturn
import sys


if sys.version_info < (3, 12):

    def ensure_python_version() -> NoReturn:
        print(
            f"This program is currently only compatible with Python 3.12 (3.12.X) and after, it will not work on version: '{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}'"
        )
        exit()

else:

    def ensure_python_version() -> None:
        return


def extend_path() -> None:
    sys.path.append("../../../")
    sys.path.append("../../")
    sys.path.append("../")
    sys.path.append("./")
