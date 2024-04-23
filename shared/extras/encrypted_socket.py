from __future__ import annotations

from shared.extras.custom_io import temp_filepath, FileLock

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from typing import Callable, Iterable, Any
import warnings
import random
import socket
import os


def not_encrypted_warn(func: Callable) -> Callable[..., Any]:
    def wrapper(*args, **kwargs) -> Any:
        warnings.warn(
            "this has not been implemented with encryption, using unencrypted functionality"
        )
        func(*args, **kwargs)

    return wrapper


def recreate_public_key(key_bytes: bytes) -> rsa.RSAPublicKey:
    return serialization.load_pem_public_key(key_bytes, backend=default_backend())  # type: ignore


def generate_keys(
    key_size: int,
) -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey, bytes, bytes]:
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=key_size, backend=default_backend()
    )
    public_key = private_key.public_key()

    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return private_key, public_key, private_key_pem, public_key_pem


class EncryptedSocket(socket.socket):
    def __init__(
        self,
        family: socket.AddressFamily | int = -1,
        type: socket.SocketKind | int = -1,
        proto: int = -1,
        fileno: int | None = None,
        xor_key_len: int = 1024,
    ) -> None:
        super().__init__(family, type, proto, fileno)

        self.__encrypt_xor_key_len = xor_key_len
        self.__encrypt_xor_key_usage_lock = FileLock()
        self.__encrypt_xor_key_usage_file = temp_filepath(".u64int", True)
        with open(self.__encrypt_xor_key_usage_file, "wb") as usage_fd:
            usage_fd.write(b"\x00" * 8)

        self.__remote_encrypt_xor_key_usage_lock = FileLock()
        self.__remote_encrypt_xor_key_usage_file = temp_filepath(".u64int", True)
        with open(self.__remote_encrypt_xor_key_usage_file, "wb") as usage_fd:
            usage_fd.write(b"\x00" * 8)

        self.__encryption_initlialized = False

    def initialize_encryption(self) -> None:
        if self.__encryption_initlialized:
            raise Exception("encryption has already been initialized")
        self.__private_key, *_, self.__public_key_pem = generate_keys(2048)

        super().sendall(len(self.__public_key_pem).to_bytes(8))
        super().sendall(self.__public_key_pem)

        self.__remote_public_key = recreate_public_key(
            super().recv(int.from_bytes(super().recv(8)))
        )

        self.__create_and_send_encrypt_xor_key()
        self.__recieve_encrypt_xor_key()

        self.__encryption_initlialized = True

    def accept(self) -> tuple[EncryptedSocket, socket._RetAddress]:
        sock, ret_addr = super().accept()

        enc_sock = EncryptedSocket(xor_key_len=self.__encrypt_xor_key_len)

        os.dup2(sock.fileno(), enc_sock.fileno())
        return enc_sock, ret_addr

    def sendall(self, data: bytes) -> None:
        self.__check_encryption_initialization()
        encrypted_data = bytearray()

        usage = self.get_encrypt_xor_key_usage()
        self.__encrypt_xor_key_usage_lock.acquire()
        for byte in data:
            xor_byte = self.__encryption_xor_key[usage % self.__encrypt_xor_key_len]
            usage += 1

            encrypted_data += (byte ^ xor_byte).to_bytes()

        self.set_encrypt_xor_key_usage(usage, True)
        self.__encrypt_xor_key_usage_lock.release()
        super().sendall(encrypted_data)

    def recv(self, bufsize: int) -> bytes:
        self.__check_encryption_initialization()
        output = bytearray()

        usage = self.get_remote_encrypt_xor_key_usage()
        self.__remote_encrypt_xor_key_usage_lock.acquire()
        for byte in super().recv(bufsize):
            xor_byte = self.__remote_encrypt_xor_key[
                usage % self.__remote_encrypt_xor_key_len
            ]
            usage += 1

            output += (byte ^ xor_byte).to_bytes()

        self.set_remote_encrypt_xor_key_usage(usage, True)
        self.__remote_encrypt_xor_key_usage_lock.release()
        return output

    def __create_and_send_encrypt_xor_key(self) -> None:
        self.__encryption_xor_key = random.randbytes(self.__encrypt_xor_key_len)

        encryption_key_parts = [
            self.__encryption_xor_key[i : i + 245]
            for i in range(0, self.__encrypt_xor_key_len, 245)
        ]

        for part in encryption_key_parts:
            encrypted_key = self.__remote_public_key.encrypt(part, padding.PKCS1v15())

            super().sendall(len(encrypted_key).to_bytes(2))
            super().sendall(encrypted_key)

        super().sendall(b"\x00" * 2)

    def __recieve_encrypt_xor_key(self) -> None:
        self.__remote_encrypt_xor_key = bytearray()

        while True:
            encrypted_encrypt_xor_key_part_len = int.from_bytes(super().recv(2))
            if encrypted_encrypt_xor_key_part_len == 0:
                break
            self.__remote_encrypt_xor_key += self.__private_key.decrypt(
                super().recv(encrypted_encrypt_xor_key_part_len), padding.PKCS1v15()
            )

        self.__remote_encrypt_xor_key_len = len(self.__remote_encrypt_xor_key)

    def get_remote_encrypt_xor_key_usage(self) -> int:
        return self.__get_key_usage_file(
            self.__remote_encrypt_xor_key_usage_file,
            self.__remote_encrypt_xor_key_usage_lock,
        )

    def get_encrypt_xor_key_usage(self) -> int:
        return self.__get_key_usage_file(
            self.__encrypt_xor_key_usage_file,
            self.__encrypt_xor_key_usage_lock,
        )

    def set_remote_encrypt_xor_key_usage(
        self, usage: int, ignore_lock: bool = False
    ) -> None:
        self.__set_key_usage_file(
            usage,
            self.__remote_encrypt_xor_key_usage_file,
            self.__remote_encrypt_xor_key_usage_lock,
            ignore_lock,
        )

    def set_encrypt_xor_key_usage(self, usage: int, ignore_lock: bool = False) -> None:
        self.__set_key_usage_file(
            usage,
            self.__encrypt_xor_key_usage_file,
            self.__encrypt_xor_key_usage_lock,
            ignore_lock,
        )

    def __get_key_usage_file(self, file: str, lock: FileLock) -> int:
        lock.acquire()

        with open(file, "rb") as usage_fd:
            usage = int.from_bytes(usage_fd.read(8))

        lock.release()

        return usage

    def __set_key_usage_file(
        self, usage: int, file: str, lock: FileLock, ignore: bool
    ) -> None:
        if ignore:
            lock.acquire()

        with open(file, "wb") as usage_fd:
            usage_fd.write(usage.to_bytes(8))

        if ignore:
            lock.release()

    def __check_encryption_initialization(self) -> None:
        if not self.__encryption_initlialized:
            raise Exception(
                "encryption has not been initialized yet, you can do so by running the initliaze_encryption method"
            )

    def send(self, data: bytes, flags: int = 0) -> int:
        raise NotImplementedError("not implemented, use the sendall method instead")

    @not_encrypted_warn
    def sendfile(
        self, file: socket._SendableFile, offset: int = 0, count: int | None = None
    ) -> int:
        return super().sendfile(file, offset, count)

    @not_encrypted_warn
    def sendmsg(self, buffers: Iterable[ReadableBuffer], ancdata: Iterable[_CMSG] = ..., flags: int = ..., address: tuple[Any, ...] | str | ReadableBuffer | None = ...) -> int:  # type: ignore
        return super().sendmsg(buffers, ancdata, flags, address)

    @not_encrypted_warn
    def sendmsg_afalg(self, msg: Iterable[ReadableBuffer] = ..., *, op: int, iv: Any = ..., assoclen: int = ..., flags: int = ...) -> int:  # type: ignore
        return super().sendmsg_afalg(msg, op=op, iv=iv, assoclen=assoclen, flags=flags)

    @not_encrypted_warn
    def recv_into(
        self, buffer: ReadableBuffer, nbytes: int | None = ..., flags: int = ...  # type: ignore
    ) -> int:
        return super().recv_into(buffer, nbytes, flags)  # type: ignore

    @not_encrypted_warn
    def recvfrom(self, bufsize: int, flags: int = ...) -> tuple[bytes, Any]:  # type: ignore
        return super().recvfrom(bufsize, flags)

    @not_encrypted_warn
    def recvfrom_into(self, buffer: ReadableBuffer, nbytes: int = ..., flags: int = ...) -> tuple[int, Any]:  # type: ignore
        return super().recvfrom_into(buffer, nbytes, flags)

    @not_encrypted_warn
    def recvmsg(self, bufsize: int, ancbufsize: int = ..., flags: int = ...) -> tuple[bytes, list[tuple[int, int, bytes]], int, Any]:  # type: ignore
        return super().recvmsg(bufsize, ancbufsize, flags)

    @not_encrypted_warn
    def recvmsg_into(self, buffers: Iterable[ReadableBuffer], ancbufsize: int = ..., flags: int = ...) -> _CMSG[int | list[tuple[int, int, bytes]] | Any]:  # type: ignore
        return super().recvmsg_into(buffers, ancbufsize, flags)  # type: ignore
