import sys


def check_versions() -> tuple[bool, bool]:
    return check_system(), check_py_version()


def check_system() -> bool:
    if sys.platform != "win32":
        return False
        print(
            f"This program is currently only compatible with Microsoft Windows ({sys.platform}), it probably wont work on {sys.platform}."
        )
    return True


def check_py_version() -> bool:
    if sys.version_info < (3, 12):
        return False
        print(
            f"This program is currently only compatible with Python 3.12 ({sys.version_info}) and up, you should expect to encounter issues on '{sys.version_info}'."
        )
    return True


def extend_path() -> None:
    sys.path.append("../../../")
    sys.path.append("../../")
    sys.path.append("../")
    sys.path.append("./")
