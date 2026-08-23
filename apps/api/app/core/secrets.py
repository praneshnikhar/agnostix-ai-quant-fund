"""Server-side encryption boundary for provider credentials."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class SecretConfigurationError(RuntimeError):
    """Raised when the provider credential key is missing or invalid."""


class SecretDecryptionError(RuntimeError):
    """Raised when encrypted provider material cannot be decrypted."""


def encrypt_secret(value: str, key: str) -> str:
    if not value:
        raise ValueError("secret value must not be empty")
    try:
        return Fernet(key.encode()).encrypt(value.encode()).decode()
    except (ValueError, TypeError) as exc:
        raise SecretConfigurationError("provider encryption key is invalid") from exc


def decrypt_secret(ciphertext: str, key: str) -> str:
    try:
        return Fernet(key.encode()).decrypt(ciphertext.encode()).decode()
    except (InvalidToken, ValueError, TypeError) as exc:
        raise SecretDecryptionError("provider credential could not be decrypted") from exc


def require_provider_encryption_key(key: str | None) -> str:
    if not key:
        raise SecretConfigurationError(
            "API_PROVIDER_ENCRYPTION_KEY must be configured before provider "
            "credentials can be stored"
        )
    # Construct once to validate the key without exposing it.
    try:
        Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise SecretConfigurationError("provider encryption key is invalid") from exc
    return key


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    suffix = value[-4:]
    return f"••••••••{suffix}"
