"""Fernet encryption for secrets an administrator saves in the database."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class CryptoError(Exception):
    pass


def encrypt_secret(fernet_key: str | None, value: str) -> str:
    if not fernet_key:
        raise CryptoError("missing_key")
    try:
        return Fernet(fernet_key.encode("utf-8")).encrypt(value.encode("utf-8")).decode("utf-8")
    except (ValueError, TypeError) as exc:
        raise CryptoError("invalid_key") from exc


def decrypt_secret(fernet_key: str | None, ciphertext: str) -> str:
    if not fernet_key:
        raise CryptoError("missing_key")
    try:
        return (
            Fernet(fernet_key.encode("utf-8")).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        )
    except (InvalidToken, ValueError, TypeError) as exc:
        raise CryptoError("decrypt_failed") from exc
