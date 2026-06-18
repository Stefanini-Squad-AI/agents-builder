"""Cryptographic services for secret encryption at rest.

Provides Fernet symmetric encryption with project-scoped keys derived
from a master key using HKDF. This ensures that compromising one
project's data does not expose secrets from other projects.

Usage:
    from app.crypto import get_crypto_service

    crypto = get_crypto_service()
    if crypto.is_enabled:
        encrypted = crypto.encrypt_dict(project_id, {"API_KEY": "secret"})
        decrypted = crypto.decrypt_dict(project_id, encrypted)
"""

from __future__ import annotations

import base64
import json
import uuid
from functools import lru_cache

import structlog
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.settings import get_settings

log = structlog.get_logger(__name__)

# Prefix to identify Fernet-encrypted values (vs plain JSON)
_ENCRYPTED_PREFIX = "fernet:v1:"


class CryptoService:
    """Fernet encryption with project-scoped keys.

    Keys are derived from the master key using HKDF with the project_id
    as salt. This provides cryptographic isolation between projects.

    If no master key is configured, encryption is disabled and methods
    fall back to plain JSON storage (with warnings).
    """

    def __init__(self, master_key: bytes | None = None):
        """Initialize the crypto service.

        Args:
            master_key: 32-byte master key for HKDF derivation.
                       If None, encryption is disabled.
        """
        self._master_key = master_key
        self._key_cache: dict[uuid.UUID, Fernet] = {}

        if self._master_key:
            log.info("crypto_service_initialized", encryption_enabled=True)
        else:
            log.warning(
                "crypto_service_disabled",
                reason="WORKSHOP_ENCRYPTION_KEY not set",
                hint="MCP secrets will be stored as plain JSON",
            )

    @property
    def is_enabled(self) -> bool:
        """Check if encryption is enabled."""
        return self._master_key is not None

    def derive_project_key(self, project_id: uuid.UUID) -> Fernet:
        """Derive a Fernet instance for a specific project.

        Uses HKDF to derive a 32-byte key from the master key,
        with the project_id as salt for isolation.

        Args:
            project_id: The project UUID to derive a key for

        Returns:
            Fernet instance for encrypt/decrypt operations

        Raises:
            RuntimeError: If encryption is not enabled
        """
        if not self._master_key:
            raise RuntimeError("Encryption is not enabled")

        if project_id in self._key_cache:
            return self._key_cache[project_id]

        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=project_id.bytes,
            info=b"mcp-secrets-v1",
        )
        derived_key = hkdf.derive(self._master_key)

        fernet_key = base64.urlsafe_b64encode(derived_key)
        fernet = Fernet(fernet_key)

        self._key_cache[project_id] = fernet
        return fernet

    def encrypt(self, project_id: uuid.UUID, plaintext: str) -> str:
        """Encrypt plaintext string.

        Args:
            project_id: Project to scope the encryption to
            plaintext: String to encrypt

        Returns:
            Prefixed base64 ciphertext (fernet:v1:...)

        Raises:
            RuntimeError: If encryption is not enabled
        """
        if not self.is_enabled:
            raise RuntimeError("Encryption is not enabled")

        fernet = self.derive_project_key(project_id)
        ciphertext = fernet.encrypt(plaintext.encode("utf-8"))
        return _ENCRYPTED_PREFIX + ciphertext.decode("utf-8")

    def decrypt(self, project_id: uuid.UUID, ciphertext: str) -> str:
        """Decrypt ciphertext string.

        Args:
            project_id: Project the data was encrypted for
            ciphertext: Prefixed ciphertext from encrypt()

        Returns:
            Decrypted plaintext string

        Raises:
            RuntimeError: If encryption is not enabled
            ValueError: If ciphertext format is invalid
            cryptography.fernet.InvalidToken: If decryption fails
        """
        if not self.is_enabled:
            raise RuntimeError("Encryption is not enabled")

        if not ciphertext.startswith(_ENCRYPTED_PREFIX):
            raise ValueError("Invalid ciphertext format (missing prefix)")

        raw_ciphertext = ciphertext[len(_ENCRYPTED_PREFIX) :]
        fernet = self.derive_project_key(project_id)
        plaintext = fernet.decrypt(raw_ciphertext.encode("utf-8"))
        return plaintext.decode("utf-8")

    def encrypt_dict(self, project_id: uuid.UUID, data: dict) -> str:
        """Encrypt a dictionary as JSON.

        Args:
            project_id: Project to scope the encryption to
            data: Dictionary to encrypt

        Returns:
            Prefixed base64 ciphertext
        """
        json_str = json.dumps(data, separators=(",", ":"))
        return self.encrypt(project_id, json_str)

    def decrypt_dict(self, project_id: uuid.UUID, ciphertext: str) -> dict:
        """Decrypt ciphertext to a dictionary.

        Args:
            project_id: Project the data was encrypted for
            ciphertext: Prefixed ciphertext from encrypt_dict()

        Returns:
            Decrypted dictionary
        """
        json_str = self.decrypt(project_id, ciphertext)
        return json.loads(json_str)

    def is_encrypted(self, value: str | None) -> bool:
        """Check if a value is Fernet-encrypted (has our prefix).

        Args:
            value: The stored value to check

        Returns:
            True if the value appears to be encrypted
        """
        if not value:
            return False
        return value.startswith(_ENCRYPTED_PREFIX)

    def decrypt_or_parse_json(
        self, project_id: uuid.UUID, value: str | None
    ) -> dict:
        """Decrypt if encrypted, otherwise parse as plain JSON.

        This provides backward compatibility with unencrypted data.

        Args:
            project_id: Project ID for decryption
            value: Stored value (encrypted or plain JSON)

        Returns:
            Decrypted/parsed dictionary, or empty dict if value is None
        """
        if not value:
            return {}

        if self.is_encrypted(value):
            if not self.is_enabled:
                log.error(
                    "crypto_decrypt_failed",
                    reason="encrypted_data_but_no_key",
                    hint="Set WORKSHOP_ENCRYPTION_KEY to decrypt",
                )
                return {}
            try:
                return self.decrypt_dict(project_id, value)
            except InvalidToken:
                log.error(
                    "crypto_decrypt_failed",
                    reason="invalid_token",
                    project_id=str(project_id),
                )
                return {}
            except Exception as e:
                log.error(
                    "crypto_decrypt_failed",
                    reason="unexpected_error",
                    error=str(e),
                )
                return {}

        try:
            return json.loads(value)
        except json.JSONDecodeError:
            log.error(
                "crypto_json_parse_failed",
                project_id=str(project_id),
            )
            return {}

    def encrypt_or_json(
        self, project_id: uuid.UUID, data: dict
    ) -> str:
        """Encrypt if enabled, otherwise return plain JSON.

        Args:
            project_id: Project ID for encryption
            data: Dictionary to store

        Returns:
            Encrypted ciphertext or plain JSON string
        """
        if not data:
            return "{}"

        if self.is_enabled:
            return self.encrypt_dict(project_id, data)
        else:
            return json.dumps(data, separators=(",", ":"))

    def clear_key_cache(self) -> None:
        """Clear the derived key cache.

        Call this if the master key changes (e.g., in tests).
        """
        self._key_cache.clear()


@lru_cache(maxsize=1)
def get_crypto_service() -> CryptoService:
    """Get the singleton crypto service instance.

    Reads the master key from settings on first call.
    """
    settings = get_settings()

    master_key: bytes | None = None
    if settings.workshop_encryption_key:
        try:
            master_key = base64.urlsafe_b64decode(
                settings.workshop_encryption_key.encode("utf-8")
            )
            if len(master_key) != 32:
                log.error(
                    "crypto_invalid_key_length",
                    expected=32,
                    actual=len(master_key),
                )
                master_key = None
        except Exception as e:
            log.error(
                "crypto_key_decode_failed",
                error=str(e),
            )
            master_key = None

    return CryptoService(master_key)


def generate_encryption_key() -> str:
    """Generate a new encryption key for configuration.

    Returns:
        Base64-encoded 32-byte key suitable for WORKSHOP_ENCRYPTION_KEY
    """
    return Fernet.generate_key().decode("utf-8")
