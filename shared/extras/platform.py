import sys


def ensure_versions() -> None:
    if not all([check_system(), check_py_version()]):
        sys.exit()


def check_system() -> bool:
    if sys.platform != "win32":
        print(
            f"This program is currently only compatible with Microsoft Windows (win32), it will not work on platform: '{sys.platform}'"
        )
        return False
    return True


def check_py_version() -> bool:
    if sys.version_info < (3, 12):
        print(
            f"This program is currently only compatible with Python 3.12 (3.12.X) and after, it will not work on version: '{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}'"
        )
        return False
    return True


def extend_path() -> None:
    sys.path.append("../../../")
    sys.path.append("../../")
    sys.path.append("../")
    sys.path.append("./")
