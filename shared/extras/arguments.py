import ipaddress
import socket


def validate_arguments(address: str, port: int, try_bind: bool = False) -> bool:
    if port > 65535:
        print(f"Specified port ({port}) is too large, maximum is 65535")
        return False
    if port <= 0:
        print(f"Specified port ({port}) cannot be zero or lower")
        return False

    try:
        ipaddress.ip_address(address)
        if try_bind:
            with socket.socket() as temp_sock:
                temp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                temp_sock.bind((address, port))
    except ValueError:
        print(f"Invalid address ({address}) provided")
        return False
    except OSError:
        print(f"Could not bind to {address}:{port}")
        return False

    return True
