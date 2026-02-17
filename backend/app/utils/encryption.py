"""
Encryption utilities for sensitive data storage.

Uses Fernet (AES-128) symmetric encryption for API keys and other secrets.
"""

import os
import logging
from cryptography.fernet import Fernet
from pathlib import Path

logger = logging.getLogger(__name__)

# Encryption key location - stored in app data directory
ENCRYPTION_KEY_FILE = Path.home() / ".scythe" / "encryption.key"


def _get_or_create_encryption_key() -> bytes:
    """
    Get encryption key from file or environment variable.
    Auto-generates and saves if not found.

    Returns:
        bytes: Fernet encryption key
    """
    # Try environment variable first
    env_key = os.getenv("ENCRYPTION_KEY")
    if env_key:
        try:
            # Validate it's a valid Fernet key
            Fernet(env_key.encode())
            return env_key.encode()
        except Exception as e:
            logger.warning(f"Invalid ENCRYPTION_KEY in environment: {e}")

    # Try loading from file
    if ENCRYPTION_KEY_FILE.exists():
        try:
            key = ENCRYPTION_KEY_FILE.read_bytes()
            # Validate it's a valid Fernet key
            Fernet(key)
            return key
        except Exception as e:
            logger.warning(f"Invalid encryption key in file: {e}")

    # Generate new key
    logger.info("Generating new encryption key")
    key = Fernet.generate_key()

    # Save to file
    try:
        ENCRYPTION_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        ENCRYPTION_KEY_FILE.write_bytes(key)
        # Set restrictive permissions (owner read/write only)
        ENCRYPTION_KEY_FILE.chmod(0o600)
        logger.info(f"Saved encryption key to {ENCRYPTION_KEY_FILE}")
    except Exception as e:
        logger.error(f"Failed to save encryption key: {e}")

    return key


def encrypt(plaintext: str) -> str:
    """
    Encrypt a plaintext string.

    Args:
        plaintext: String to encrypt

    Returns:
        str: Encrypted string (base64 encoded)
    """
    if not plaintext:
        return ""

    key = _get_or_create_encryption_key()
    fernet = Fernet(key)
    encrypted = fernet.encrypt(plaintext.encode())
    return encrypted.decode()


def decrypt(ciphertext: str) -> str:
    """
    Decrypt an encrypted string.

    Args:
        ciphertext: Encrypted string (base64 encoded)

    Returns:
        str: Decrypted plaintext string
    """
    if not ciphertext:
        return ""

    key = _get_or_create_encryption_key()
    fernet = Fernet(key)
    try:
        decrypted = fernet.decrypt(ciphertext.encode())
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Failed to decrypt data: {e}")
        raise ValueError("Failed to decrypt data - encryption key may have changed")


def mask_api_key(api_key: str, show_chars: int = 4) -> str:
    """
    Mask an API key for display purposes.

    Args:
        api_key: Full API key
        show_chars: Number of characters to show at end

    Returns:
        str: Masked API key (e.g., "sk-or-...xyz123")
    """
    if not api_key or len(api_key) <= show_chars:
        return "***"

    # Extract prefix if present (e.g., "sk-or-v1-")
    prefix = ""
    if api_key.startswith("sk-"):
        parts = api_key.split("-")
        if len(parts) >= 3:
            prefix = "-".join(parts[:3]) + "-"
            api_key = "-".join(parts[3:])

    suffix = api_key[-show_chars:]
    return f"{prefix}...{suffix}"
